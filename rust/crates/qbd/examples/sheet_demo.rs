//! Compose the floor plan onto an ARCH-D sheet at true 1:50 and write the SVG.
//! Empirical check for the sheet-layout system.
//!
//!     cargo run --release -p ls-qbd --example sheet_demo -- <building.json> <out.svg>

fn main() {
    let mut args = std::env::args().skip(1);
    let building = args.next().expect("usage: sheet_demo <building.json> <out.svg>");
    let out = args.next().expect("usage: sheet_demo <building.json> <out.svg>");

    let doc = archgeometry::parse_file(&building).expect("parse building.json");
    let project = drawing::ProjectInfo {
        name: "12 Test St, Toronto".into(),
        address: "Lot 7, Plan 42M-1234".into(),
        designer: "J. Smith".into(),
        designer_bcin: "BCIN 112233".into(),
        climate_zone: "Zone 6".into(),
        ..Default::default()
    };

    let (svg, place) = qbd::floor_plan_sheet(&doc, &project, 50.0, drawing::PaperSize::ARCH_D);
    std::fs::write(&out, &svg).expect("write svg");
    eprintln!(
        "wrote {out}: drawing {:.0} x {:.0} mm on paper, overflows={}",
        place.content_w_mm, place.content_h_mm, place.overflows,
    );
}
