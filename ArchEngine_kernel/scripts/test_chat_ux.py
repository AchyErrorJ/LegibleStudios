#!/usr/bin/env python3
"""Test LegiQBD Chat UX with Reality Layers."""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from legiqbd.api import LegiQBDAPI


def test_chat_ux():
    """Test the chat UX functionality."""

    print("=" * 70)
    print("LEGIQBD CHAT UX TEST")
    print("=" * 70)

    # Create API instance
    api = LegiQBDAPI()

    # Test 1: Get initial state
    print("\n[1] INITIAL STATE")
    print("-" * 70)
    initial = api.get_initial_state()
    print(f"Greeting: {initial['greeting']}")
    print(f"Session ID: {initial['session_id']}")
    print(f"Questions: {len(initial['questions'])} starter questions")
    session_id = initial['session_id']

    # Test 2: Simple chat
    print("\n[2] SIMPLE CHAT")
    print("-" * 70)
    print("User: I need a 3 bedroom 2 bath house")
    response = api.chat('I need a 3 bedroom 2 bath house', session_id=session_id)
    print(f"Response: {response['response'][:150]}...")
    print(f"  Rooms: {response['room_count']}")
    print(f"  Is Solvable: {response['is_solvable']}")
    print(f"  Is Solved: {response['is_solved']}")
    print(f"  Phase: {response['phase']}")

    # Test 3: Reality analysis
    print("\n[3] REALITY ANALYSIS")
    print("-" * 70)
    if response['room_count'] > 0:
        reality = api.analyze_reality(session_id=session_id)
        print(f"Overall Score: {reality['overall_score']}")
        print(f"  Thermal Load: {reality['environment']['thermal_load_kw']} kW")
        print(f"  Cooling Load: {reality['environment']['cooling_load_kw']} kW")
        print(f"  Total Cost: ${reality['materiality']['total_cost']:,.0f}")
        print(f"  Cost per sqft: ${reality['materiality']['cost_per_sqft']:.2f}")
        print(f"  Construction Weeks: {reality['materiality']['construction_weeks']}")
        print(f"  Wayfinding Score: {reality['perception']['wayfinding_score']}")
        print(f"  Overall Experience: {reality['perception']['overall_experience']}")
    else:
        print("No rooms to analyze")
        return False

    # Test 4: Chat with reality included
    print("\n[4] CHAT WITH REALITY INCLUDED")
    print("-" * 70)
    print("User: Add a garage (include_reality=True)")
    response2 = api.chat('Add a garage', session_id=session_id, include_reality=True)
    print(f"Response: {response2['response'][:100]}...")
    if response2.get('reality'):
        print(f"Reality included in response!")
        reality2 = response2['reality']
        print(f"  Overall Score: {reality2['overall_score']}")
        print(f"  Total Cost: ${reality2['materiality']['total_cost']:,.0f}")

    # Test 5: Individual layer analysis
    print("\n[5] INDIVIDUAL LAYER ANALYSIS")
    print("-" * 70)
    env = api.analyze_environment(session_id=session_id)
    print(f"Environment Layer:")
    print(f"  Thermal Load: {env['thermal_load_kw']} kW")
    print(f"  Passive Strategies: {', '.join(env['passive_strategies'])}")

    mat = api.analyze_materiality(session_id=session_id)
    print(f"Materiality Layer:")
    print(f"  Total Cost: ${mat['total_cost']:,.0f}")
    print(f"  Budget Status: {mat['budget_status']}")

    perc = api.analyze_perception(session_id=session_id)
    print(f"Perception Layer:")
    print(f"  Wayfinding Score: {perc['wayfinding_score']}")
    print(f"  Overall Experience: {perc['overall_experience']}")

    # Test 6: Design state
    print("\n[6] DESIGN STATE")
    print("-" * 70)
    design = api.get_design_state(session_id=session_id)
    print(f"Rooms: {design['room_count']}")
    print(f"Adjacencies: {design['adjacencies']}")
    print(f"Is Solvable: {design['is_solvable']}")
    print(f"Is Solved: {design['is_solved']}")
    print(f"Phase: {design['phase']}")
    if design['layout']:
        print(f"Score: {design['layout'].get('score', 'N/A')}")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED!")
    print("=" * 70)

    return True


if __name__ == "__main__":
    try:
        success = test_chat_ux()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
