"""
smoke_test.py - End-to-end pipeline test for Legible Studio.

Exercises (synthetic answers) -> layout generation -> validators -> drawing set.
Times each stage. Reports what works, what breaks.

Does NOT test: Vulkan rendering, AI render hero shots. Verifies kernel DLL
exists and can be loaded.
"""
import sys
import os
import time
import json
import traceback
from pathlib import Path

# Force UTF-8 stdout/stderr regardless of the Windows console default (cp1252).
# Several scripts in the pipeline print emojis (✅, ⚠️) that crash on cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO_ROOT = Path(__file__).parent.resolve()
QBD = REPO_ROOT / "ArchEngine_kernel" / "qbd"
ENHANCER = REPO_ROOT / "ArchEngine_kernel" / "enhancer"
CAD = REPO_ROOT / "ArchEngine_CAD"
SCRIPTS = REPO_ROOT / "ArchEngine_kernel" / "scripts"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(QBD))
sys.path.insert(0, str(CAD))
sys.path.insert(0, str(REPO_ROOT))

OUTPUT_DIR = REPO_ROOT / "smoke_test_output"
OUTPUT_DIR.mkdir(exist_ok=True)

results = []


def stage(name):
    def decorator(fn):
        def wrapped(*args, **kwargs):
            print(f"\n=== {name} ===")
            t0 = time.perf_counter()
            try:
                out = fn(*args, **kwargs)
                dt = time.perf_counter() - t0
                print(f"OK ({dt*1000:.1f}ms)")
                results.append((name, "OK", dt, None))
                return out
            except Exception as e:
                dt = time.perf_counter() - t0
                print(f"FAIL ({dt*1000:.1f}ms): {type(e).__name__}: {e}")
                tb = traceback.format_exc()
                print(tb)
                results.append((name, "FAIL", dt, f"{type(e).__name__}: {e}"))
                return None
        return wrapped
    return decorator


@stage("1. Synthesize Ontario residential answers")
def synthesize_answers():
    if "--small" in sys.argv:
        # Tiny program for fast iteration: 1-bed, 1-bath, ~800 sqft.
        # Use this for solver perf work where the cached run isn't applicable.
        return {
            "bedrooms": 1,
            "bathrooms": 1,
            "sqft": 800,
            "garage": "none",
            "stories": 1,
            "style": "ranch",
        }
    return {
        "bedrooms": 3,
        "bathrooms": 2,
        "sqft": 1800,
        "garage": "double",
        "stories": 1,
        "style": "ranch",
    }


@stage("2. QBD answers -> building JSON (qbd_layout_generator)")
def generate_layout(answers):
    from qbd_layout_generator import generate_floor_plan_from_qbd, OutputFormat

    def _do_solve():
        return generate_floor_plan_from_qbd(
            answers,
            width=None,
            depth=None,
            output_format=OutputFormat.ARCHENGINE,
        )

    if "--profile-solver" in sys.argv:
        import cProfile, pstats, io
        prof = cProfile.Profile()
        prof.enable()
        result = _do_solve()
        prof.disable()
        prof_path = OUTPUT_DIR / "solver_profile.prof"
        prof.dump_stats(str(prof_path))
        # Top 25 by cumulative time
        s = io.StringIO()
        ps = pstats.Stats(prof, stream=s).sort_stats("cumulative")
        ps.print_stats(25)
        print(f"   --- top 25 by cumulative ---")
        for line in s.getvalue().splitlines():
            print(f"   {line}")
        # Top 15 by total (own time)
        s = io.StringIO()
        ps = pstats.Stats(prof, stream=s).sort_stats("tottime")
        ps.print_stats(15)
        print(f"   --- top 15 by tottime ---")
        for line in s.getvalue().splitlines():
            print(f"   {line}")
        print(f"   Profile dumped: {prof_path}")
    else:
        result = _do_solve()

    print(f"   Building keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
    if isinstance(result, dict):
        for key in ["walls_batch", "doors", "windows", "rooms", "floors_batch"]:
            v = result.get(key)
            if v is not None:
                print(f"   {key}: {len(v) if hasattr(v, '__len__') else v}")
    # Persist
    out_file = OUTPUT_DIR / "building.json"
    out_file.write_text(json.dumps(result, indent=2, default=str))
    print(f"   Wrote: {out_file}")
    return result


@stage("3a. Code validation (CodeStudio)")
def validate_code(building):
    sys.path.insert(0, str(CAD))
    from legible_studios.studios.code_studio import CodeStudio
    code = CodeStudio()
    result = code.analyze(building, intensity=0.7)
    print(f"   Score: {result.score:.2f}")
    print(f"   Critical violations: {result.get_critical_count()}")
    print(f"   Warnings: {result.get_warning_count()}")
    print(f"   Metrics: {result.metrics}")
    if result.violations:
        for v in result.violations[:5]:
            print(f"   - [{v.priority.value}] {v.message}")
    return result


@stage("3b. Cost validation (CostStudio)")
def validate_cost(building):
    from legible_studios.studios.cost_studio import CostStudio
    cost = CostStudio()
    result = cost.analyze(building, intensity=0.5)
    m = result.metrics
    print(f"   Score: {result.score:.2f}")
    print(f"   Estimated cost: ${m.get('estimated_cost_cad', 0):,.0f} CAD")
    print(f"   Cost per m2:    ${m.get('cost_per_m2', 0):,.0f}")
    print(f"   Cost per sqft:  ${m.get('cost_per_sqft', 0):,.0f}")
    print(f"   Floor area:     {m.get('total_floor_area_m2', 0)} m2 ({m.get('total_floor_area_sqft', 0)} sqft)")
    print(f"   Wall area:      {m.get('total_wall_area_m2', 0)} m2  Doors: {m.get('door_count')}  Windows: {m.get('window_count')}")
    if result.violations:
        for v in result.violations[:5]:
            print(f"   - [{v.priority.value}] {v.message}")
    return result


@stage("4. Permit drawing set generation")
def generate_drawings(building):
    from permit_drawing_set import create_permit_drawing_set
    building_file = OUTPUT_DIR / "building.json"
    drawings_dir = OUTPUT_DIR / "drawings"
    drawings_dir.mkdir(exist_ok=True)
    return create_permit_drawing_set(
        building_json_path=building_file,
        output_dir=drawings_dir,
        lot_width_ft=60.0,
        lot_depth_ft=120.0,
    )


@stage("5. DB save (SQLite via SQLAlchemy)")
def db_save(building):
    """Self-contained DB save — no WAL, no engine.py event hooks."""
    db_file = OUTPUT_DIR / "smoke_test.db"
    if db_file.exists():
        db_file.unlink()

    print(f"   Importing sqlalchemy...", flush=True)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    print(f"   Importing models...", flush=True)
    from database.models.base import Base
    from database.models.workspace import Workspace
    from database.models.building import Wall, Door, Window, Room
    from database.repository.project import ProjectRepository

    print(f"   Creating engine: sqlite:///{db_file}", flush=True)
    engine = create_engine(f"sqlite:///{db_file}", echo=False)

    print(f"   Creating tables...", flush=True)
    Base.metadata.create_all(bind=engine)

    print(f"   Opening session...", flush=True)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    try:
        workspace = Workspace(name="smoke_test")
        session.add(workspace)
        session.flush()
        ws_id = workspace.id

        building_for_save = dict(building)
        building_for_save["name"] = building.get("name") or f"smoke_{building.get('building_id', 'test')}"

        print(f"   Importing project...", flush=True)
        repo = ProjectRepository(session)
        project = repo.import_from_dict(building_for_save, ws_id)
        session.commit()

        wall_n = session.query(Wall).filter_by(project_id=project.id).count()
        print(f"   DB:           {db_file} ({db_file.stat().st_size//1024}KB)")
        print(f"   workspace_id: {ws_id}")
        print(f"   project_id:   {project.id}  ({project.name})")
        print(f"   walls saved:  {wall_n}")
        return {"db_file": str(db_file), "workspace_id": ws_id, "project_id": project.id}
    finally:
        session.close()
        engine.dispose()


@stage("6. DB load + roundtrip identity check")
def db_load(save_info):
    if not save_info:
        raise RuntimeError("save did not produce info")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models.building import Wall, Door, Window, Room
    from database.models.project import Project

    engine = create_engine(f"sqlite:///{save_info['db_file']}", echo=False)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    try:
        project = session.query(Project).filter_by(id=save_info["project_id"]).first()
        if not project:
            raise RuntimeError(f"project {save_info['project_id']!r} not found in DB")

        wall_count = session.query(Wall).filter_by(project_id=project.id).count()
        door_count = session.query(Door).filter_by(project_id=project.id).count()
        window_count = session.query(Window).filter_by(project_id=project.id).count()
        room_count = session.query(Room).filter_by(project_id=project.id).count()

        print(f"   Loaded project:  {project.name}  (id={project.id})")
        print(f"   walls:   {wall_count}")
        print(f"   doors:   {door_count}")
        print(f"   windows: {window_count}")
        print(f"   rooms:   {room_count}")

        # Sample one wall, one room — identity check
        first_wall = session.query(Wall).filter_by(project_id=project.id).order_by(Wall.index).first()
        first_room = session.query(Room).filter_by(project_id=project.id).first()
        if first_wall:
            print(f"   wall[0]: start=({first_wall.start_x:.0f},{first_wall.start_y:.0f},{first_wall.start_z:.0f}) "
                  f"end=({first_wall.end_x:.0f},{first_wall.end_y:.0f},{first_wall.end_z:.0f}) "
                  f"category={first_wall.category} length={first_wall.length:.0f}mm")
        if first_room:
            print(f"   room[0]: key={first_room.room_key} type={first_room.room_type} area={first_room.area:.0f}")
        return {"wall_count": wall_count, "room_count": room_count}
    finally:
        session.close()
        engine.dispose()


@stage("7. Vulkan kernel DLL availability")
def check_vulkan_dll():
    candidates = [
        REPO_ROOT / "ArchEngine_kernel" / "build" / "Release" / "ArchEngineLib.dll",
        REPO_ROOT / "ArchEngine_kernel" / "build" / "Debug" / "ArchEngineLib.dll",
        REPO_ROOT / "ArchEngine_kernel" / "build" / "ArchEngineLib.dll",
        CAD / "viewport" / "archengine_viewport.dll",
    ]
    for p in candidates:
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f"   Found: {p} ({size_mb:.1f}MB)")
            try:
                import ctypes
                lib = ctypes.CDLL(str(p))
                exports = [name for name in ["arch_init", "arch_load_json", "arch_render_frame"]
                           if hasattr(lib, name)]
                print(f"   Loadable. Exports present: {exports}")
                return p
            except Exception as e:
                print(f"   Found but not loadable: {e}")
    raise FileNotFoundError(f"No DLL found at any candidate path: {candidates}")


# Run
print("=" * 70)
print(f"LEGIBLE STUDIO END-TO-END SMOKE TEST")
print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Repo:    {REPO_ROOT}")
print("=" * 70)

t_total_start = time.perf_counter()

USE_CACHE = "--cached" in sys.argv
cache_file = OUTPUT_DIR / "building.json"

answers = synthesize_answers()
if USE_CACHE and cache_file.exists():
    print(f"\n=== 2. (CACHED) loading {cache_file} ===")
    building = json.loads(cache_file.read_text())
    print(f"OK ({cache_file.stat().st_size//1024}KB)")
    results.append(("2. (CACHED) load building", "OK", 0, None))
else:
    building = generate_layout(answers) if answers else None

if building:
    validate_code(building)
    validate_cost(building)
    generate_drawings(building)
    save_info = db_save(building)
    db_load(save_info)

check_vulkan_dll()

t_total = time.perf_counter() - t_total_start

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total wall time: {t_total*1000:.0f}ms ({t_total:.1f}s, {t_total/60:.2f}min)")
print(f"5-min target:    {'PASS' if t_total < 300 else 'FAIL'}")
print()
ok_count = sum(1 for r in results if r[1] == "OK")
print(f"Passed: {ok_count}/{len(results)}")
print()
print("Stage results:")
for name, status, dt, err in results:
    sym = "[OK]  " if status == "OK" else "[FAIL]"
    print(f"  {sym} {name}  ({dt*1000:.0f}ms)")
    if err:
        print(f"         -> {err[:160]}")
