"""
Demo script for Legible Studios.

Shows how the constraint lens system interprets the same geometry
through different studios.
"""

import json
from legible_studios import (
    StudioManager, StudioLevel,
    ClimateStudio, StructuralStudio, CodeStudio,
    CostStudio, AcousticStudio
)


def create_sample_geometry():
    """Create sample building geometry for testing."""
    return {
        "rooms": [
            {
                "id": "living",
                "name": "Living Room",
                "type": "living",
                "area": 25.0,
                "width": 5.0,
                "length": 5.0,
                "center": (2500, 2500),
                "orientation": "south",
                "exterior": True,
            },
            {
                "id": "kitchen",
                "name": "Kitchen",
                "type": "kitchen",
                "area": 12.0,
                "width": 3.0,
                "length": 4.0,
                "center": (4500, 2500),
                "orientation": "east",
                "exterior": True,
            },
            {
                "id": "bed1",
                "name": "Master Bedroom",
                "type": "bedroom",
                "area": 16.0,
                "width": 4.0,
                "length": 4.0,
                "center": (2500, 4500),
                "orientation": "north",
                "exterior": True,
            },
        ],
        "walls": [
            {"id": "w1", "length": 5.0, "area": 13.5, "structural": True, "material": "drywall"},
            {"id": "w2", "length": 4.0, "area": 10.8, "structural": False, "material": "drywall"},
            {"id": "w3", "length": 8.0, "area": 21.6, "structural": True, "material": "drywall"},
        ],
        "openings": [
            {"id": "win1", "room_id": "living", "type": "window", "area": 3.0, "egress": False},
            {"id": "win2", "room_id": "bed1", "type": "window", "area": 1.5, "egress": True},
            {"id": "door1", "room_id": "living", "type": "door", "width": 900, "egress": True},
        ],
        "floors": [
            {"id": "f1", "area": 53.0, "center": (3500, 3500)},
        ],
    }


def demo_all_studios():
    """Run all studios on sample geometry."""
    print("=" * 60)
    print("Legible Studios Demo")
    print("=" * 60)

    geometry = create_sample_geometry()
    studios = {
        "Climate": ClimateStudio(),
        "Structural": StructuralStudio(),
        "Code": CodeStudio(),
        "Cost": CostStudio(),
        "Acoustic": AcousticStudio(),
    }

    for name, studio in studios.items():
        print(f"\n{'=' * 40}")
        print(f"{studio.name}")
        print(f"{studio.description}")
        print(f"{'=' * 40}")

        result = studio.analyze(geometry, intensity=0.7)

        print(f"\nScore: {result.score:.2f}")
        print(f"Metrics:")
        for key, value in result.metrics.items():
            print(f"  {key}: {value}")

        if result.violations:
            print(f"\nViolations:")
            for v in result.violations:
                print(f"  [{v.priority.value}] {v.message}")
                if v.suggestion:
                    print(f"    → {v.suggestion}")

        overlays = studio.get_visual_overlays(geometry, intensity=0.7)
        print(f"\nVisual Overlays: {len(overlays)}")
        for ov in overlays[:3]:  # Show first 3
            print(f"  - {ov['type']}: {ov.get('color', 'no color')}")


def demo_studio_manager():
    """Demo the studio manager transitions."""
    print("\n" + "=" * 60)
    print("Studio Manager Demo")
    print("=" * 60)

    manager = StudioManager()

    # Show opacities at different focus levels
    for focus in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        dominant = manager.get_dominant_studio(focus)
        opacities = manager.calculate_all_opacities(focus)
        
        print(f"\nFocus {focus:.1f}:")
        print(f"  Dominant: {dominant.name} ({STUDIO_INFO[dominant].icon})")
        print(f"  Opacities: ", end="")
        for level, opacity in opacities.items():
            if opacity > 0.1:
                print(f"{level.name}={opacity:.1f} ", end="")
        print()


def demo_comparison():
    """Compare how different studios see the same room."""
    print("\n" + "=" * 60)
    print("Multi-Studio Comparison: Living Room")
    print("=" * 60)

    geometry = create_sample_geometry()
    living_room = geometry["rooms"][0]

    print(f"\nRoom: {living_room['name']}")
    print(f"Area: {living_room['area']} m²")
    print(f"Orientation: {living_room['orientation']}")

    studios = {
        "Climate": ClimateStudio(),
        "Structural": StructuralStudio(),
        "Code": CodeStudio(),
        "Cost": CostStudio(),
        "Acoustic": AcousticStudio(),
    }

    print("\nEach studio's perspective:")
    for name, studio in studios.items():
        result = studio.analyze(geometry, intensity=0.5)
        
        # Find violations related to living room
        room_violations = [v for v in result.violations 
                          if v.element_id == "living" or "living" in v.message.lower()]
        
        print(f"\n  {STUDIO_INFO[getattr(StudioLevel, name.upper())].icon} {name}:")
        if room_violations:
            for v in room_violations:
                print(f"    ⚠️  {v.message}")
        else:
            print(f"    ✓ No issues")


if __name__ == "__main__":
    demo_all_studios()
    demo_studio_manager()
    demo_comparison()
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
