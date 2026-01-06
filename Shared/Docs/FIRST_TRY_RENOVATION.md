# First Try Design: Renovation Questionnaire

Design starts from what exists. The plan evolves from constraints inward.

---

## Philosophy

New construction: blank slate → describe life → generate optimal plan

Renovation: existing conditions → describe problems → solve within constraints

You're not designing from scratch. You're negotiating between what you have, what you want, and what's possible.

---

## How It Works

1. Capture existing conditions
2. Describe what's wrong
3. Define what's fixed (can't or won't change)
4. Describe what you need (same as new construction)
5. Set scope boundaries (how far are you willing to go?)
6. System generates options within constraints
7. See what's possible — and what requires going further

---

## Group 0: Existing Conditions

*What do you have? The building is the first constraint.*

### Input Methods

**0.1 How do we capture the existing building?**
- Upload existing plans (PDF, CAD, image)
- 3D scan (phone LiDAR, Matterport, etc.)
- Manual survey (system guides you through measuring)
- Rough sketch + key dimensions

**0.2 What information is needed?**
- Overall footprint dimensions
- Room layout and sizes
- Wall locations
- Door and window locations
- Ceiling heights
- Number of floors

**0.3 System identifies:**
- Room names and sizes
- Circulation paths
- Structural vs. non-structural walls (may need confirmation)
- Plumbing locations (kitchens, baths, laundry)
- Exterior wall locations
- Building footprint on site

### Plan Output After Group 0

- Existing conditions documented
- Current room areas calculated
- Adjacencies mapped
- **Baseline established** — this is what we're working with

---

## Group 1: What's Wrong

*Why are you renovating? Problems drive solutions.*

### Questions

**1.1 What doesn't work about how you live here?**
- Free form description
- Or pick from common issues:

**Layout Issues**
- Kitchen is closed off / too small / poorly laid out
- Not enough bathrooms / bathroom in wrong location
- Bedrooms too small / not enough bedrooms
- No dedicated workspace
- Bad flow between spaces
- Wasted space (hallways, awkward rooms)
- Main living area too dark
- No mudroom / entry drop zone

**Functional Issues**
- Not enough storage
- Laundry in wrong location
- No main floor bathroom (need one for accessibility/guests)
- Garage doesn't fit cars / no garage
- No outdoor connection

**Condition Issues**
- Kitchen outdated (cabinets, appliances, layout)
- Bathrooms outdated
- Finishes worn
- Windows drafty / too small
- Systems failing (HVAC, electrical, plumbing)

**Life Changes**
- Family growing (need more space / bedrooms)
- Family shrinking (too much house)
- Working from home now (need office)
- Aging in place (accessibility needs)
- New hobbies (workshop, studio, gym)

**1.2 Rank the problems**
- Which is the #1 thing that has to change?
- What would be nice but isn't critical?
- What can you live with if budget is tight?

### System Translates To

| Problem | Potential Solutions |
|---------|-------------------|
| Kitchen closed off | Remove wall (if non-structural), create opening, reconfigure |
| Not enough bathrooms | Add bathroom (plumbing feasibility check) |
| Bedroom too small | Expand into adjacent space, or swap room functions |
| No workspace | Convert room, carve out space, add |
| Too dark | Add windows, remove walls, add skylights |
| No mudroom | Convert existing space, add at entry |

### Plan Output After Group 1

- Problems documented and ranked
- System flags which problems can be solved within existing footprint
- System flags which problems likely require addition
- **Problem map** — what needs to change, prioritized

---

## Group 2: What's Fixed

*What can't change? Or what won't you change?*

### Structural Constraints

**2.1 Do you know which walls are structural?**
- Yes (mark them)
- No (system will assume exterior + likely candidates)
- Have original plans showing structure

**2.2 Foundation type?**
- Basement (can potentially expand down or reconfigure)
- Crawlspace (limited access)
- Slab (plumbing relocation expensive)
- Don't know

**2.3 Building type?**
- Single family detached
- Semi-detached / duplex
- Townhouse (shared walls)
- Condo / apartment (limited to interior)

### Regulatory Constraints

**2.4 Any heritage / historic designation?**
- Yes — exterior can't change
- Yes — some interior restrictions
- No

**2.5 Zoning limitations?**
- Maximum lot coverage (limits additions)
- Setback requirements
- Height restrictions
- Don't know (system can look up by address)

### Personal Constraints

**2.6 What do you love and want to keep?**
- Specific rooms that work well
- Features (fireplace, built-ins, moldings, original hardwood)
- Character elements (archways, ceiling details)
- Layout aspects (love the living room location)

**2.7 What areas are off-limits?**
- Don't touch the front facade
- Don't change the roofline
- Leave the basement as-is
- Guest suite / rental unit stays
- [Room X] just renovated, not changing it

**2.8 Exterior changes?**
- Open to changing exterior (new windows, siding, additions)
- Prefer to keep exterior as-is
- Minor changes okay (new windows same locations)

### System Translates To

| Constraint | Impact |
|------------|--------|
| Structural wall between kitchen/living | Can't remove, but can add opening with beam |
| Slab foundation | Moving plumbing expensive, minimize drain relocations |
| Townhouse shared wall | Can't add windows on that side |
| Heritage designation | Exterior unchanged, work within existing shell |
| Keep fireplace | Design around this anchor element |
| Don't touch front facade | All changes to rear/sides |

### Plan Output After Group 2

- Fixed elements locked
- Moveable elements identified
- **Constraint map** — what can and can't change

---

## Group 3: What Do You Need

*Same as new construction — describe life, not dimensions.*

### Questions

Use the same questions from the new construction questionnaire, but framed as "what you need" vs. "what you have":

**3.1 Bedroom needs**
- Current: 3 bedrooms
- Need: Still 3? More? Could reduce?
- For each: what furniture, what size bed, who uses it

**3.2 Bathroom needs**
- Current: 1 full bath, 1 powder room
- Need: Another full bath? Where? For whom?
- Accessibility requirements?

**3.3 Kitchen needs**
- What's wrong with current kitchen?
- How do you cook? (same Group 3 questions)
- Island? More storage? Better layout?

**3.4 Living/gathering needs**
- How do you use current living spaces?
- What's missing? (open to kitchen, more seating, playroom)

**3.5 Work/hobby needs**
- Current: no dedicated office
- Need: full office, occasional desk, studio, workshop

**3.6 Storage needs**
- Where is storage lacking?
- Coat closet, pantry, linen, garage, basement

**3.7 Outdoor connection**
- Current: slider to small deck
- Want: bigger deck, covered porch, indoor-outdoor living

### System Compares

For each need:
- Can it fit in existing space? (reconfigure)
- Does it require taking space from somewhere else? (tradeoff)
- Does it require adding space? (addition)

### Plan Output After Group 3

- Needs documented
- Gap analysis: needs vs. existing
- **Feasibility flags** — what fits, what's tight, what requires addition

---

## Group 4: How Far Will You Go

*Scope determines possibilities. Be honest about limits.*

### Questions

**4.1 What's your budget range?**
- Under $25k (cosmetic only)
- $25k - $75k (minor reconfiguration)
- $75k - $150k (significant renovation)
- $150k - $300k (major renovation)
- $300k+ (gut renovation or addition)
- Not sure yet (show me options at different levels)

**4.2 What level of disruption can you handle?**
- We're living in the house during construction
- We can move out for a few weeks
- We can move out for months
- House is vacant

**4.3 What scope are you comfortable with?**

| Level | Description | Typical Work |
|-------|-------------|--------------|
| 1: Cosmetic | Surfaces only | Paint, flooring, fixtures, appliances |
| 2: Minor | Non-structural changes | Remove partitions, reconfigure rooms, new kitchen/bath in place |
| 3: Moderate | Some structural work | Open up walls with beams, add bathroom, move kitchen |
| 4: Major | Significant structural | Reconfigure floor plan, add dormers/skylights |
| 5: Addition | Expand footprint | Bump-out, second story, new wing |
| 6: Gut | Keep shell, redo everything | Down to studs, new systems, fully reconfigured |

**4.4 Any hard stops?**
- Definitely not adding square footage
- Not touching the roof
- Not opening walls (dust, mess concerns)
- Must keep a functional kitchen throughout

### System Uses Scope To

- Filter solutions to what's within scope
- Flag when a need requires exceeding scope
- Show "if you went to Level X, you could also..."

### Plan Output After Group 4

- Scope boundaries set
- **Options generated within scope**
- Stretch options shown (what you'd get at next level)

---

## Group 5: Priorities & Feel

*Same as new construction — what matters most, how should it feel?*

### Questions

**5.1 Priorities** (rank for tradeoffs)
- Maximize space
- Minimize cost
- Minimize disruption
- Natural light
- Open plan
- Storage
- Future flexibility

**5.2 Match or update the existing character?**
- Match existing style (seamless addition/renovation)
- Update to something new (contrast is okay)
- Hybrid (new areas modern, keep original character where it exists)

**5.3 Material/finish direction**
- Keep existing materials where possible
- Update everything to consistent new palette
- Mix old and new

### Plan Output After Group 5

- Design direction set
- **Final options generated** — here's what's possible

---

## Output: Renovation Options

The system generates options at different scope levels:

### Option A: Minimal Intervention
- Scope: Level 2 (minor)
- Budget: ~$50k
- What changes: Kitchen reconfigured in place, powder room added in closet
- What's solved: Better kitchen, main floor bath
- What's not solved: Still no dedicated office

### Option B: Moderate Renovation
- Scope: Level 3 (moderate)
- Budget: ~$120k
- What changes: Wall removed kitchen-to-living (beam added), small office carved from dining room, new deck
- What's solved: Open plan, dedicated office, outdoor living
- Tradeoffs: Dining room smaller

### Option C: Addition
- Scope: Level 5 (addition)
- Budget: ~$250k
- What changes: Rear bump-out for family room + office, existing living becomes larger open kitchen/dining
- What's solved: Everything on the list
- Impact: 400 sf added, 3-4 month construction

Each option shows:
- Floor plan before/after
- What problems it solves
- What constraints drove the design
- Budget estimate
- Construction impact (timeline, disruption)

---

## Renovation-Specific Constraints

### Plumbing Stack Rule
- Bathrooms and kitchens are cheapest near existing plumbing
- Moving a toilet more than a few feet = expensive
- Adding bathroom directly above/below existing = cheapest
- System flags plumbing cost impacts

### Structural Intervention
- Every structural change adds cost and complexity
- System minimizes structural work unless required
- Shows "beam required" for any wall removal

### Matching Existing
- New windows should align with existing
- Rooflines on additions should relate to original
- Floor levels need to match (or intentional step)
- System checks for mismatches

### Phasing
- Can this be done in phases?
- Kitchen first, addition later
- System can suggest logical phases

---

## Comparison: New Construction vs. Renovation

| Aspect | New Construction | Renovation |
|--------|------------------|------------|
| Starting point | Intent | Existing conditions |
| Primary constraint | Site + budget | Existing building + budget |
| Question flow | Life → rooms → site → feel | Problems → constraints → needs → scope |
| Output | Optimal plan | Options within constraints |
| Iteration | Refine your description | Adjust scope or accept tradeoffs |

---

## Edge Cases

### "Just tell me what's possible"
System can generate options at every scope level and let you react. Sometimes seeing the options clarifies what you actually want.

### "I want X but can't afford it"
System shows what you get at your budget, and what it would take to get X. Your choice: adjust expectations or adjust budget.

### "The building is weird"
Older buildings have quirks — non-square rooms, random level changes, odd structure. System works with documented conditions. Capture accurately.

### "Can I DIY some of it?"
System can flag which work requires permits/professionals vs. cosmetic/DIY. Doesn't change the design, but helps phase and budget.

### "What about permits?"
System flags work that likely requires permits (structural, plumbing, electrical, egress). Permit requirements vary by jurisdiction — system notes this but doesn't guarantee.

---

## The Point

Renovation is negotiation: what you have vs. what you want vs. what's possible.

The system maps the territory:
- Here's what exists
- Here's what you want
- Here's what's fixed
- Here's what's possible at each scope level

You decide how far to go. The system shows you what you get.

If you can describe the problem and your limits, we can show you the solutions.
