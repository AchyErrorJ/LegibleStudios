//! Sheet layout: compose drawings onto a fixed-size permit sheet at true
//! architectural scale, with a reserved title block that never overlaps the
//! drawing.
//!
//! The rest of the drawing crate emits each drawing as its own SVG authored in
//! a per-drawing unit space (plan millimetres × an export factor). This module
//! treats those as *viewports*: it parses a drawing's `viewBox`, scales it so
//! the real-world geometry lands at a chosen paper scale (e.g. 1:50), and
//! places it inside the drawing area of a fixed paper size (default ARCH D),
//! with a full-width title block strip along the bottom.
//!
//! The sheet itself is authored in **paper millimetres** (1 user unit = 1 mm),
//! so [`crate::sheet::PaperSize`] dimensions are the real page size. Render to
//! PDF with a 25.4-DPI page (1 unit → 1 mm) for a true-to-scale plot.

use std::fmt::Write as _;

use crate::title_block::{DrawingInfo, ProjectInfo};

/// A fixed paper size in landscape millimetres (`w_mm >= h_mm`).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PaperSize {
    pub w_mm: f32,
    pub h_mm: f32,
    pub name: &'static str,
}

impl PaperSize {
    /// ARCH D — 24" × 36", landscape. The standard residential permit sheet.
    pub const ARCH_D: PaperSize = PaperSize { w_mm: 914.0, h_mm: 610.0, name: "ARCH D" };
    /// ARCH C — 18" × 24", landscape.
    pub const ARCH_C: PaperSize = PaperSize { w_mm: 610.0, h_mm: 457.0, name: "ARCH C" };
    /// ANSI B / Tabloid — 11" × 17", landscape.
    pub const ANSI_B: PaperSize = PaperSize { w_mm: 432.0, h_mm: 279.0, name: "ANSI B" };
    /// ISO A1 — 841 × 594 mm, landscape.
    pub const A1: PaperSize = PaperSize { w_mm: 841.0, h_mm: 594.0, name: "A1" };
}

impl Default for PaperSize {
    fn default() -> Self {
        Self::ARCH_D
    }
}

/// Sheet layout constants (paper millimetres).
const BORDER_MM: f32 = 12.0; // outer margin to the sheet edge
const TITLE_STRIP_MM: f32 = 40.0; // height of the bottom title-block strip
const GUTTER_MM: f32 = 8.0; // gap between drawing area and title strip

/// One drawing to place on a sheet.
#[derive(Debug, Clone)]
pub struct SheetDrawing {
    /// A complete drawing SVG (no title block) authored by one of the crate's
    /// generators.
    pub svg: String,
    /// The drawing's authored model units per real-world millimetre — i.e. the
    /// `scale` passed to its exporter (floor plan = 10.0, section = 0.05, …).
    pub model_units_per_mm: f32,
    /// Paper scale denominator: 50 for 1:50, 20 for 1:20.
    pub scale_denominator: f32,
    /// Sub-title shown under the drawing when several share a sheet.
    pub caption: String,
}

impl SheetDrawing {
    /// Scale label, e.g. `"1 : 50"`.
    #[must_use]
    pub fn scale_label(&self) -> String {
        format!("1 : {}", self.scale_denominator.round() as i64)
    }
}

/// The drawing-area rectangle (paper mm) inside the borders, above the title
/// strip: `(x, y, w, h)`.
#[must_use]
fn drawing_area(paper: PaperSize) -> (f32, f32, f32, f32) {
    let x = BORDER_MM;
    let y = BORDER_MM;
    let w = paper.w_mm - 2.0 * BORDER_MM;
    let h = paper.h_mm - 2.0 * BORDER_MM - TITLE_STRIP_MM - GUTTER_MM;
    (x, y, w, h)
}

/// Parse `viewBox="x y w h"` → `(x, y, w, h)`.
fn parse_viewbox(svg: &str) -> Option<(f32, f32, f32, f32)> {
    let vb = svg.split("viewBox=\"").nth(1)?.split('"').next()?;
    let n: Vec<f32> = vb.split_whitespace().filter_map(|t| t.parse().ok()).collect();
    if n.len() == 4 {
        Some((n[0], n[1], n[2], n[3]))
    } else {
        None
    }
}

/// Extract the body of a drawing SVG: everything between the opening `<svg …>`
/// tag and `</svg>`, with the full-bleed white background rect removed (it
/// would otherwise paint over the whole sheet once nested in a group).
fn svg_body(svg: &str) -> String {
    // Strip the XML declaration and the opening `<svg …>` tag (NOT just the
    // first `>`, which would be the `?>` of `<?xml?>` and leave the inner
    // `<svg>` element — a nested viewport that ignores our placement transform).
    let after_open = svg
        .find("<svg")
        .and_then(|i| svg[i..].find('>').map(|j| i + j + 1));
    let body = match (after_open, svg.rfind("</svg>")) {
        (Some(start), Some(close)) if start <= close => &svg[start..close],
        _ => svg,
    };
    body.replace(
        "<rect width=\"100%\" height=\"100%\" fill=\"white\"/>\n",
        "",
    )
    .replace("<rect width=\"100%\" height=\"100%\" fill=\"white\"/>", "")
}

/// How a placed drawing turned out — lets callers warn when a chosen scale
/// overflows the drawing area.
#[derive(Debug, Clone, Copy)]
pub struct Placement {
    /// Placed width/height on paper (mm) at the requested scale.
    pub content_w_mm: f32,
    pub content_h_mm: f32,
    /// True if the drawing exceeds the drawing area at this scale.
    pub overflows: bool,
}

/// Compose a single drawing onto a sheet at its true scale, with a bottom
/// title block. Returns the sheet SVG (authored in paper millimetres) and the
/// [`Placement`] for overflow reporting.
#[must_use]
pub fn compose_sheet(
    drawing: &SheetDrawing,
    paper: PaperSize,
    project: &ProjectInfo,
    info: &DrawingInfo,
) -> (String, Placement) {
    let (ax, ay, aw, ah) = drawing_area(paper);

    let (vbx, vby, vbw, vbh) = parse_viewbox(&drawing.svg).unwrap_or((0.0, 0.0, aw, ah));
    // Scale from the drawing's model units to paper millimetres at 1:N.
    // model_units = real_mm * model_units_per_mm, and real_mm → real_mm/N on
    // paper, so paper_mm = model_units / (model_units_per_mm * N).
    let denom = (drawing.model_units_per_mm * drawing.scale_denominator).max(1e-6);
    let g = 1.0 / denom;
    let content_w = g * vbw;
    let content_h = g * vbh;

    // Centre the drawing in the area; pin to top-left if it overflows.
    let overflows = content_w > aw + 0.5 || content_h > ah + 0.5;
    let off_x = ax + ((aw - content_w) * 0.5).max(0.0) - g * vbx;
    let off_y = ay + ((ah - content_h) * 0.5).max(0.0) - g * vby;

    let mut s = String::with_capacity(drawing.svg.len() + 2048);
    s.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
    let _ = writeln!(
        s,
        r#"<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">"#,
        w = paper.w_mm,
        h = paper.h_mm,
    );
    s.push_str("<rect width=\"100%\" height=\"100%\" fill=\"white\"/>\n");

    // Sheet border (inside the bleed).
    let _ = writeln!(
        s,
        r#"<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="black" stroke-width="1.2"/>"#,
        x = BORDER_MM * 0.5,
        y = BORDER_MM * 0.5,
        w = paper.w_mm - BORDER_MM,
        h = paper.h_mm - BORDER_MM,
    );

    // Placed drawing, clipped to the drawing area so an overflow can't bleed
    // into the title block.
    let _ = writeln!(
        s,
        r#"<clipPath id="area"><rect x="{ax}" y="{ay}" width="{aw}" height="{ah}"/></clipPath>"#,
    );
    let _ = writeln!(s, r#"<g clip-path="url(#area)">"#);
    let _ = writeln!(s, r#"<g transform="translate({off_x} {off_y}) scale({g})">"#);
    s.push_str(&svg_body(&drawing.svg));
    s.push_str("</g>\n</g>\n");

    // Title block strip along the bottom.
    s.push_str(&bottom_title_block(paper, project, info, &drawing.scale_label()));

    s.push_str("</svg>\n");

    (
        s,
        Placement { content_w_mm: content_w, content_h_mm: content_h, overflows },
    )
}

/// Render the full-width bottom title block (paper-mm coordinates, paper-sized
/// text). Lays out a single horizontal strip divided into labelled cells.
fn bottom_title_block(
    paper: PaperSize,
    project: &ProjectInfo,
    info: &DrawingInfo,
    scale_label: &str,
) -> String {
    let x0 = BORDER_MM;
    let y0 = paper.h_mm - BORDER_MM - TITLE_STRIP_MM;
    let w = paper.w_mm - 2.0 * BORDER_MM;
    let h = TITLE_STRIP_MM;

    // Right-hand data block columns (sheet metadata); the left is project info.
    let meta_w = 150.0_f32.min(w * 0.35);
    let meta_x = x0 + w - meta_w;

    let mut s = String::with_capacity(1024);
    let esc = crate::svg::xml_escape;

    // Strip outline.
    let _ = writeln!(
        s,
        r#"<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="white" stroke="black" stroke-width="1"/>"#,
    );
    // Divider between project info and metadata.
    let _ = writeln!(
        s,
        r#"<line x1="{mx}" y1="{y0}" x2="{mx}" y2="{y1}" stroke="black" stroke-width="0.8"/>"#,
        mx = meta_x,
        y1 = y0 + h,
    );

    // --- left: project name + address + designer ---
    let _ = writeln!(
        s,
        r#"<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="7" font-weight="bold" fill="black">{name}</text>"#,
        x = x0 + 6.0,
        y = y0 + 12.0,
        name = esc(&project.name),
    );
    if !project.address.is_empty() {
        let _ = writeln!(
            s,
            r#"<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="4.5" fill="rgb(51,51,51)">{addr}</text>"#,
            x = x0 + 6.0,
            y = y0 + 20.0,
            addr = esc(&project.address),
        );
    }
    let designer_line = if project.designer.is_empty() {
        String::new()
    } else if project.designer_bcin.is_empty() {
        format!("QUALIFIED DESIGNER: {}", project.designer)
    } else {
        format!(
            "QUALIFIED DESIGNER: {}   {}",
            project.designer, project.designer_bcin
        )
    };
    if !designer_line.is_empty() {
        let _ = writeln!(
            s,
            r#"<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="4.5" fill="rgb(51,51,51)">{d}</text>"#,
            x = x0 + 6.0,
            y = y0 + h - 6.0,
            d = esc(&designer_line),
        );
    }
    // Drawing title — large, centred in the left zone.
    let _ = writeln!(
        s,
        r#"<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="8" font-weight="bold" fill="black" text-anchor="middle">{title}</text>"#,
        x = x0 + (meta_x - x0) * 0.5,
        y = y0 + h - 6.0,
        title = esc(&info.title),
    );

    // --- right: metadata cells (sheet no, scale, date) ---
    let cell = |s: &mut String, row: usize, label: &str, value: &str| {
        let cy = y0 + 8.0 + (row as f32) * 11.0;
        let _ = writeln!(
            s,
            r#"<text x="{lx}" y="{cy}" font-family="Arial, sans-serif" font-size="3.5" fill="rgb(102,102,102)">{label}</text>"#,
            lx = meta_x + 4.0,
        );
        let _ = writeln!(
            s,
            r#"<text x="{vx}" y="{vy}" font-family="Arial, sans-serif" font-size="6" font-weight="bold" fill="black">{value}</text>"#,
            vx = meta_x + 4.0,
            vy = cy + 6.0,
            value = esc(value),
        );
    };
    cell(&mut s, 0, "SHEET", &info.number);
    cell(&mut s, 1, "SCALE", scale_label);
    cell(&mut s, 2, "DATE", &info.date);

    s
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_drawing(scale_denominator: f32) -> SheetDrawing {
        // A 10 m × 8 m plan authored at 10 units/mm (floor-plan convention):
        // viewBox is 100000 × 80000 units.
        let svg = concat!(
            "<?xml version=\"1.0\"?>\n",
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1000\" height=\"800\" ",
            "viewBox=\"0 0 100000 80000\">\n",
            "<rect width=\"100%\" height=\"100%\" fill=\"white\"/>\n",
            "<rect x=\"0\" y=\"0\" width=\"100000\" height=\"80000\" fill=\"none\" stroke=\"#000\"/>\n",
            "</svg>\n",
        );
        SheetDrawing {
            svg: svg.to_string(),
            model_units_per_mm: 10.0,
            scale_denominator,
            caption: String::new(),
        }
    }

    fn info() -> DrawingInfo {
        DrawingInfo {
            title: "FLOOR PLAN - LEVEL 1".into(),
            number: "A-101".into(),
            scale: "1:50".into(),
            date: "2026-06-08".into(),
            ..Default::default()
        }
    }

    #[test]
    fn arch_d_is_default_landscape() {
        let p = PaperSize::default();
        assert_eq!(p.name, "ARCH D");
        assert!(p.w_mm > p.h_mm);
    }

    #[test]
    fn sheet_has_paper_size_viewbox_and_title_block() {
        let (svg, _) = compose_sheet(
            &dummy_drawing(50.0),
            PaperSize::ARCH_D,
            &ProjectInfo { name: "Test House".into(), ..Default::default() },
            &info(),
        );
        assert!(svg.contains(r#"viewBox="0 0 914 610""#), "ARCH D page");
        assert!(svg.contains("FLOOR PLAN - LEVEL 1"));
        assert!(svg.contains("1 : 50"));
        assert!(svg.contains("Test House"));
        assert!(svg.ends_with("</svg>\n"));
        // The drawing's full-bleed white rect must be stripped.
        assert!(!svg.contains(r#"<rect width="100%" height="100%" fill="white"/>
<rect x="0" y="0" width="100000""#));
    }

    #[test]
    fn true_scale_sizing_is_correct() {
        // 10 m wide at 1:50 → 200 mm on paper.
        let (_, place) = compose_sheet(
            &dummy_drawing(50.0),
            PaperSize::ARCH_D,
            &ProjectInfo::default(),
            &info(),
        );
        assert!((place.content_w_mm - 200.0).abs() < 0.5, "w={}", place.content_w_mm);
        assert!((place.content_h_mm - 160.0).abs() < 0.5, "h={}", place.content_h_mm);
        assert!(!place.overflows, "10 m plan at 1:50 fits ARCH D");
    }

    #[test]
    fn overflow_is_flagged_when_scale_too_large() {
        // Same plan at 1:10 → 1000 mm wide, far past ARCH D's ~890 mm area.
        let (_, place) = compose_sheet(
            &dummy_drawing(10.0),
            PaperSize::ARCH_D,
            &ProjectInfo::default(),
            &info(),
        );
        assert!(place.overflows, "1:10 should overflow ARCH D");
    }

    #[test]
    fn title_block_sits_in_the_bottom_strip() {
        let (svg, _) = compose_sheet(
            &dummy_drawing(50.0),
            PaperSize::ARCH_D,
            &ProjectInfo::default(),
            &info(),
        );
        // The strip's top edge is at h - border - strip = 610 - 12 - 40 = 558.
        assert!(svg.contains(r#"y="558""#), "title strip not at expected y: {svg}");
    }
}
