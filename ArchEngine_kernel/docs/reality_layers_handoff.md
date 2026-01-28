# Reality Layers Integration Handoff

## Overview

The QBD system now includes **Reality Layer Analysis** that provides physics-based simulation data for building designs. This data is automatically included in the `generated_building.json` output and is available via the LegiQBD API.

**Total Reality = Logic + Physics + Economics + Psychology**

---

## Quick Start

### Accessing Reality Data in JSON

The reality analysis is included in the `generated_building.json` output under the `reality_analysis` key:

```python
import json

# Load the building JSON
with open('generated_building.json', 'r') as f:
    building = json.load(f)

# Access reality analysis
reality = building['reality_analysis']

# Quick quality check
overall_score = reality['overall_score']  # 0.0 to 1.0
print(f"Design Quality: {overall_score * 100:.0f}%")
```

### Accessing via LegiQBD API

```python
from legiqbd.api import LegiQBDAPI

api = LegiQBDAPI()
session_id = api.new_session()

# Chat to create design
api.chat("3 bedroom house", session_id=session_id)

# Run reality analysis
reality = api.analyze_reality(session_id=session_id)

# Or include in chat response
response = api.chat("Add a garage", session_id=session_id, include_reality=True)
reality = response.get('reality')
```

---

## Data Structure Reference

### Top-Level Structure

```json
{
  "reality_analysis": {
    "environment": { /* Physics */ },
    "materiality": { /* Economics */ },
    "perception": { /* Psychology */ },
    "overall_score": 0.6  // Combined quality score (0-1)
  }
}
```

### 1. Environment Layer (Physics)

**Solar & Thermal Analysis**

```json
{
  "thermal_load_kw": 400.7,        // Peak heating demand
  "cooling_load_kw": 279.8,        // Peak cooling demand
  "peak_heating_month": "January", // Worst month for heating
  "passive_strategies": [          // Recommended passive design strategies
    "passive_solar_gain",
    "natural_ventilation",
    "thermal_mass",
    "night_flush_cooling"
  ],
  "daylight_factors": {
    "living": 0.45,    // 2-5% is good, <2% needs artificial light
    "kitchen": 0.38,
    "master_bedroom": 0.52
  },
  "acoustic_privacy": {
    "living": "moderate",      // good, moderate, poor
    "bedroom_1": "good",
    "bathroom": "poor"
  },
  "physics_violations": [
    "Excessive heating load: 400.7 kW",
    "Room master_bedroom: Poor acoustic privacy (poor)"
  ]
}
```

**Key Metrics:**
- `thermal_load_kw`: Peak heating load in kilowatts (lower = better insulation)
- `cooling_load_kw`: Peak cooling load in kilowatts (lower = better)
- `daylight_factors`: 2-5% is good, <2% needs more windows, >5% may cause glare
- `acoustic_privacy`: Privacy level between adjacent rooms

**Use Cases:**
- Size HVAC equipment
- Identify rooms needing additional windows
- Detect acoustic privacy issues between bedrooms/bathrooms
- Validate passive design strategies

### 2. Materiality Layer (Economics)

**Cost & Construction Analysis**

```json
{
  "total_cost": 521875,           // Total construction cost ($)
  "cost_per_sqft": 290.32,        // Cost per square foot ($/sqft)
  "budget_status": "under",       // under, near, over
  "construction_weeks": 8,        // Estimated construction duration
  "crew_size": 3,                 // Typical crew size
  "carbon_footprint_kg": 25050,   // Embodied carbon (kg CO2e)
  "lifecycle_cost_30yr": 854063,  // 30-year lifecycle cost ($)
  "risk_factors": [
    "Complex roof geometry",
    "Multiple exterior wall types"
  ]
}
```

**Key Metrics:**
- `budget_status`: "under" (good), "near" (caution), "over" (over budget)
- `construction_weeks`: Timeline for scheduling
- `carbon_footprint_kg`: Environmental impact for sustainability metrics
- `risk_factors`: Items that may cause cost overruns or delays

**Use Cases:**
- Real-time cost estimation during design
- Budget tracking and alerts
- Construction scheduling
- Sustainability reporting (LEED, carbon footprint)
- Contractor bidding preparation

### 3. Perception Layer (Psychology)

**Human Experience Analysis**

```json
{
  "wayfinding_score": 0.68,       // 0-1, higher = easier navigation
  "comfort_scores": {
    "living": 0.75,               // Combined thermal/visual/acoustic comfort
    "kitchen": 0.68,
    "master_bedroom": 0.82
  },
  "delight_scores": {
    "living": 0.60,               // Aesthetic quality, biophilia, etc.
    "kitchen": 0.55,
    "master_bedroom": 0.72
  },
  "overall_experience": 0.59,     // 0-1, overall user experience
  "critical_issues": [
    "No clear circulation path from entry to living"
  ],
  "enhancement_opportunities": [
    "increase_biophilic_elements",
    "add_landmarks_at_decision_points",
    "improve_daylight_uniformity"
  ]
}
```

**Key Metrics:**
- `wayfinding_score`: How easy it is to navigate (0-1 scale)
- `comfort_scores`: Per-room comfort (thermal + visual + acoustic)
- `delight_scores": Per-room delight (biophilia + prospect/refuge + aesthetics)
- `overall_experience`: Average of all perception metrics

**Use Cases:**
- Identify confusing layouts before construction
- Validate universal design principles
- Optimize room placement for comfort
- Generate design improvement suggestions

---

## Implementation Examples

### Example 1: Display Reality Dashboard

```python
def create_reality_dashboard(building_json):
    """Create a dashboard showing key reality metrics."""
    reality = building_json['reality_analysis']

    dashboard = {
        "overall_quality": reality['overall_score'] * 100,

        "physics": {
            "hvac_load": reality['environment']['thermal_load_kw'],
            "daylight_avg": sum(reality['environment']['daylight_factors'].values()) /
                           len(reality['environment']['daylight_factors']),
            "issues": len(reality['environment']['physics_violations'])
        },

        "economics": {
            "total_cost": reality['materiality']['total_cost'],
            "cost_sqft": reality['materiality']['cost_per_sqft'],
            "duration_weeks": reality['materiality']['construction_weeks'],
            "on_budget": reality['materiality']['budget_status'] == 'under'
        },

        "experience": {
            "navigation": reality['perception']['wayfinding_score'] * 100,
            "comfort_avg": sum(reality['perception']['comfort_scores'].values()) /
                           len(reality['perception']['comfort_scores']),
            "delight_avg": sum(reality['perception']['delight_scores'].values()) /
                          len(reality['perception']['delight_scores'])
        }
    }

    return dashboard
```

### Example 2: Room-Level Data Visualization

```python
def get_room_reality_data(building_json, room_id):
    """Get reality data for a specific room."""
    reality = building_json['reality_analysis']
    rooms = building_json['rooms']

    if room_id not in rooms:
        return None

    return {
        "room_name": rooms[room_id]['name'],
        "daylight_factor": reality['environment']['daylight_factors'].get(room_id, 0),
        "acoustic_privacy": reality['environment']['acoustic_privacy'].get(room_id, "unknown"),
        "comfort_score": reality['perception']['comfort_scores'].get(room_id, 0),
        "delight_score": reality['perception']['delight_scores'].get(room_id, 0),
    }

# Example: Generate room tooltips
for room_id in building_json['rooms']:
    data = get_room_reality_data(building_json, room_id)
    tooltip = f"""
    {data['room_name']}
    Daylight: {data['daylight_factor']*100:.0f}%
    Comfort: {data['comfort_score']*100:.0f}%
    Privacy: {data['acoustic_privacy']}
    """
```

### Example 3: Cost Alerts

```python
def check_budget_alerts(building_json, budget_limit):
    """Check if design is over budget and provide alerts."""
    reality = building_json['reality_analysis']
    materiality = reality['materiality']

    alerts = []

    # Check total cost
    if materiality['total_cost'] > budget_limit:
        alerts.append({
            "severity": "error",
            "message": f"Over budget by ${materiality['total_cost'] - budget_limit:,.0f}"
        })

    # Check budget status
    if materiality['budget_status'] == 'over':
        alerts.append({
            "severity": "warning",
            "message": "Design is over budget based on square footage"
        })

    # Check for risk factors
    for risk in materiality['risk_factors']:
        alerts.append({
            "severity": "info",
            "message": f"Risk factor: {risk}"
        })

    return alerts
```

### Example 4: Physics Validation

```python
def validate_physics(building_json):
    """Validate building physics and return issues."""
    reality = building_json['reality_analysis']
    env = reality['environment']

    validation = {
        "errors": [],
        "warnings": [],
        "info": []
    }

    # Check thermal load (typical range: 50-200 kW for residential)
    if env['thermal_load_kw'] > 300:
        validation['errors'].append(
            f"Heating load too high: {env['thermal_load_kw']} kW. "
            "Consider improving insulation."
        )

    # Check daylight factors
    for room_id, df in env['daylight_factors'].items():
        if df < 0.02:  # Less than 2%
            validation['warnings'].append(
                f"{room_id}: Low daylight ({df*100:.1f}%). Consider adding windows."
            )
        elif df > 0.10:  # More than 10%
            validation['info'].append(
                f"{room_id}: High daylight ({df*100:.1f}%). May cause glare."
            )

    # Check acoustic privacy for bedrooms
    for room_id, privacy in env['acoustic_privacy'].items():
        if 'bedroom' in room_id and privacy == 'poor':
            validation['errors'].append(
                f"{room_id}: Poor acoustic privacy. "
                "Consider adding sound insulation."
            )

    return validation
```

---

## Revit Integration Patterns

### Pattern 1: Room Tags with Reality Data

```csharp
// Revit API example - Update room tags with reality data
public void UpdateRoomTagsWithReality(Document doc, string jsonPath)
{
    string json = File.ReadAllText(jsonPath);
    var building = JsonConvert.DeserializeObject<BuildingData>(json);
    var reality = building.RealityAnalysis;

    foreach (Element room in new FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Rooms)
        .WhereElementIsNotElementType())
    {
        string roomId = room.get_Parameter(BuiltInParameter.ROOM_NUMBER).AsString();

        // Update room tag with daylight factor
        if (reality.Environment.DaylightFactors.ContainsKey(roomId))
        {
            Parameter daylightParam = room.LookupParameter("Daylight Factor");
            if (daylightParam != null)
            {
                double df = reality.Environment.DaylightFactors[roomId];
                daylightParam.Set(df * 100); // Convert to percentage
            }
        }

        // Update room tag with comfort score
        if (reality.Perception.ComfortScores.ContainsKey(roomId))
        {
            Parameter comfortParam = room.LookupParameter("Comfort Score");
            if (comfortParam != null)
            {
                double comfort = reality.Perception.ComfortScores[roomId];
                comfortParam.Set(comfort * 100); // Convert to 0-100 scale
            }
        }
    }
}
```

### Pattern 2: Schedule Generation

```csharp
// Create a schedule view showing reality layer data
public ViewSchedule CreateRealitySchedule(Document doc, string layer)
{
    // Create schedule for room data
    ViewSchedule schedule = ViewSchedule.CreateSchedule(
        doc, new ElementId(BuiltInCategory.OST_Rooms));

    // Define schedule fields
    schedule.Definition.AddField(SchedulableField.SchedulableFieldType.Field, "Room Name");
    schedule.Definition.AddField(SchedulableField.SchedulableFieldType.Field, "Area");

    if (layer == "environment")
    {
        schedule.Definition.AddField(SchedulableField.SchedulableFieldType.Parameter, "Daylight Factor");
        schedule.Definition.AddField(SchedulableField.SchedulableFieldType.Parameter, "Acoustic Privacy");
    }
    else if (layer == "perception")
    {
        schedule.Definition.AddField(SchedulableField.SchedulableFieldType.Parameter, "Comfort Score");
        schedule.Definition.AddField(SchedulableField.SchedulableFieldType.Parameter, "Delight Score");
    }

    schedule.Name = $"Reality Layer - {layer}";
    return schedule;
}
```

---

## API Reference

### LegiQBD API Methods

```python
# Full reality analysis (all three layers)
reality = api.analyze_reality(
    session_id="session_id",
    construction_system="wood_light_frame",  # or: steel, concrete, mass_timber
    quality_level="standard",                # basic, standard, premium, custom
    region="northeast"                      # for cost calculations
)

# Individual layer analysis
env = api.analyze_environment(session_id="session_id")
mat = api.analyze_materiality(session_id="session_id")
perc = api.analyze_perception(session_id="session_id")
```

### Construction System Options

| System | Description | Cost Multiplier |
|--------|-------------|-----------------|
| `wood_light_frame` | Standard 2x4/2x6 wood framing | 1.0x |
| `wood_advanced` | Advanced wood frame with high-performance materials | 1.2x |
| `steel_light_gauge` | Light gauge steel framing | 1.1x |
| `steel_structural` | Structural steel frame | 1.3x |
| `concrete_cmu` | Concrete masonry units | 1.2x |
| `concrete_poured` | Poured concrete structure | 1.4x |
| `mass_timber` | CLT/glulam mass timber | 1.5x |

### Quality Level Options

| Level | Description | Cost Multiplier |
|-------|-------------|-----------------|
| `basic` | Economy-grade materials and finishes | 0.8x |
| `standard` | Standard builder-grade materials | 1.0x |
| `premium` | Higher-end materials and finishes | 1.3x |
| `custom` | Custom architect-designed details | 1.6x |

---

## Troubleshooting

### Reality Analysis Returns Zeros

**Problem:** All reality values are 0

**Solution:** Check that:
1. The building has rooms defined in the JSON
2. Rooms have valid area_min and dimensions
3. Site data (width, depth) is present

### Missing Daylight Factors

**Problem:** `daylight_factors` dict is empty

**Solution:**
- Ensure rooms have valid positions and dimensions
- Check that site latitude and climate_zone are set
- Verify building_layout has exterior wall definitions

### Cost Seems Wrong

**Problem:** Cost values seem incorrect

**Solution:**
- Verify `construction_system` and `quality_level` parameters
- Check that `region` matches your project location
- Ensure room areas are in square meters (not square feet)

---

## Best Practices

1. **Run Reality Analysis After Each Major Change**
   ```python
   # After adding/removing rooms
   api.chat("Add a master bathroom")
   reality = api.analyze_reality()  # Get updated analysis
   ```

2. **Monitor Budget Status Continuously**
   ```python
   if reality['materiality']['budget_status'] == 'over':
       # Alert user or suggest cost-saving changes
   ```

3. **Use Physics Violations for Design Validation**
   ```python
   violations = reality['environment']['physics_violations']
   if violations:
       # Display to user as design issues to resolve
   ```

4. **Leverage Enhancement Opportunities**
   ```python
   opportunities = reality['perception']['enhancement_opportunities']
   # Suggest these to user as design improvements
   ```

5. **Combine Scores for Decision Making**
   ```python
   # Example: Recommend design if overall_score > 0.7 and no violations
   if (reality['overall_score'] > 0.7 and
       len(reality['environment']['physics_violations']) == 0):
       return "Design approved for documentation"
   ```

---

## Contact & Support

For questions or issues with reality layer integration:
- Documentation: See `qbd/layers/` source code
- API Reference: `legiqbd/api.py`
- Test Examples: `test_qbd_reality_layers.py`

---

## Version History

- **v1.0** (2024-01): Initial reality layer implementation
  - Environment: Solar, thermal, acoustics
  - Materiality: Cost, construction, carbon
  - Perception: Wayfinding, comfort, delight
