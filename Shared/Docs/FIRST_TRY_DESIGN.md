# First Try Design: Input Specification

The computer generates the optimal solution. Your job is to describe what you need clearly enough that optimal is actually optimal for you.

If you don't like the output, the problem is your input.

---

## Philosophy

- Design is description. If you can't describe it, it's not design — it's preference.
- The computer is the designer. You are the client.
- One try. No iteration on output. Iterate on your thinking instead.
- Clarity is required. Vague input produces generic output.

---

## Input Categories

### 1. Program Requirements

What spaces do you need?

```yaml
rooms:
  - name: "Living Room"
    area_min: 300 sf
    area_max: 450 sf
    priority: high
    
  - name: "Kitchen"
    area_min: 150 sf
    area_max: 200 sf
    priority: high
    features:
      - island
      - pantry
    
  - name: "Primary Bedroom"
    area_min: 200 sf
    area_max: 280 sf
    priority: high
    features:
      - ensuite
      - walk-in closet
      
  - name: "Bedroom 2"
    area_min: 120 sf
    area_max: 150 sf
    priority: medium
    
  - name: "Bedroom 3"
    area_min: 100 sf
    area_max: 130 sf
    priority: low  # can be sacrificed if needed
```

**Required fields:**
- Room name
- Area range (min/max)
- Priority (what can be sacrificed if constraints conflict?)

**Optional fields:**
- Features (ensuite, closet, island, etc.)
- Fixed dimensions (if aspect ratio matters)
- Ceiling height (if different from default)

---

### 2. Relationships

How should spaces connect?

```yaml
adjacencies:
  - [Kitchen, Living Room, required]      # must be directly connected
  - [Kitchen, Dining, required]
  - [Living Room, Dining, preferred]      # ideally connected, not mandatory
  - [Primary Bedroom, Ensuite, required]
  - [Bedrooms, Bathroom, preferred]       # group reference
  
separations:
  - [Bedrooms, Living Room, preferred]    # should have buffer/distance
  - [Primary Bedroom, Kids Bedrooms, preferred]
  
zones:
  - name: "Public"
    rooms: [Living Room, Dining, Kitchen]
    
  - name: "Private"
    rooms: [Primary Bedroom, Bedroom 2, Bedroom 3]
    
  - name: "Service"
    rooms: [Laundry, Garage, Mechanical]
```

**Relationship types:**
- `required` — must be satisfied or design fails
- `preferred` — optimize for this, but can sacrifice
- `avoid` — these should not be adjacent

---

### 3. Site Constraints

What does the land dictate?

```yaml
site:
  dimensions:
    width: 60 ft
    depth: 120 ft
    
  setbacks:
    front: 25 ft
    rear: 20 ft
    left: 5 ft
    right: 5 ft
    
  orientation:
    front_faces: south
    
  access:
    street: south
    alley: none
    
  topography: flat  # or: slopes_to_rear, slopes_to_left, etc.
  
  features:
    - existing_tree: { location: [45, 80], radius: 15, protect: true }
    
  views:
    - direction: north
      quality: good
      description: "Mountain view"
    - direction: west
      quality: bad
      description: "Neighbor's wall"
```

**Required fields:**
- Dimensions or boundary polygon
- Setbacks
- Street access direction

**Optional fields:**
- Orientation
- Topography
- Features to preserve
- View quality by direction

---

### 4. Priorities

What matters most? Rank these or assign weights.

```yaml
priorities:
  natural_light: 9        # 1-10 scale
  privacy: 7
  open_plan: 8
  efficient_circulation: 6
  outdoor_connection: 8
  views: 7
  minimize_hallways: 5
  compact_footprint: 4
  future_flexibility: 3
  cost: 5
```

**Common priority dimensions:**
- Natural light
- Privacy (from street, from neighbors)
- Open plan vs. defined rooms
- Circulation efficiency
- Indoor-outdoor connection
- View capture
- Minimize hallways / wasted space
- Compact footprint
- Expandability / flexibility
- Cost / simplicity

The system uses these to make tradeoffs. If you want light AND privacy AND open plan, you need to say which wins when they conflict.

---

### 5. Constraints (Hard Rules)

What is non-negotiable?

```yaml
constraints:
  max_footprint: 2000 sf
  max_stories: 2
  max_budget: 450000       # triggers cost optimization
  accessibility: full      # or: visitability, none
  
  code:
    jurisdiction: "Ontario Building Code"
    occupancy: residential
    
  structural:
    system: wood_frame     # or: steel, concrete, mass_timber
    max_span: 20 ft        # affects room dimensions
    
  envelope:
    insulation: R40_walls, R60_roof
    windows: triple_glazed
```

**Constraint types:**
- Size limits (footprint, height, FAR)
- Budget (triggers cost-aware optimization)
- Accessibility requirements
- Code jurisdiction
- Structural system
- Performance targets

Constraints are pass/fail. The design either meets them or it doesn't.

---

### 6. Style / Character (Optional)

Can you describe the feel?

```yaml
character:
  style: "modern farmhouse"   # or leave blank for pure optimization
  
  keywords:
    - clean lines
    - warm materials
    - connection to landscape
    
  avoid:
    - busy rooflines
    - dark interiors
    
  references:
    - "project_image_01.jpg"
    - "project_image_02.jpg"
```

This is the hardest category. Style is fuzzy. Options:
- Named styles (modern, craftsman, farmhouse, etc.)
- Keywords / descriptors
- Things to avoid
- Reference images (system extracts patterns)

If you can't describe it, leave it blank. The system optimizes for function. Style is your problem later.

---

### 7. Special Requirements

Anything unusual?

```yaml
special:
  - "Home office must have separate entrance for clients"
  - "Kids' bedrooms should share a Jack-and-Jill bathroom"
  - "Want to be able to convert garage to ADU later"
  - "Dog washing station near back entry"
  - "No stairs for elderly parent visits — main floor living"
```

Free-form text. The LLM interprets these and incorporates them as constraints or priorities.

---

## Example: Complete Input

```yaml
project:
  name: "Smith Residence"
  type: residential
  
program:
  rooms:
    - name: Living Room
      area: [300, 400]
      priority: high
    - name: Kitchen
      area: [150, 200]
      priority: high
      features: [island]
    - name: Dining
      area: [120, 150]
      priority: medium
    - name: Primary Bedroom
      area: [200, 250]
      priority: high
      features: [ensuite, walk-in closet]
    - name: Bedroom 2
      area: [120, 140]
      priority: medium
    - name: Office
      area: [100, 120]
      priority: medium
    - name: 2-Car Garage
      area: [400, 450]
      priority: high

adjacencies:
  - [Kitchen, Living Room, required]
  - [Kitchen, Dining, required]
  - [Primary Bedroom, Ensuite, required]
  - [Garage, Kitchen, preferred]

separations:
  - [Bedrooms, Living Room, preferred]

site:
  dimensions: [55, 110]
  setbacks: [25, 20, 5, 5]
  front_faces: south
  street: south
  views:
    - direction: north
      quality: good

priorities:
  natural_light: 9
  open_plan: 8
  outdoor_connection: 7
  efficient_circulation: 6
  privacy: 5

constraints:
  max_footprint: 1800 sf
  max_stories: 1
  accessibility: visitability
  code: "Ontario Building Code"
  structural: wood_frame

character:
  style: modern
  keywords: [clean, minimal, warm wood accents]

special:
  - "Office needs exterior door for client access"
  - "Covered patio off living room"
```

---

## Output

Given complete input, the system generates:

1. **Optimal floor plan** — rooms sized and placed to satisfy all constraints and maximize priorities
2. **Constraint report** — which constraints were binding (limited the design)
3. **Tradeoff summary** — what was sacrificed and why
4. **Confidence score** — how well does this satisfy your stated priorities?

If confidence is low, the system asks clarifying questions rather than generating a bad plan.

---

## If You Don't Like the Output

Don't adjust the plan. Adjust your input.

Ask yourself:
- Did I describe my priorities correctly?
- Did I miss a constraint?
- Did I say something was "preferred" when it's actually "required"?
- Did I forget to mention something I assumed was obvious?

The computer optimized for what you said. If that's not what you wanted, you said the wrong thing.

---

## The Hard Truth

Most design "iteration" is discovering what you actually want by reacting to what you don't want.

First Try Design makes you do that work upfront. It's harder. But it's honest.

If you can't describe it, it's not design. It's guessing.
