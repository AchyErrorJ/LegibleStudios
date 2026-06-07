# The Escher Feeling — Visual & Interaction Philosophy

How Legible Studio feels. The spatial logic underneath the interface.

---

## Reference

**M.C. Escher — Relativity (1953)**

Three staircases. Three gravity fields. Three groups of people, each walking in a direction that makes sense to them, impossible to each other. Same space, different orientations. All true at once.

The staircases connect — they share landings, share structure. Each orientation is internally consistent. You can trace a path within one gravity. But the whole is impossible if you try to unify it into one gravity.

You don't need to unify it. You accept all three.

---

## The Core Insight

The model isn't viewed from different angles. The model *exists* differently depending on who's holding it.

| Gravity | Who | What's Real to Them |
|---------|-----|---------------------|
| Design | Architect / Designer | Relationships, flow, topology |
| Client | Homeowner / Occupant | Spaces, light, feel, life |
| Build | Contractor / Builder | Coordinates, sequence, materials |

Same geometry. Not different views of one truth. **Different truths that share structure.**

---

## The Shared Landings

Where do the gravities connect?

A wall exists in all three — but means something different:

| Gravity | What the Wall Means |
|---------|---------------------|
| Design | "This is a door relationship with the hall" |
| Client | "This separates my bedroom from the hallway" |
| Build | "2x6 @ 406mm OC, corner A to corner B" |

Same wall. Three gravities. All true.

---

## Two Axes of Control

### Axis 1: Elevation = Abstraction (LOD)

How high you are above the model determines how abstract it is.

| Position | What You See | LOD |
|----------|--------------|-----|
| High above | Blobs, topology, relationships | LOD 1 |
| Mid height | Walls, openings, structure | LOD 2 |
| Eye level | Fixtures, materials, space | LOD 3 |
| Drafting table | 2D views, documentation | LOD 4-5 |

In VR: physically move up/down.
On monitor: zoom in/out, camera height.

### Axis 2: Gravity Triangle = Whose Truth

Which perspective dominates the rendering.

```
            Design
              △
             / \
            / ● \
           /     \
       Client ――― Build
```

Drag the point. Reality shifts.

---

## The Gravity Triangle

A small control, corner of screen. Three corners, three gravities. Drag the puck inside the triangle to blend.

| Puck Position | What You See |
|---------------|--------------|
| Design corner | Blobs, relationships, wireframe, analytical |
| Client corner | Realistic render, materials, light, livable |
| Build corner | Coordinates, control points, specs, structure |
| Center | All three faintly present, nothing dominant |
| Edge | Blend of two gravities |

**Blending, not switching.** The transition is a fade. Elements don't disappear — they lose focus. Elements don't appear — they gain focus.

---

## Rendering by Gravity

One model, three renders. Everything interpolates.

| Element | Design | Client | Build |
|---------|--------|--------|-------|
| Blobs | Solid, draggable | Hidden | Hidden |
| Relationships | Color-coded overlaps | Hidden | Hidden |
| Walls | Wireframe or simple | Solid, textured | Solid, material tags |
| Openings | Symbols | Realistic doors/windows | Rough openings |
| Fixtures | Ghosted or icons | Solid, realistic | Coordinate markers |
| Materials | None | Visible, lit | Specification labels |
| Light | Analytical (arrows) | Realistic (sun, shadows) | None |
| Coordinates | Visible | Hidden | Primary |
| Dimensions | Hidden | Hidden | On demand |
| Annotations | Relationship labels | Room names | Grid lines, control points |

---

## Blending Use Cases

| Scenario | Gravity Blend |
|----------|---------------|
| Designer working alone | 100% Design |
| Presenting to client | Slide toward Client |
| Explaining a decision | Pull back toward Design — "this is why" |
| Handing off to builder | Slide toward Build |
| Client + contractor meeting | Blend Client + Build — "this is what it looks like, here are the control points" |
| Design review with engineer | Blend Design + Build |

---

## The Two Controls Together

Elevation and gravity are independent but complementary.

| Elevation | Gravity | Experience |
|-----------|---------|------------|
| High (LOD 1) | Design | Topology editing, blob manipulation |
| High (LOD 1) | Client | Massing with realistic light, "feel" of the shape |
| High (LOD 1) | Build | Site plan, overall coordinates |
| Mid (LOD 2) | Design | Wall relationships, flow analysis |
| Mid (LOD 2) | Client | Spatial preview, room sizes |
| Mid (LOD 2) | Build | Wall layout, control points |
| Eye level (LOD 3) | Design | Checking fixture relationships |
| Eye level (LOD 3) | Client | Walking through realistic house |
| Eye level (LOD 3) | Build | Verifying coordinates in context |

**Any combination is valid.** The software doesn't restrict you.

---

## VR vs Monitor

The VR version is the true version. The monitor version is a projection of it.

### VR

- You physically exist above the model
- Move up/down to change LOD
- Gravity triangle as floating UI or hand gesture
- Descend into the house, walk through at human scale
- Rise up to god view, manipulate topology
- The spatial metaphor is literal

### Monitor

- Orbital/isometric camera looking down at model
- Scroll/zoom to change elevation (LOD)
- Gravity triangle in corner of screen
- Same mental model, 2D projection
- Keyboard shortcuts for gravity presets (D/C/B)

---

## The Fade Transition

When gravity shifts, elements don't pop in/out. They fade.

**Transition properties:**

- Duration: 300-500ms (fast enough to feel responsive, slow enough to track)
- Easing: smooth ease-in-out
- Overlapping: outgoing elements fade as incoming elements resolve
- Never fully invisible: even at 0% gravity, elements ghost at ~5% opacity

**The feeling:** Like adjusting your eyes. Like focus pulling. Like waking up and the room coming into clarity.

---

## Why This Matters

Traditional CAD: one view, one truth. Switch between plan/elevation/3D. Hard cuts. Mode switches.

Legible Studio: multiple truths coexist. Blend between them. The same space holds different meanings for different people. The software respects that.

**The Escher feeling:** You're not looking at a model. You're inside a structure that exists differently depending on which way gravity pulls you. And you can rotate gravity.

---

## Summary

- **Relativity (1953):** The reference. Three gravities, same space, all true.
- **Elevation:** How abstract (LOD 1-5)
- **Gravity triangle:** Whose truth (Design / Client / Build)
- **Blending:** Continuous, not discrete. Fade transitions.
- **One geometry:** Rendering is the lens, not the reality.
- **VR-first:** Monitor is projection of the true spatial interface.

The design exists at multiple levels simultaneously. You move through it — up/down for abstraction, triangle for perspective. The Escher feeling is the product.

---

*Document version: 1.0*
