"""Test QBD Reality Layers - Full Pipeline Test.

Tests the complete QBD Algebra with all three reality layers:
- Environment (Physics): Solar, thermal, acoustics
- Materiality (Economics): Cost, construction, materials
- Perception (Psychology): Wayfinding, comfort, delight

Usage:
    python test_qbd_reality_layers.py
"""

import sys
import json
from qbd import (
    QBDState,
    add_room,
    set_adjacency,
    set_constraint,
    set_site,
    set_window_area,
    set_insulation,
    set_construction_system,
    set_quality_level,
    set_budget,
    set_finishes,
    set_privacy_level,
    add_biophilic_element,
)
from qbd.layers import EnvironmentLayer, MaterialityLayer, PerceptionLayer
from qbd.layers.materiality import ConstructionSystem, QualityLevel, ConstructionSystemAnalysis


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_basic_pipeline():
    """Test 1: Basic QBD pipeline with fragments."""
    print_section("TEST 1: Basic QBD Pipeline")

    # Create state
    state = QBDState()
    print(f"Initial lifecycle: {state.lifecycle.value}")

    # Apply fragments
    frag_living = add_room("Living Room", "living")
    state.apply_fragment(frag_living)
    living_id = frag_living.data.get("_generated_id")
    print(f"Added living room: {living_id}")

    frag_kitchen = add_room("Kitchen", "kitchen")
    state.apply_fragment(frag_kitchen)
    kitchen_id = frag_kitchen.data.get("_generated_id")
    print(f"Added kitchen: {kitchen_id}")

    frag_bedroom = add_room("Primary Bedroom", "primary_bedroom")
    state.apply_fragment(frag_bedroom)
    bedroom_id = frag_bedroom.data.get("_generated_id")
    print(f"Added bedroom: {bedroom_id}")

    # Set adjacency
    result = state.apply_fragment(set_adjacency(living_id, kitchen_id, "required", "open"))
    print(f"Set adjacency: living <-> kitchen")

    # Set site
    site_data = {
        "width": 15000,  # 15m
        "depth": 12000,  # 12m
        "latitude": 40.7,
        "climate_zone": "4A",
        "orientation": {"front_faces": "S"}
    }
    result = state.apply_fragment(set_site(site_data))
    print(f"Set site: 15m x 12m, climate zone 4A")

    # Set constraints
    result = state.apply_fragment(set_constraint("footprint_max", 150))
    print(f"Set footprint: 150 m2")

    print(f"\nFinal lifecycle: {state.lifecycle.value}")
    print(f"Rooms: {len(state.rooms)}")
    print(f"Adjacencies: {len(state.adjacencies)}")

    return state, living_id, kitchen_id, bedroom_id


def test_environment_layer(state):
    """Test 2: Environment Layer (Physics)."""
    print_section("TEST 2: Environment Layer (Physics)")

    # Get site data
    site_data = state.site
    print(f"Site latitude: {site_data.get('latitude')}")
    print(f"Climate zone: {site_data.get('climate_zone')}")

    # Initialize environment layer
    env = EnvironmentLayer(site_data)

    # Analyze
    result = env.analyze(
        rooms=state.rooms,
        adjacencies=state.adjacencies,
        separations=state.separations,
        building_layout={}  # Empty for now
    )

    # Display results
    print(f"\n--- Solar/Daylight Analysis ---")
    for room_id, daylight in result.solar.items():
        room = next((r for r in state.rooms if r.get("id") == room_id), None)
        room_name = room.get("name") if room else room_id
        print(f"{room_name}:")
        print(f"  Daylight factor: {daylight.daylight_factor:.2f}")
        print(f"  Direct sun (winter): {daylight.direct_hours.get('winter', 0)}h")
        print(f"  Glare potential: {daylight.glare_potential}")

    print(f"\n--- Thermal Analysis ---")
    thermal = result.thermal
    print(f"Total heating load: {thermal.total_heating_load:.1f} kW")
    print(f"Total cooling load: {thermal.total_cooling_load:.1f} kW")
    print(f"Peak heating month: {thermal.peak_heating_month}")
    print(f"Passive strategies: {', '.join(thermal.passive_strategy_potential)}")

    print(f"\n--- Acoustic Analysis ---")
    for room_id, acoustic in result.acoustic.items():
        room = next((r for r in state.rooms if r.get("id") == room_id), None)
        room_name = room.get("name") if room else room_id
        print(f"{room_name}:")
        print(f"  STC rating: {acoustic.stc_rating}")
        print(f"  Privacy: {acoustic.privacy_level}")
        print(f"  RT60: {acoustic.reverberation_time:.2f}s")

    if result.critical_issues:
        print(f"\n--- Physics Violations ---")
        for issue in result.critical_issues:
            print(f"  [!] {issue}")
    else:
        print(f"\n[OK] No physics violations")

    return result


def test_materiality_layer(state):
    """Test 3: Materiality Layer (Economics)."""
    print_section("TEST 3: Materiality Layer (Economics)")

    # Initialize materiality layer
    mat = MaterialityLayer(region="northeast")

    # Set construction system and quality
    construction_system = ConstructionSystem.WOOD_LIGHT_FRAME
    quality_level = QualityLevel.STANDARD

    # Analyze
    result = mat.analyze(
        rooms=state.rooms,
        site=state.site,
        construction_system=construction_system,
        quality_level=quality_level
    )

    # Display results
    print(f"Construction system: {construction_system.value}")
    print(f"Quality level: {quality_level.value}")

    cost = result.cost
    print(f"\n--- Cost Analysis ---")
    print(f"Total cost: ${cost.total_cost:,.0f}")
    print(f"Cost per sqft: ${cost.cost_per_sqft:.2f}")
    print(f"Budget status: {cost.budget_status}")
    print(f"Contingency: {int(cost.contingency_recommendation * 100)}%")

    print(f"\n--- Cost Breakdown ---")
    for breakdown in cost.breakdown:
        print(f"{breakdown.category}:")
        print(f"  Materials: ${breakdown.materials:,.0f}")
        print(f"  Labor: ${breakdown.labor:,.0f}")
        print(f"  Total: ${breakdown.total:,.0f}")

    complexity = result.complexity
    print(f"\n--- Construction Complexity ---")
    print(f"Complexity score: {complexity.complexity_score}")
    print(f"Crew size: {complexity.crew_size} people")
    print(f"Duration: {complexity.duration_weeks} weeks")
    print(f"Special equipment: {', '.join(complexity.special_equipment) or 'None'}")
    print(f"Skilled trades: {', '.join(complexity.skilled_trades_needed)}")

    if complexity.risk_factors:
        print(f"\nRisk factors:")
        for risk in complexity.risk_factors:
            print(f"  [!] {risk}")
    else:
        print(f"\n[OK] No significant risks")

    print(f"\n--- Sustainability ---")
    print(f"Embodied carbon: {result.carbon_footprint:,.0f} kg CO2e")
    print(f"Lifecycle cost (30yr): ${result.lifecycle_cost_30yr:,.0f}")

    return result


def test_perception_layer(state, env_result):
    """Test 4: Perception Layer (Psychology)."""
    print_section("TEST 4: Perception Layer (Psychology)")

    # Initialize perception layer
    perc = PerceptionLayer()

    # Analyze
    result = perc.analyze(
        rooms=state.rooms,
        adjacencies=state.adjacencies,
        separations=state.separations,
        layout={},  # Empty for now
        environmental_result=env_result
    )

    # Display results
    wayfinding = result.wayfinding
    print(f"--- Wayfinding Analysis ---")
    print(f"Overall legibility: {wayfinding.overall_legibility:.2f}")
    print(f"Number of landmarks: {sum(1 for n in wayfinding.nodes if n.is_landmark)}")

    print(f"\nCritical paths:")
    for key, path in wayfinding.critical_paths.items():
        print(f"  {key}:")
        print(f"    Steps: {path.steps}")
        print(f"    Decision points: {path.decision_points}")
        print(f"    Has landmark: {path.has_landmark}")

    comfort = result.comfort
    print(f"\n--- Comfort Analysis ---")
    for room_id, comfort_result in comfort.items():
        room = next((r for r in state.rooms if r.get("id") == room_id), None)
        room_name = room.get("name") if room else room_id
        print(f"{room_name}:")
        print(f"  Overall comfort: {comfort_result.overall_comfort:.2f}")
        print(f"  Thermal: {comfort_result.thermal_comfort:.2f}")
        print(f"  Visual: {comfort_result.visual_comfort:.2f}")
        print(f"  Acoustic: {comfort_result.acoustic_comfort:.2f}")

    delight = result.delight
    print(f"\n--- Delight Analysis ---")
    for room_id, delight_result in delight.items():
        room = next((r for r in state.rooms if r.get("id") == room_id), None)
        room_name = room.get("name") if room else room_id
        print(f"{room_name}:")
        print(f"  Delight score: {delight_result.delight_score:.2f}")
        print(f"  Biophilia: {delight_result.biophilia_score:.2f}")
        print(f"  Prospect/refuge: {delight_result.prospect_refuge_score:.2f}")
        print(f"  Affect qualities: {[q.value for q in delight_result.affect_qualities]}")

    print(f"\n--- Overall Experience ---")
    print(f"Experience score: {result.overall_experience_score:.2f}")

    if result.critical_issues:
        print(f"\n--- Experience Issues ---")
        for issue in result.critical_issues:
            print(f"  [!] {issue}")
    else:
        print(f"\n[OK] No critical experience issues")

    if result.enhancement_opportunities:
        print(f"\nEnhancement opportunities:")
        for opp in result.enhancement_opportunities:
            print(f"  - {opp}")

    return result


def test_reality_layer_fragments():
    """Test 5: Reality layer fragment operations."""
    print_section("TEST 5: Reality Layer Fragments")

    state = QBDState()

    # Add a room
    frag_bedroom = add_room("Master Bedroom", "primary_bedroom")
    state.apply_fragment(frag_bedroom)
    room_id = frag_bedroom.data.get("_generated_id")
    print(f"Created room: {room_id}")

    # Environment fragments
    print("\n--- Environment Fragments ---")
    state.apply_fragment(set_window_area(room_id, 4.5))
    print(f"[OK] Set window area: 4.5 m2")

    state.apply_fragment(set_insulation(room_id, "passive_house"))
    print(f"[OK] Set insulation: passive_house")

    state.apply_fragment(set_finishes(room_id, {
        "floor": "hardwood",
        "walls": "painted",
        "ceiling": "acoustic"
    }))
    print(f"[OK] Set finishes: hardwood/painted/acoustic")

    # Materiality fragments
    print("\n--- Materiality Fragments ---")
    state.apply_fragment(set_construction_system("wood_advanced"))
    print(f"[OK] Set construction system: wood_advanced")

    state.apply_fragment(set_quality_level("premium"))
    print(f"[OK] Set quality level: premium")

    state.apply_fragment(set_budget("total", 500000))
    print(f"[OK] Set budget: $500,000")

    # Perception fragments
    print("\n--- Perception Fragments ---")
    state.apply_fragment(set_privacy_level(room_id, "intimate"))
    print(f"[OK] Set privacy level: intimate")

    state.apply_fragment(add_biophilic_element(room_id, "plants"))
    print(f"[OK] Added biophilic element: plants")

    # Show state
    print(f"\n--- State Summary ---")
    for room in state.rooms:
        print(f"\n{room.get('name')}:")
        if room.get("window_area"):
            print(f"  Window area: {room.get('window_area')} m2")
        if room.get("constraints", {}).get("insulation"):
            print(f"  Insulation: {room['constraints']['insulation']}")
        if room.get("finishes"):
            print(f"  Finishes: {room['finishes']}")


def run_all_tests():
    """Run all tests."""
    print("\n")
    print("=" * 70)
    print("QBD REALITY LAYERS - FULL PIPELINE TEST".center(70))
    print("=" * 70)

    try:
        # Test 1: Basic pipeline
        state, living_id, kitchen_id, bedroom_id = test_basic_pipeline()

        # Test 2: Environment layer
        env_result = test_environment_layer(state)

        # Test 3: Materiality layer
        mat_result = test_materiality_layer(state)

        # Test 4: Perception layer
        perc_result = test_perception_layer(state, env_result)

        # Test 5: Reality layer fragments
        test_reality_layer_fragments()

        # Summary
        print_section("SUMMARY")
        print("[OK] All tests passed!")
        print("\nThe QBD Algebra pipeline is working:")
        print("  1. Logic layer (state, fragments, validation)")
        print("  2. Environment layer (solar, thermal, acoustics)")
        print("  3. Materiality layer (cost, construction, materials)")
        print("  4. Perception layer (wayfinding, comfort, delight)")
        print("\nTotal Reality = Logic + Physics + Economics + Psychology")

        return True

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
