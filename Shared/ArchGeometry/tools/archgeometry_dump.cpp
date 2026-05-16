// archgeometry_dump — canonical output of ArchGeometry generation for a building JSON.
//
// Output is line-oriented and deterministic so a Rust reimplementation can be
// diffed against it for the M1 regression oracle.
//
// Usage:
//     archgeometry_dump <building.json>
//
// Output schema (v1):
//     ARCHGEOMETRY_DUMP v1
//     INPUT <basename>
//     BUILDING id=<id> bounds_min=x,y,z bounds_max=x,y,z
//     WALLS   count=N vertices=V triangles=T hash=0x...
//     FLOORS  count=N vertices=V triangles=T hash=0x...
//     ROOFS   count=N vertices=V triangles=T hash=0x...
//     DOORS   count=N vertices=V triangles=T hash=0x...
//     WINDOWS count=N vertices=V triangles=T hash=0x...
//     ROOMS   count=N hash=0x...
//     END
//
// Hash is FNV-1a 64-bit over a canonical byte sequence: each vertex's position
// (3x float), normal (3x float), color (3x float), uv (2x float), stress (1x
// float) formatted as "%.4f ", followed by each triangle's three indices
// formatted as "%u ". Items are emitted in array order. Items themselves are
// concatenated in (wall_index, element_id) sort order to remove generator
// ordering from the hash; if generation order is part of the contract, this
// changes to source array order — flip the kSortItems flag below.

#include <archgeometry/archgeometry.hpp>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using namespace archgeometry;

namespace {

constexpr bool kSortItems = true;  // emit categories in deterministic order

// FNV-1a 64-bit. Plenty for a regression-oracle diff hash.
constexpr uint64_t kFnvOffset = 14695981039346656037ULL;
constexpr uint64_t kFnvPrime = 1099511628211ULL;

struct Hasher {
    uint64_t state = kFnvOffset;
    void feed(const char* p, size_t n) {
        for (size_t i = 0; i < n; ++i) {
            state ^= static_cast<uint8_t>(p[i]);
            state *= kFnvPrime;
        }
    }
    void feed(const std::string& s) { feed(s.data(), s.size()); }
    void feedf(float f) {
        char buf[32];
        // %.4f gives consistent 4-decimal output. -0 vs 0 is normalised:
        if (f == 0.0f) f = 0.0f;  // turns -0 into +0 in IEEE754
        std::snprintf(buf, sizeof(buf), "%.4f ", f);
        feed(buf, std::strlen(buf));
    }
    void feedu(uint32_t u) {
        char buf[16];
        std::snprintf(buf, sizeof(buf), "%u ", u);
        feed(buf, std::strlen(buf));
    }
};

void hashMesh(Hasher& h, const Mesh3D& m) {
    for (const auto& v : m.vertices) {
        h.feedf(v.position.x); h.feedf(v.position.y); h.feedf(v.position.z);
        h.feedf(v.normal.x);   h.feedf(v.normal.y);   h.feedf(v.normal.z);
        h.feedf(v.color.x);    h.feedf(v.color.y);    h.feedf(v.color.z);
        h.feedf(v.uv.x);       h.feedf(v.uv.y);
        h.feedf(v.stress);
    }
    for (const auto& t : m.faces) {
        h.feedu(t.v0); h.feedu(t.v1); h.feedu(t.v2);
    }
}

template <typename T>
void emitCategory(const char* label,
                  const std::vector<T>& items,
                  std::vector<size_t> order,
                  Mesh3D T::* meshField) {
    Hasher h;
    size_t totalV = 0, totalT = 0;
    for (size_t idx : order) {
        const auto& it = items[idx];
        if (meshField) {
            const Mesh3D& m = it.*meshField;
            hashMesh(h, m);
            totalV += m.vertices.size();
            totalT += m.faces.size();
        }
    }
    std::printf("%-8s count=%zu vertices=%zu triangles=%zu hash=0x%016llx\n",
                label, items.size(), totalV, totalT,
                static_cast<unsigned long long>(h.state));
}

template <typename T, typename KeyFn>
std::vector<size_t> sortedOrder(const std::vector<T>& items, KeyFn keyOf) {
    std::vector<size_t> idx(items.size());
    for (size_t i = 0; i < items.size(); ++i) idx[i] = i;
    if (kSortItems) {
        std::stable_sort(idx.begin(), idx.end(),
            [&](size_t a, size_t b) { return keyOf(items[a]) < keyOf(items[b]); });
    }
    return idx;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::fprintf(stderr, "usage: archgeometry_dump <building.json>\n");
        return 2;
    }
    const std::string path = argv[1];
    if (!fs::exists(path)) {
        std::fprintf(stderr, "error: file not found: %s\n", path.c_str());
        return 2;
    }

    auto result = ArchGeometry::generateFromFile(path);
    if (!isSuccess(result)) {
        const auto& err = getError(result);
        std::fprintf(stderr, "error: %s (line=%d col=%d)\n",
                     err.message.c_str(), err.line, err.column);
        return 1;
    }
    const BuildingGeometry& g = getValue(result);

    std::printf("ARCHGEOMETRY_DUMP v1\n");
    std::printf("INPUT %s\n", fs::path(path).filename().string().c_str());
    std::printf("BUILDING id=%s bounds_min=%.4f,%.4f,%.4f bounds_max=%.4f,%.4f,%.4f\n",
                g.building_id.empty() ? "-" : g.building_id.c_str(),
                g.bounds_min.x, g.bounds_min.y, g.bounds_min.z,
                g.bounds_max.x, g.bounds_max.y, g.bounds_max.z);

    emitCategory("WALLS",   g.walls,
                 sortedOrder(g.walls,   [](const WallGeometry& w)   { return std::pair{w.wall_index, w.wall_id}; }),
                 &WallGeometry::mesh_3d);
    emitCategory("FLOORS",  g.floors,
                 sortedOrder(g.floors,  [](const FloorGeometry& f)  { return std::pair{f.floor_index, f.floor_id}; }),
                 &FloorGeometry::mesh_3d);
    emitCategory("ROOFS",   g.roofs,
                 sortedOrder(g.roofs,   [](const RoofGeometry& r)   { return std::pair{r.roof_index, r.roof_id}; }),
                 &RoofGeometry::mesh_3d);
    emitCategory("DOORS",   g.doors,
                 sortedOrder(g.doors,   [](const DoorGeometry& d)   { return std::pair{d.door_index, d.door_id}; }),
                 &DoorGeometry::mesh_3d);
    emitCategory("WINDOWS", g.windows,
                 sortedOrder(g.windows, [](const WindowGeometry& w) { return std::pair{w.window_index, w.window_id}; }),
                 &WindowGeometry::mesh_3d);

    // Rooms are 2D boundaries, no Mesh3D. Hash polygon points + area + label.
    {
        Hasher h;
        auto order = sortedOrder(g.rooms, [](const RoomBoundary& r) { return r.room_id; });
        for (size_t idx : order) {
            const auto& r = g.rooms[idx];
            h.feed(r.room_id); h.feed(" ");
            h.feedf(r.area);
            h.feedf(r.center.x); h.feedf(r.center.y);
            for (const auto& p : r.boundary.points) {
                h.feedf(p.x); h.feedf(p.y);
            }
        }
        std::printf("%-8s count=%zu hash=0x%016llx\n",
                    "ROOMS", g.rooms.size(),
                    static_cast<unsigned long long>(h.state));
    }

    std::printf("END\n");
    return 0;
}
