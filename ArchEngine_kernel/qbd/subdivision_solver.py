"""
subdivision_solver.py - BSP-style top-down room placement.

Alternative to coordinate_solver's backtracking approach. Starts with the
building envelope and subdivides it room by room, big rooms first. Result:
clean envelope walls (4 for rectangle, 6 for L), no unused interior space.

Algorithm (per user spec 2026-04-30):
    1. Anchor: place entry at the entry edge (small footprint).
    2. Hallway: reserve a minimal strip (44") from entry into the building.
    3. BIG rooms (program-defined): living, dining, kitchen, primary_bedroom,
       garage. Cut perpendicular to longest edge of best free rectangle;
       slice anchored on the side that satisfies must_touch.
    4. MEDIUM rooms: bedrooms, primary_bath, office, mudroom.
    5. SMALL rooms: bathrooms, closets, laundry, pantry — fill remainder.
    6. Verify min_area; if any room infeasible, shrink big-room targets and
       retry (one iteration max for now).

Phase 1 (this version): rectangular envelope only, simple greedy placement.
L-envelope, budget integration, and look-ahead heuristics deferred.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

from collections import defaultdict
from coordinate_solver import Rect, Point, PlacedRoom, PlacedLayout, WallCoordinate
from wall_graph import WallType, OpeningType
from room_relationships import SpatialGraph


# =============================================================================
# ROOM TIERS — program role determines size priority
# =============================================================================

BIG_ROOM_TYPES = {
    "living", "great_room", "dining", "kitchen",
    "primary_bedroom", "garage",
}

MEDIUM_ROOM_TYPES = {
    "bedroom", "primary_bath", "office", "mudroom", "foyer",
}

SMALL_ROOM_TYPES = {
    "bathroom", "powder_room",
    "closet", "walk_in_closet", "coat_closet",
    "laundry", "pantry", "mechanical",
}


def _room_tier(room_id: str, room_type: str) -> str:
    """Return 'big', 'medium', or 'small' based on program role."""
    base = room_type
    # Strip numeric suffix: "bedroom_2" -> "bedroom"
    if room_type not in (BIG_ROOM_TYPES | MEDIUM_ROOM_TYPES | SMALL_ROOM_TYPES):
        base = room_id.split("_")[0]
    if base in BIG_ROOM_TYPES:
        return "big"
    if base in MEDIUM_ROOM_TYPES:
        return "medium"
    if base in SMALL_ROOM_TYPES:
        return "small"
    return "medium"


# =============================================================================
# SOLVER
# =============================================================================

@dataclass
class SubdivisionResult:
    placed: Dict[str, Rect] = field(default_factory=dict)
    free: List[Rect] = field(default_factory=list)
    unplaced: List[str] = field(default_factory=list)
    iterations: int = 1

    @property
    def success(self) -> bool:
        return len(self.unplaced) == 0


class SubdivisionSolver:
    HALLWAY_WIDTH = 4.0  # feet (~1220mm)
    ENTRY_WIDTH = 6.0
    ENTRY_DEPTH = 8.0
    MIN_ROOM_DIM = 4.0  # feet — minimum closet depth; below this is unusable

    def __init__(self, graph: SpatialGraph, envelope: Rect, entry_edge: str = "south"):
        self.graph = graph
        self.envelope = envelope
        self.entry_edge = entry_edge

    def solve(self) -> SubdivisionResult:
        """BSP with hallway as first-class spine. Layout is three strips:
        public-side, hallway, private-side. Each room slice spans the strip's
        SHORT axis, so by construction every room shares an edge with the
        hallway — every room is one door away from circulation."""
        rooms_dict = self.graph.rooms

        # Categorize rooms by zone
        entry_room = rooms_dict.get("entry")
        hallway_room = rooms_dict.get("hallway")

        public_rooms = []   # entry-side: living, dining, kitchen, garage, mudroom
        private_rooms = []  # back: bedrooms, baths, closets, office, laundry

        # Bundle small rooms inside larger parent rooms — small rooms can't
        # span the full strip depth without becoming unusable slivers.
        # Architectural pairings (Ontario residential):
        #   - bedroom suites: closets + primary bath inside parent bedroom
        #   - service area: mudroom + laundry inside garage zone
        #   - public area: entry inside living (foyer), dining inside kitchen (open plan)
        suite_pairs = {
            # Bedroom suites
            "primary_closet": "primary_bedroom",
            "primary_bath": "primary_bedroom",
            "closet_2": "bedroom_2",
            "closet_3": "bedroom_3",
            "closet_4": "bedroom_4",
            # Service area
            "mudroom": "garage",
            "laundry": "garage",
            # Public area (avoid sliver rooms)
            "entry": "living",          # entry vestibule inside living's slice
            "dining": "kitchen",        # open kit-din
        }
        # Map parent_id -> list of (child_id, child_room)
        bundles: Dict[str, List] = defaultdict(list)
        for child_id, parent_id in suite_pairs.items():
            if child_id in rooms_dict and parent_id in rooms_dict:
                bundles[parent_id].append((child_id, rooms_dict[child_id]))

        for rid, r in rooms_dict.items():
            if rid == "hallway":
                continue
            if rid in suite_pairs:  # skip bundled children — placed via parent
                continue
            z = _zone_of(rid, r.room_type)
            if z in ("public", "service"):
                public_rooms.append(r)
            else:
                private_rooms.append(r)

        # Set target areas. Bedroom parents inherit their children's area too.
        for r in rooms_dict.values():
            r.target_area = max(r.min_area * 1.10, r.min_area)
        for parent_id, children in bundles.items():
            parent = rooms_dict.get(parent_id)
            if parent:
                child_total = sum(c.target_area for _, c in children)
                parent.target_area = parent.target_area + child_total
                parent._bundled_children = children  # remember for sub-placement

        env = self.envelope
        hallway_t = self.HALLWAY_WIDTH

        # Compute strip dimensions (entry is now bundled inside living, no separate add)
        public_area = sum(r.target_area for r in public_rooms)
        private_area = sum(r.target_area for r in private_rooms)

        if self.entry_edge in ("south", "north"):
            avail_h = env.height - hallway_t
            public_h = avail_h * (public_area / max(public_area + private_area, 1))
            private_h = avail_h - public_h
            # Ensure both have minimum room depth
            public_h = max(self.MIN_ROOM_DIM * 2, public_h)
            private_h = max(self.MIN_ROOM_DIM * 2, env.height - hallway_t - public_h)

            if self.entry_edge == "south":
                public_strip = Rect(env.x, env.y, env.width, public_h)
                hallway_strip = Rect(env.x, env.y + public_h, env.width, hallway_t)
                private_strip = Rect(env.x, env.y + public_h + hallway_t,
                                     env.width, private_h)
            else:  # north
                private_strip = Rect(env.x, env.y, env.width, private_h)
                hallway_strip = Rect(env.x, env.y + private_h, env.width, hallway_t)
                public_strip = Rect(env.x, env.y + private_h + hallway_t,
                                    env.width, public_h)
        else:
            # Vertical strips (entry on west/east)
            avail_w = env.width - hallway_t
            public_w = avail_w * (public_area / max(public_area + private_area, 1))
            private_w = avail_w - public_w
            public_w = max(self.MIN_ROOM_DIM * 2, public_w)
            private_w = max(self.MIN_ROOM_DIM * 2, env.width - hallway_t - public_w)

            if self.entry_edge == "west":
                public_strip = Rect(env.x, env.y, public_w, env.height)
                hallway_strip = Rect(env.x + public_w, env.y, hallway_t, env.height)
                private_strip = Rect(env.x + public_w + hallway_t, env.y,
                                     private_w, env.height)
            else:  # east
                private_strip = Rect(env.x, env.y, private_w, env.height)
                hallway_strip = Rect(env.x + private_w, env.y, hallway_t, env.height)
                public_strip = Rect(env.x + private_w + hallway_t, env.y,
                                    public_w, env.height)

        placed: Dict[str, Rect] = {}
        if hallway_room:
            placed["hallway"] = hallway_strip

        # Bathroom min width: ≥6ft for any bath in a strip. Bump target_area
        # so BSP allocates enough width. Computed here because we need the
        # actual strip depth (private_strip.height).
        BATH_MIN_WIDTH = 6.0
        priv_strip_depth = (private_strip.height
                            if private_strip.width >= private_strip.height
                            else private_strip.width)
        for r in private_rooms:
            rt = r.room_type
            base = rt if rt in PRIVATE_ZONE else r.id.split("_")[0]
            if base in ("bathroom", "primary_bath", "powder_room"):
                r.target_area = max(r.target_area, BATH_MIN_WIDTH * priv_strip_depth)

        # BSP public strip (entry bundled inside living, dining bundled inside kitchen)
        for rid, rect in self._bsp_strip(public_strip, list(public_rooms)).items():
            placed[rid] = rect

        # BSP private strip
        for rid, rect in self._bsp_strip(private_strip, private_rooms).items():
            placed[rid] = rect

        unplaced = [rid for rid in rooms_dict if rid not in placed]
        return SubdivisionResult(placed=placed, free=[], unplaced=unplaced)

    def _bsp_strip(self, strip: Rect, rooms: List, axis: Optional[str] = None) -> Dict[str, Rect]:
        """Recursive BSP within a strip. ALL cuts use the same axis (the strip's
        original LONG axis), so every leaf face spans the strip's short axis
        and therefore shares an edge with the hallway."""
        if axis is None:
            axis = "x" if strip.width >= strip.height else "y"
        if not rooms:
            return {}
        if len(rooms) == 1:
            room = rooms[0]
            placed = {room.id: strip}
            # If this room has bundled children (closets), sub-divide its slice
            # to place them inside (en-suite, not on the corridor).
            children = getattr(room, "_bundled_children", None)
            if children:
                placed.update(self._place_bundled_children(strip, room, children, axis))
            return placed

        rooms_sorted = sorted(rooms, key=lambda r: -r.target_area)
        total = sum(r.target_area for r in rooms)
        half = total / 2.0

        a, b = [], []
        acc = 0.0
        for r in rooms_sorted:
            if acc + r.target_area <= half * 1.2 or not a:
                a.append(r)
                acc += r.target_area
            else:
                b.append(r)
        if not a:
            a.append(b.pop(0))
        if not b:
            b.append(a.pop(-1))

        ratio = sum(r.target_area for r in a) / total

        if axis == "x":
            # All cuts in a horizontal strip stay vertical — every leaf spans full height
            cut = strip.x + strip.width * ratio
            cut = max(strip.x + self.MIN_ROOM_DIM,
                      min(cut, strip.x2 - self.MIN_ROOM_DIM))
            face_a = Rect(strip.x, strip.y, cut - strip.x, strip.height)
            face_b = Rect(cut, strip.y, strip.x2 - cut, strip.height)
        else:
            cut = strip.y + strip.height * ratio
            cut = max(strip.y + self.MIN_ROOM_DIM,
                      min(cut, strip.y2 - self.MIN_ROOM_DIM))
            face_a = Rect(strip.x, strip.y, strip.width, cut - strip.y)
            face_b = Rect(strip.x, cut, strip.width, strip.y2 - cut)

        return {**self._bsp_strip(face_a, a, axis),
                **self._bsp_strip(face_b, b, axis)}

    def _place_bundled_children(self, parent_slice: Rect, parent, children: List,
                                 strip_axis: str) -> Dict[str, Rect]:
        """Place children (closets, en-suite bath, etc.) inside the parent
        slice. Children get a thin strip on the FAR side (away from hallway)
        so the parent keeps its hallway adjacency.

        If any child is a BATH, the strip depth gets bumped to ≥6ft so the
        bath has walkable proportions (closets are happy with 4ft)."""
        BATH_MIN_DEPTH = 6.5  # ft — bath needs walkable depth in a strip layout
        has_bath = any(
            c.room_type in ("primary_bath", "bathroom") or c.id.split("_")[0] == "bathroom"
            for _, c in children
        )
        # Total child area
        child_area = sum(c.target_area for _, c in children)
        result: Dict[str, Rect] = {}

        # Determine the FAR side of the parent slice (away from hallway).
        # The hallway runs along ONE of the long edges of the strip:
        # - For a horizontal strip (axis='x'), hallway is along y=top or y=bottom
        # - We don't have explicit hallway info here, so use the side opposite
        #   to the parent's LARGEST shared edge with the rest of the building.
        # Heuristic: place children on the side OPPOSITE to the strip's long axis.
        # Specifically: for axis='x', children get a slice along the short (y)
        # direction at one end; the bedroom keeps the hallway-facing edge.

        if strip_axis == "x":
            # Strip cuts vertically; rooms span full height. Place closet at the
            # TOP (far from south hallway) or BOTTOM (far from north hallway).
            # For simplicity, place closet on the side AWAY from y=center of envelope.
            # Better heuristic: closet on the back wall.
            # Use parent_slice.y vs envelope center: closet farther from center.
            env_cy = self.envelope.y + self.envelope.height / 2
            closet_at_top = parent_slice.y + parent_slice.height / 2 > env_cy
            closet_h = child_area / parent_slice.width
            if closet_h < self.MIN_ROOM_DIM:
                closet_h = self.MIN_ROOM_DIM
            if has_bath and closet_h < BATH_MIN_DEPTH:
                closet_h = BATH_MIN_DEPTH
            if closet_at_top:
                closet_strip = Rect(parent_slice.x, parent_slice.y2 - closet_h,
                                     parent_slice.width, closet_h)
                bedroom_slice = Rect(parent_slice.x, parent_slice.y,
                                      parent_slice.width, parent_slice.height - closet_h)
            else:
                closet_strip = Rect(parent_slice.x, parent_slice.y,
                                     parent_slice.width, closet_h)
                bedroom_slice = Rect(parent_slice.x, parent_slice.y + closet_h,
                                      parent_slice.width, parent_slice.height - closet_h)
            result[parent.id] = bedroom_slice
            # If multiple children, subdivide closet_strip among them
            if len(children) == 1:
                result[children[0][0]] = closet_strip
            else:
                # Subdivide along x
                total_child = sum(c.target_area for _, c in children)
                cursor = closet_strip.x
                for child_id, c in children:
                    w = closet_strip.width * (c.target_area / total_child)
                    result[child_id] = Rect(cursor, closet_strip.y, w, closet_strip.height)
                    cursor += w
        else:
            # axis='y' — vertical strip, cuts horizontal. Closet on far x side.
            env_cx = self.envelope.x + self.envelope.width / 2
            closet_at_right = parent_slice.x + parent_slice.width / 2 > env_cx
            closet_w = child_area / parent_slice.height
            if closet_w < self.MIN_ROOM_DIM:
                closet_w = self.MIN_ROOM_DIM
            if has_bath and closet_w < BATH_MIN_DEPTH:
                closet_w = BATH_MIN_DEPTH
            if closet_at_right:
                closet_strip = Rect(parent_slice.x2 - closet_w, parent_slice.y,
                                     closet_w, parent_slice.height)
                bedroom_slice = Rect(parent_slice.x, parent_slice.y,
                                      parent_slice.width - closet_w, parent_slice.height)
            else:
                closet_strip = Rect(parent_slice.x, parent_slice.y,
                                     closet_w, parent_slice.height)
                bedroom_slice = Rect(parent_slice.x + closet_w, parent_slice.y,
                                      parent_slice.width - closet_w, parent_slice.height)
            result[parent.id] = bedroom_slice
            if len(children) == 1:
                result[children[0][0]] = closet_strip
            else:
                total_child = sum(c.target_area for _, c in children)
                cursor = closet_strip.y
                for child_id, c in children:
                    h = closet_strip.height * (c.target_area / total_child)
                    result[child_id] = Rect(closet_strip.x, cursor, closet_strip.width, h)
                    cursor += h
        return result

    def _bsp(self, face: Rect, rooms: List, depth: int) -> Dict[str, Rect]:
        """Recursive bisection. Each call: subdivide `face` among `rooms`."""
        if not rooms:
            return {}
        if len(rooms) == 1:
            # Whole face becomes this room
            return {rooms[0].id: face}

        # Pick cut axis: at depth 0, perpendicular to the entry edge
        # (separates front/back). After that, perpendicular to longest edge
        # of the current face (keeps room aspects square-ish).
        if depth == 0 and self.entry_edge in ("south", "north"):
            axis = "y"  # horizontal cut
        elif depth == 0 and self.entry_edge in ("east", "west"):
            axis = "x"  # vertical cut
        else:
            axis = "x" if face.width >= face.height else "y"

        # Partition rooms into two groups
        group_a, group_b = self._partition(rooms, face, axis, depth)
        if not group_a or not group_b:
            # Degenerate split — shouldn't happen with our heuristic but handle it
            single = group_a or group_b
            return self._bsp(face, single, depth + 1)

        # Cut position by area ratio
        area_a = sum(r.target_area for r in group_a)
        area_b = sum(r.target_area for r in group_b)
        ratio = area_a / (area_a + area_b)
        # Clamp ratio so we don't produce tiny faces unable to fit MIN_ROOM_DIM
        if axis == "x":
            min_ratio = self.MIN_ROOM_DIM / face.width
            max_ratio = 1.0 - min_ratio
            ratio = max(min_ratio, min(max_ratio, ratio))
            cut = face.x + face.width * ratio
            face_a = Rect(face.x, face.y, cut - face.x, face.height)
            face_b = Rect(cut, face.y, face.x2 - cut, face.height)
        else:
            min_ratio = self.MIN_ROOM_DIM / face.height
            max_ratio = 1.0 - min_ratio
            ratio = max(min_ratio, min(max_ratio, ratio))
            cut = face.y + face.height * ratio
            face_a = Rect(face.x, face.y, face.width, cut - face.y)
            face_b = Rect(face.x, cut, face.width, face.y2 - cut)

        return {**self._bsp(face_a, group_a, depth + 1),
                **self._bsp(face_b, group_b, depth + 1)}

    def _partition(self, rooms: List, face: Rect, axis: str,
                   depth: int) -> Tuple[List, List]:
        """Split rooms into two groups for a BSP cut. Strategy:
           - Depth 0: zone-based (public/circulation vs private/service)
           - Deeper: balanced area split"""
        if depth == 0:
            front, back = [], []
            for r in rooms:
                z = _zone_of(r.id, r.room_type)
                if z in ("public", "circulation"):
                    front.append(r)
                else:
                    back.append(r)
            if front and back:
                # Anchor "front" to the entry-edge side
                if self.entry_edge in ("south", "west"):
                    return front, back
                return back, front

        # Balanced area split (rooms sorted big→small for stability)
        rooms_sorted = sorted(rooms, key=lambda r: -r.target_area)
        half = sum(r.target_area for r in rooms) / 2.0
        a, b = [], []
        acc_a = 0.0
        for r in rooms_sorted:
            if acc_a + r.target_area <= half * 1.2:
                a.append(r)
                acc_a += r.target_area
            else:
                b.append(r)
        # Make sure both groups are non-empty
        if not a:
            a.append(b.pop(0))
        if not b:
            b.append(a.pop(-1))
        return a, b


class _BSPFailure(Exception):
    """Raised when BSP can't continue. Includes partial placements."""
    def __init__(self, placed: Dict[str, Rect], unplaced: List[str]):
        super().__init__("BSP subdivision failed")
        self.placed = placed
        self.unplaced = unplaced


PUBLIC_ZONE = {"entry", "living", "great_room", "dining", "kitchen",
               "foyer", "powder_room"}
PRIVATE_ZONE = {"primary_bedroom", "bedroom", "primary_bath", "bathroom",
                "primary_closet", "closet", "walk_in_closet", "coat_closet",
                "office"}
SERVICE_ZONE = {"mudroom", "pantry", "mechanical", "laundry", "garage"}
CIRCULATION_ZONE = {"hallway"}


def _zone_of(room_id: str, room_type: str) -> str:
    base = room_type
    if room_type not in (PUBLIC_ZONE | PRIVATE_ZONE | SERVICE_ZONE | CIRCULATION_ZONE):
        base = room_id.split("_")[0]
    if base in PUBLIC_ZONE: return "public"
    if base in PRIVATE_ZONE: return "private"
    if base in SERVICE_ZONE: return "service"
    if base in CIRCULATION_ZONE: return "circulation"
    return "other"

    # ============================ legacy below =============================

    def _solve_pass(self, target_scale: float) -> SubdivisionResult:
        free: List[Rect] = [self.envelope]
        placed: Dict[str, Rect] = {}
        unplaced: List[str] = []

        # 1. Anchor: entry
        entry_rect = self._place_entry()
        placed["entry"] = entry_rect
        free = self._subtract(free, entry_rect)

        # 2. Hallway: minimal strip
        if "hallway" in self.graph.rooms:
            hall = self._place_hallway(entry_rect)
            if hall is not None:
                placed["hallway"] = hall
                free = self._subtract(free, hall)

        # 3-5. Place by tier, biggest first within each tier
        tiers = self._rooms_by_tier()
        for tier_name in ("big", "medium", "small"):
            for room_id in tiers.get(tier_name, []):
                if room_id in placed:
                    continue
                rect, free = self._place_room(room_id, free, placed,
                                               target_scale=target_scale)
                if rect is None:
                    unplaced.append(room_id)
                else:
                    placed[room_id] = rect

        return SubdivisionResult(placed=placed, free=free, unplaced=unplaced)

    # ------------------------------------------------------------------ steps

    def _place_entry(self) -> Rect:
        """Place entry at a corner of the entry edge (not centered) so the
        remainder is a single continuous rectangle, not 4 fragments."""
        env = self.envelope
        w, d = self.ENTRY_WIDTH, self.ENTRY_DEPTH
        if self.entry_edge == "south":
            return Rect(env.x, env.y, w, d)  # SW corner
        if self.entry_edge == "north":
            return Rect(env.x, env.y2 - d, w, d)  # NW corner
        if self.entry_edge == "west":
            return Rect(env.x, env.y, d, w)  # SW corner
        return Rect(env.x2 - d, env.y, d, w)  # SE corner (east entry)

    def _place_hallway(self, entry_rect: Rect) -> Optional[Rect]:
        """Single perpendicular strip from the entry into the building."""
        env = self.envelope
        hw = self.HALLWAY_WIDTH
        edge_clearance = 8.0  # leave 8ft for end-of-hallway rooms
        if self.entry_edge in ("south", "north"):
            x_center = entry_rect.x + entry_rect.width / 2
            if self.entry_edge == "south":
                y_start = entry_rect.y2
                y_end = env.y2 - edge_clearance
            else:
                y_start = env.y + edge_clearance
                y_end = entry_rect.y
            length = y_end - y_start
            if length < self.MIN_ROOM_DIM:
                return None
            return Rect(x_center - hw / 2, y_start, hw, length)
        else:  # west / east
            y_center = entry_rect.y + entry_rect.height / 2
            if self.entry_edge == "west":
                x_start = entry_rect.x2
                x_end = env.x2 - edge_clearance
            else:
                x_start = env.x + edge_clearance
                x_end = entry_rect.x
            length = x_end - x_start
            if length < self.MIN_ROOM_DIM:
                return None
            return Rect(x_start, y_center - hw / 2, length, hw)

    def _rooms_by_tier(self) -> Dict[str, List[str]]:
        """Group rooms by tier; sort each tier biggest-first by min_area."""
        tiers: Dict[str, List[str]] = {"big": [], "medium": [], "small": []}
        for rid, room in self.graph.rooms.items():
            if rid in ("entry", "hallway"):
                continue
            tier = _room_tier(rid, room.room_type)
            tiers[tier].append(rid)
        for tier in tiers:
            tiers[tier].sort(key=lambda rid: -self.graph.rooms[rid].min_area)
        return tiers

    def _place_room(self, room_id: str, free: List[Rect],
                    placed: Dict[str, Rect],
                    target_scale: float = 1.10) -> Tuple[Optional[Rect], List[Rect]]:
        """Pick best free rect, cut a slice for the room."""
        room = self.graph.rooms[room_id]
        target_area = room.min_area * target_scale

        must_touch = self._must_touch_for(room_id, placed)

        # Score and pick best free rect
        candidates: List[Tuple[float, Rect]] = []
        for fr in free:
            if fr.area < room.min_area * 0.95:
                continue
            score = self._score_free(fr, room, target_area, must_touch, placed)
            candidates.append((score, fr))
        if not candidates:
            return None, free

        candidates.sort(key=lambda c: -c[0])
        chosen = candidates[0][1]

        # Cut perpendicular to longest edge
        room_rect = self._cut_slice(chosen, target_area, must_touch, placed)
        if room_rect is None:
            return None, free

        new_free = self._subtract(free, room_rect)
        return room_rect, new_free

    def _cut_slice(self, free_r: Rect, target_area: float,
                   must_touch: List[str], placed: Dict[str, Rect],
                   target_aspect: float = 1.0) -> Optional[Rect]:
        """Cut a corner chunk from free_r sized to ~target_area with a
        roughly square aspect (default). The remainder is L-shaped; _subtract
        handles its decomposition into rectangles for subsequent placements.

        target_aspect: width/height ratio of the room (1.0 = square).
        """
        import math
        # Compute desired room dimensions
        room_h = math.sqrt(target_area / target_aspect)
        room_w = target_area / room_h

        # Clamp to free rect — if it doesn't fit, take the most that does
        if room_w > free_r.width:
            room_w = free_r.width
            room_h = target_area / room_w
        if room_h > free_r.height:
            room_h = free_r.height
            room_w = target_area / room_h
        if room_w > free_r.width:  # second pass after height clamp
            room_w = free_r.width

        # Reject if either dim is unusable
        if room_w < self.MIN_ROOM_DIM or room_h < self.MIN_ROOM_DIM:
            return None

        # Pick which corner to anchor at based on must_touch adjacency
        anchor_x = "low"  # left
        anchor_y = "low"  # bottom
        tol = 0.5
        for mt_id in must_touch:
            if mt_id not in placed:
                continue
            mt = placed[mt_id]
            if abs(mt.x2 - free_r.x) < tol:
                anchor_x = "low"   # mt is left of free → anchor room left edge to free.x
            elif abs(mt.x - free_r.x2) < tol:
                anchor_x = "high"  # mt is right of free → anchor right edge
            if abs(mt.y2 - free_r.y) < tol:
                anchor_y = "low"
            elif abs(mt.y - free_r.y2) < tol:
                anchor_y = "high"

        x = free_r.x if anchor_x == "low" else free_r.x2 - room_w
        y = free_r.y if anchor_y == "low" else free_r.y2 - room_h
        return Rect(x, y, room_w, room_h)

    def _anchor_left(self, free_r: Rect, must_touch: List[str],
                     placed: Dict[str, Rect], axis: str) -> bool:
        """Return True if the slice should anchor on the lower-coordinate side
        of free_r (left if axis=x, bottom if axis=y), False for upper side."""
        tol = 0.5
        for mt_id in must_touch:
            if mt_id not in placed:
                continue
            mt = placed[mt_id]
            if axis == "x":
                # If must_touch is to the LEFT of free_r, anchor left
                if abs(mt.x2 - free_r.x) < tol:
                    return True
                if abs(mt.x - free_r.x2) < tol:
                    return False
            else:
                if abs(mt.y2 - free_r.y) < tol:
                    return True
                if abs(mt.y - free_r.y2) < tol:
                    return False
        return True  # default: anchor low side

    def _must_touch_for(self, room_id: str, placed: Dict[str, Rect]) -> List[str]:
        """Find which already-placed rooms this room must touch."""
        results = []
        # SpatialGraph stores adjacencies in graph.adjacencies (or similar).
        # Use a defensive lookup via room attributes or graph methods.
        for attr in ("must_touch", "adjacencies"):
            data = getattr(self.graph, attr, None)
            if isinstance(data, dict) and room_id in data:
                for other_id in data[room_id]:
                    if other_id in placed:
                        results.append(other_id)
                return results
        # Fallback: heuristic adjacencies based on room type
        room_type = self.graph.rooms[room_id].room_type
        defaults = {
            "living": ["entry", "hallway"],
            "kitchen": ["living", "dining"],
            "dining": ["kitchen", "living"],
            "bedroom": ["hallway"],
            "primary_bedroom": ["hallway"],
            "primary_bath": ["primary_bedroom"],
            "primary_closet": ["primary_bedroom"],
            "bathroom": ["hallway"],
            "powder_room": ["hallway", "living"],
            "closet": ["hallway"],
            "laundry": ["hallway", "mudroom"],
            "garage": ["mudroom", "entry"],
            "mudroom": ["garage", "entry"],
        }
        for adj in defaults.get(room_type, []):
            if adj in placed:
                results.append(adj)
        return results

    def _score_free(self, free_r: Rect, room, target_area: float,
                    must_touch: List[str], placed: Dict[str, Rect]) -> float:
        """Higher = better fit for this room."""
        score = 0.0
        # Strong bonus for adjacency to must_touch
        for mt_id in must_touch:
            if mt_id in placed and self._rects_adjacent(free_r, placed[mt_id]):
                score += 200
        # Prefer rects close to target area (penalize way-too-big rects too)
        area_ratio = free_r.area / target_area
        if area_ratio < 1.0:
            score -= (1.0 - area_ratio) * 100  # penalize too-small
        elif area_ratio > 3.0:
            score -= (area_ratio - 3.0) * 10  # mild penalize way-too-large
        # Aspect ratio: prefer rects that aren't pencil-thin
        aspect = min(free_r.width, free_r.height) / max(free_r.width, free_r.height)
        score += aspect * 30
        return score

    def _rects_adjacent(self, a: Rect, b: Rect) -> bool:
        tol = 0.5
        if abs(a.x2 - b.x) < tol or abs(a.x - b.x2) < tol:
            return a.y < b.y2 and a.y2 > b.y
        if abs(a.y2 - b.y) < tol or abs(a.y - b.y2) < tol:
            return a.x < b.x2 and a.x2 > b.x
        return False

    def _subtract(self, free: List[Rect], placed: Rect) -> List[Rect]:
        """Subtract placed from each free rect, splitting into up to 4 remainders."""
        out: List[Rect] = []
        for f in free:
            # No overlap → unchanged
            if (f.x2 <= placed.x or f.x >= placed.x2 or
                    f.y2 <= placed.y or f.y >= placed.y2):
                out.append(f)
                continue
            # Left strip
            if f.x < placed.x - 0.01:
                out.append(Rect(f.x, f.y, placed.x - f.x, f.height))
            # Right strip
            if f.x2 > placed.x2 + 0.01:
                out.append(Rect(placed.x2, f.y, f.x2 - placed.x2, f.height))
            # Bottom strip (within placed's x range)
            x_lo = max(f.x, placed.x)
            x_hi = min(f.x2, placed.x2)
            if f.y < placed.y - 0.01 and x_hi > x_lo + 0.01:
                out.append(Rect(x_lo, f.y, x_hi - x_lo, placed.y - f.y))
            # Top strip
            if f.y2 > placed.y2 + 0.01 and x_hi > x_lo + 0.01:
                out.append(Rect(x_lo, placed.y2, x_hi - x_lo, f.y2 - placed.y2))
        # Drop slivers smaller than MIN_ROOM_DIM in either dimension
        return [r for r in out if r.width >= self.MIN_ROOM_DIM
                and r.height >= self.MIN_ROOM_DIM]


# =============================================================================
# WALL GENERATION (envelope-based, like coordinate_solver's new path)
# =============================================================================

def _generate_walls(placed: Dict[str, Rect], envelope: Rect,
                    entry_edge: str) -> List[WallCoordinate]:
    """Generate exterior walls along envelope perimeter + interior walls
    between adjacent rooms."""
    walls: List[WallCoordinate] = []

    # Exterior: 4 walls along envelope perimeter
    # Entry door on entry edge
    half_door = 1.5
    edge_perimeter = [
        ("south", Point(envelope.x, envelope.y), Point(envelope.x2, envelope.y)),
        ("east", Point(envelope.x2, envelope.y), Point(envelope.x2, envelope.y2)),
        ("north", Point(envelope.x2, envelope.y2), Point(envelope.x, envelope.y2)),
        ("west", Point(envelope.x, envelope.y2), Point(envelope.x, envelope.y)),
    ]
    entry_rect = placed.get("entry")
    for i, (edge, start, end) in enumerate(edge_perimeter):
        wall = WallCoordinate(
            wall_id=f"ext_{edge}",
            start=start, end=end,
            wall_type=WallType.EXTERIOR,
            room1="exterior", room2="exterior",
        )
        # Attach entry door if this is the entry edge
        if entry_rect is not None and edge == entry_edge:
            if edge == "south":
                cx = entry_rect.x + entry_rect.width / 2
                wall.openings.append((Point(cx - half_door, envelope.y),
                                       Point(cx + half_door, envelope.y),
                                       OpeningType.DOOR))
            elif edge == "north":
                cx = entry_rect.x + entry_rect.width / 2
                wall.openings.append((Point(cx - half_door, envelope.y2),
                                       Point(cx + half_door, envelope.y2),
                                       OpeningType.DOOR))
            elif edge == "west":
                cy = entry_rect.y + entry_rect.height / 2
                wall.openings.append((Point(envelope.x, cy - half_door),
                                       Point(envelope.x, cy + half_door),
                                       OpeningType.DOOR))
            else:
                cy = entry_rect.y + entry_rect.height / 2
                wall.openings.append((Point(envelope.x2, cy - half_door),
                                       Point(envelope.x2, cy + half_door),
                                       OpeningType.DOOR))
        walls.append(wall)

    # Interior: for each room edge, generate walls covering the FULL edge —
    # either as shared walls with neighbors or as walls facing empty interior
    # space (so every room is closed, even with gaps in the layout).
    walls.extend(_generate_interior_walls(placed, envelope))
    return walls


def _generate_interior_walls(placed: Dict[str, Rect],
                             envelope: Rect) -> List[WallCoordinate]:
    """For each room edge that's NOT on the envelope perimeter, ensure it has
    walls covering its full length: shared walls where neighbors meet, plus
    walls where the edge faces empty interior space."""
    tol = 0.5
    walls: List[WallCoordinate] = []
    seen_segments: Set[Tuple[float, float, float, float]] = set()

    def add_wall(start: Point, end: Point, room1: str, room2: str, is_wet: bool = False):
        # Canonical key (lower-coord endpoint first) to dedupe
        if (start.x, start.y) < (end.x, end.y):
            key = (round(start.x, 1), round(start.y, 1), round(end.x, 1), round(end.y, 1))
        else:
            key = (round(end.x, 1), round(end.y, 1), round(start.x, 1), round(start.y, 1))
        if key in seen_segments:
            return
        seen_segments.add(key)
        wt = WallType.WET if is_wet else WallType.FULL
        walls.append(WallCoordinate(
            wall_id=f"int_{room1}__{room2}",
            start=start, end=end, wall_type=wt,
            room1=room1, room2=room2,
        ))

    def on_envelope(coord: float, axis: str) -> bool:
        if axis == "x":
            return abs(coord - envelope.x) < tol or abs(coord - envelope.x2) < tol
        return abs(coord - envelope.y) < tol or abs(coord - envelope.y2) < tol

    def subtract_intervals(start: float, end: float,
                            covered: List[Tuple[float, float, str]]) -> List[Tuple[float, float, str]]:
        """Given an interval [start, end] and a list of (a, b, neighbor_id)
        covered sub-intervals, return list of (a, b, neighbor_id_or_'exterior')
        sub-intervals tiling [start, end]."""
        # Sort by start
        covered = sorted(covered, key=lambda c: c[0])
        result: List[Tuple[float, float, str]] = []
        cursor = start
        for a, b, who in covered:
            if a > cursor + tol:
                result.append((cursor, a, "exterior"))  # uncovered gap
            if b > cursor + tol:
                result.append((max(cursor, a), b, who))
                cursor = b
        if cursor < end - tol:
            result.append((cursor, end, "exterior"))
        # Merge consecutive same-neighbor segments (rare but cleaner)
        merged: List[Tuple[float, float, str]] = []
        for seg in result:
            if merged and merged[-1][2] == seg[2] and abs(merged[-1][1] - seg[0]) < tol:
                merged[-1] = (merged[-1][0], seg[1], seg[2])
            else:
                merged.append(seg)
        return merged

    for room_id, rect in placed.items():
        # 4 edges: south (y=rect.y), north (y=rect.y2), west (x=rect.x), east (x=rect.x2)
        # For each edge, if it's on envelope perimeter skip (exterior covers it).
        # Otherwise compute neighbor coverage and emit walls for each segment.

        # SOUTH edge: y = rect.y, x from rect.x to rect.x2
        if not on_envelope(rect.y, "y"):
            covered = []
            for other_id, other in placed.items():
                if other_id == room_id: continue
                if abs(other.y2 - rect.y) < tol:  # other touches our south
                    a = max(rect.x, other.x)
                    b = min(rect.x2, other.x2)
                    if b > a + tol:
                        covered.append((a, b, other_id))
            for a, b, who in subtract_intervals(rect.x, rect.x2, covered):
                add_wall(Point(a, rect.y), Point(b, rect.y), room_id, who)

        # NORTH edge: y = rect.y2
        if not on_envelope(rect.y2, "y"):
            covered = []
            for other_id, other in placed.items():
                if other_id == room_id: continue
                if abs(other.y - rect.y2) < tol:
                    a = max(rect.x, other.x)
                    b = min(rect.x2, other.x2)
                    if b > a + tol:
                        covered.append((a, b, other_id))
            for a, b, who in subtract_intervals(rect.x, rect.x2, covered):
                add_wall(Point(a, rect.y2), Point(b, rect.y2), room_id, who)

        # WEST edge: x = rect.x
        if not on_envelope(rect.x, "x"):
            covered = []
            for other_id, other in placed.items():
                if other_id == room_id: continue
                if abs(other.x2 - rect.x) < tol:
                    a = max(rect.y, other.y)
                    b = min(rect.y2, other.y2)
                    if b > a + tol:
                        covered.append((a, b, other_id))
            for a, b, who in subtract_intervals(rect.y, rect.y2, covered):
                add_wall(Point(rect.x, a), Point(rect.x, b), room_id, who)

        # EAST edge: x = rect.x2
        if not on_envelope(rect.x2, "x"):
            covered = []
            for other_id, other in placed.items():
                if other_id == room_id: continue
                if abs(other.x - rect.x2) < tol:
                    a = max(rect.y, other.y)
                    b = min(rect.y2, other.y2)
                    if b > a + tol:
                        covered.append((a, b, other_id))
            for a, b, who in subtract_intervals(rect.y, rect.y2, covered):
                add_wall(Point(rect.x2, a), Point(rect.x2, b), room_id, who)

    return walls


def _shared_edge(a: Rect, b: Rect, tol: float) -> Optional[Tuple[Point, Point, bool]]:
    """Return the shared edge between a and b, or None if not adjacent."""
    # Vertical shared edge (a.x2 == b.x or a.x == b.x2)
    if abs(a.x2 - b.x) < tol:
        y1 = max(a.y, b.y)
        y2 = min(a.y2, b.y2)
        if y2 > y1 + tol:
            return Point(a.x2, y1), Point(a.x2, y2), False
    if abs(a.x - b.x2) < tol:
        y1 = max(a.y, b.y)
        y2 = min(a.y2, b.y2)
        if y2 > y1 + tol:
            return Point(a.x, y1), Point(a.x, y2), False
    # Horizontal shared edge
    if abs(a.y2 - b.y) < tol:
        x1 = max(a.x, b.x)
        x2 = min(a.x2, b.x2)
        if x2 > x1 + tol:
            return Point(x1, a.y2), Point(x2, a.y2), False
    if abs(a.y - b.y2) < tol:
        x1 = max(a.x, b.x)
        x2 = min(a.x2, b.x2)
        if x2 > x1 + tol:
            return Point(x1, a.y), Point(x2, a.y), False
    return None


# =============================================================================
# PUBLIC ENTRY POINT
# =============================================================================

def solve_layout_subdivision(graph: SpatialGraph, width: float, depth: float,
                             entry_edge: str = "south") -> PlacedLayout:
    """Convenience function returning a PlacedLayout (compatible with downstream)."""
    envelope = Rect(0, 0, width, depth)
    solver = SubdivisionSolver(graph, envelope, entry_edge)
    result = solver.solve()

    placed_rooms = {rid: PlacedRoom(rid, rect) for rid, rect in result.placed.items()}
    walls = _generate_walls(result.placed, envelope, entry_edge)
    _add_egress_doors(walls, result.placed, envelope, graph)

    return PlacedLayout(
        rooms=placed_rooms,
        walls=walls,
        building_bounds=envelope,
        is_complete=result.success,
        unplaced_rooms=result.unplaced,
        score=1.0 if result.success else 0.5,
    )


PASS_THROUGH_TYPES = {"entry", "hallway", "foyer", "mudroom",
                      "living", "great_room", "dining", "kitchen"}


def _can_pass_through(room_id: str, graph: SpatialGraph) -> bool:
    """True if this room can be a routing waypoint (not just a destination).
    Bedrooms/bathrooms/closets are destinations; you can't walk through them."""
    if room_id == "entry":
        return True
    room = graph.rooms.get(room_id)
    rt = room.room_type if room else room_id
    base = rt
    # Strip trailing _N: "bedroom_2" -> "bedroom"
    if rt not in PASS_THROUGH_TYPES and rt not in (PRIVATE_ZONE | SERVICE_ZONE):
        base = room_id.split("_")[0]
    return base in PASS_THROUGH_TYPES


def _add_egress_doors(walls: List[WallCoordinate],
                      placed: Dict[str, Rect],
                      envelope: Rect,
                      graph: SpatialGraph) -> None:
    """Mutate walls to add DOOR openings forming a spanning tree from entry.
    Constrained BFS: routes through public/circulation rooms only — never
    crosses private rooms (bedrooms, baths, closets). If a room can't be
    reached under that constraint, prints a diagnostic — that's a layout
    problem the hallway needs to solve."""
    from collections import defaultdict, deque

    if "entry" not in placed:
        return

    # Build adjacency: room_id -> [(neighbor_id, wall_index)]
    adjacency: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for i, w in enumerate(walls):
        if w.wall_type == WallType.EXTERIOR:
            continue
        a, b = w.room1, w.room2
        if a in placed and b in placed and a != b:
            adjacency[a].append((b, i))
            adjacency[b].append((a, i))

    # PASS 1 — En-suite pattern: bathrooms/closets connect to their PARENT
    # bedroom (the adjacent bedroom), not to a corridor. Place these doors
    # first so the constrained BFS treats parent bedrooms as already linked
    # to their en-suite destinations.
    tree_edges: List[Tuple[str, str, int]] = []
    visited = {"entry"}
    paired = set()  # room ids already connected via en-suite

    # Must mirror the bundle list in solve() — keep these in sync.
    suite_pairs = [
        # Bedroom suites
        ("primary_bath", "primary_bedroom"),
        ("primary_closet", "primary_bedroom"),
        ("closet_2", "bedroom_2"),
        ("closet_3", "bedroom_3"),
        ("closet_4", "bedroom_4"),
        # Service area
        ("mudroom", "garage"),
        ("laundry", "garage"),
        # Public area
        ("entry", "living"),
        ("dining", "kitchen"),
    ]
    for child, parent in suite_pairs:
        if child not in placed or parent not in placed:
            continue
        # Find wall between them
        for nb_id, wall_idx in adjacency.get(child, []):
            if nb_id == parent:
                tree_edges.append((parent, child, wall_idx))
                paired.add(child)
                break

    # PASS 2 — Constrained BFS from entry. Only expand FROM pass-through rooms.
    queue = deque(["entry"])

    def neighbor_priority(nb_id: str) -> int:
        if nb_id == "hallway" or nb_id.startswith("hallway_"):
            return 0
        return 1

    while queue:
        current = queue.popleft()
        # Only continue routing through pass-through rooms (public/circulation).
        # Private rooms (bedrooms etc.) get a door but don't extend the path —
        # except via en-suite paired children, which were placed in Pass 1.
        if not _can_pass_through(current, graph):
            # If this is a parent bedroom whose en-suite children we paired,
            # mark them as visited too (they're reachable via the parent).
            for child, parent in suite_pairs:
                if parent == current and child in placed:
                    visited.add(child)
            continue
        for neighbor, wall_idx in sorted(adjacency[current],
                                          key=lambda nb: neighbor_priority(nb[0])):
            if neighbor not in visited:
                visited.add(neighbor)
                tree_edges.append((current, neighbor, wall_idx))
                queue.append(neighbor)
    # After BFS, mark en-suite children visited if their parent is reachable
    for child, parent in suite_pairs:
        if parent in visited and child in placed:
            visited.add(child)

    # Diagnostic: which rooms can't be reached under the privacy constraint?
    unreachable = [r for r in placed if r != "entry" and r not in visited]
    if unreachable:
        print(f"[Egress] WARNING: cannot reach without crossing private rooms: {unreachable}")
        print(f"[Egress]   Need hallway extension to bridge these.")

    # Add one door opening per tree edge, centered on the shared wall
    door_width = 0.9 / 0.3048  # 900mm in feet
    for parent, child, wall_idx in tree_edges:
        wall = walls[wall_idx]
        seg_start, seg_end = wall.start, wall.end
        seg_len = ((seg_end.x - seg_start.x) ** 2 +
                   (seg_end.y - seg_start.y) ** 2) ** 0.5
        if seg_len < door_width * 1.2:
            continue
        cx = (seg_start.x + seg_end.x) / 2
        cy = (seg_start.y + seg_end.y) / 2
        dx = (seg_end.x - seg_start.x) / seg_len
        dy = (seg_end.y - seg_start.y) / seg_len
        d_start = Point(cx - dx * door_width / 2, cy - dy * door_width / 2)
        d_end = Point(cx + dx * door_width / 2, cy + dy * door_width / 2)
        wall.openings.append((d_start, d_end, OpeningType.DOOR))
