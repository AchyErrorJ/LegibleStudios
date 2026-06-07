//! HTTP API surface (axum). Replaces the C++ `ipc_server` TCP service.
//!
//! Three routes today:
//! - `GET  /health`  — liveness probe; returns `{"status": "ok", ...}`.
//! - `POST /solve`   — questionnaire `Answers` JSON → building JSON.
//! - `POST /draw`    — building JSON → `Bundle { sheets, ifc?, validation? }`.
//!
//! The router is built by [`router`] so tests can drive it via
//! `tower::ServiceExt::oneshot` and the binary in `src/bin/server.rs`
//! can wrap it with a TCP listener.

use axum::{
    Json, Router,
    extract::Query,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::PathBuf;

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/// JSON body for `POST /draw`. The `building_id`/`walls`/`rooms`/… fields
/// match what [`solver::building_json`] emits, so a `/solve` response can
/// be fed straight back into `/draw`.
#[derive(Debug, Deserialize)]
pub struct DrawRequest {
    /// Raw building JSON as produced by `/solve`. We keep it as
    /// `serde_json::Value` so callers don't have to mirror the entire
    /// schema; the deeper parsing happens inside `archgeometry::parse_json`.
    #[serde(flatten)]
    pub building: serde_json::Value,
}

/// Query parameters for `/draw` — primarily controls which artifact set
/// the caller wants back.
#[derive(Debug, Default, Deserialize)]
pub struct DrawQuery {
    /// Project name baked into every title block. Defaults to `"API Project"`.
    #[serde(default)]
    pub project: Option<String>,
    /// Qualified-designer name. Empty → omitted from the title block.
    #[serde(default)]
    pub designer: Option<String>,
    /// BCIN / license number for the designer.
    #[serde(default)]
    pub bcin: Option<String>,
    /// When set, also include the IFC4 STEP file in the response.
    #[serde(default)]
    pub include_ifc: Option<bool>,
    /// When set, also include DXF geometry for floor plan + elevations.
    #[serde(default)]
    pub include_dxf: Option<bool>,
    /// When set, optionally point at an OBC library directory so the
    /// compliance report can be filled. Same shape as `qbd_dump --obc`.
    #[serde(default)]
    pub obc_dir: Option<PathBuf>,
}

/// Response body for `POST /draw`. `sheets` maps the canonical bundle
/// filename (`02_floor_plan.svg`, …) to its SVG string.
#[derive(Debug, Serialize)]
pub struct DrawResponse {
    pub project: String,
    pub generated_date: String,
    pub sheets: BTreeMap<String, String>,
    /// IFC4 STEP-file contents when `?include_ifc=true` was set.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ifc: Option<String>,
    /// DXF geometry files when `?include_dxf=true` was set.
    /// Keys are canonical filenames (`02_floor_plan.dxf`, …);
    /// values are ASCII DXF contents.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dxf: Option<BTreeMap<String, String>>,
    /// Compliance summary when an OBC library was loaded.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub validation: Option<ValidationSummary>,
}

/// Slim, JSON-friendly summary of [`qbd::ValidationResult`]. The full
/// `wall_reports` payload is intentionally omitted — clients that need
/// per-wall checks should pull them out of the compliance-report SVG.
#[derive(Debug, Serialize)]
pub struct ValidationSummary {
    pub overall_pass: bool,
    pub walls_checked: i32,
    pub walls_passed: i32,
    pub walls_failed: i32,
    pub thermal_compliance: bool,
    pub average_r_value: f32,
}

impl From<&qbd::ValidationResult> for ValidationSummary {
    fn from(v: &qbd::ValidationResult) -> Self {
        Self {
            overall_pass: v.overall_pass,
            walls_checked: v.walls_checked,
            walls_passed: v.walls_passed,
            walls_failed: v.walls_failed,
            thermal_compliance: v.thermal_compliance,
            average_r_value: v.average_r_value,
        }
    }
}

// ---------------------------------------------------------------------------
// Errors — translated to HTTP via `IntoResponse`
// ---------------------------------------------------------------------------

#[derive(Debug, thiserror::Error)]
pub enum ApiError {
    #[error("bad request: {0}")]
    BadRequest(String),
    #[error("internal error: {0}")]
    Internal(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, msg) = match &self {
            ApiError::BadRequest(m) => (StatusCode::BAD_REQUEST, m.clone()),
            ApiError::Internal(m) => (StatusCode::INTERNAL_SERVER_ERROR, m.clone()),
        };
        (status, Json(serde_json::json!({ "error": msg }))).into_response()
    }
}

// ---------------------------------------------------------------------------
// Router factory
// ---------------------------------------------------------------------------

/// Build the axum router. Kept as a free function (not bound to a port) so
/// tests can drive it directly via `tower::ServiceExt::oneshot`.
#[must_use]
pub fn router() -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/solve", post(solve))
        .route("/draw", post(draw))
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

async fn health() -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "ok",
        "service": "ls-api",
        "version": env!("CARGO_PKG_VERSION"),
    }))
}

async fn solve(Json(answers): Json<solver::Answers>) -> Result<Json<serde_json::Value>, ApiError> {
    let value = solver::building_json(&answers);
    if !value.get("success").and_then(|v| v.as_bool()).unwrap_or(false) {
        let reason = value
            .get("error")
            .and_then(|v| v.as_str())
            .unwrap_or("solver failed");
        return Err(ApiError::BadRequest(reason.to_string()));
    }
    Ok(Json(value))
}

async fn draw(
    Query(q): Query<DrawQuery>,
    Json(req): Json<DrawRequest>,
) -> Result<Json<DrawResponse>, ApiError> {
    // Parse the building JSON into the schema.
    let json_str = serde_json::to_string(&req.building)
        .map_err(|e| ApiError::BadRequest(format!("invalid building JSON: {e}")))?;
    let doc = archgeometry::parse_json(&json_str)
        .map_err(|e| ApiError::BadRequest(format!("schema parse: {e}")))?;

    // Optional OBC validation — drives the compliance-report sheet.
    let validation = if let Some(dir) = q.obc_dir.as_deref() {
        let mut engine = obc::OBCEngine::new();
        engine
            .initialize(dir)
            .map_err(|e| ApiError::Internal(format!("OBC init: {e}")))?;
        Some(qbd::validate_layout(&engine, &doc, "Zone 6"))
    } else {
        None
    };

    // Title-block identity from the query string.
    let project_name = q.project.unwrap_or_else(|| "API Project".to_string());
    let project_info = drawing::ProjectInfo {
        name: project_name.clone(),
        number: doc.building_id.clone(),
        solver: "QBD Layout".into(),
        designer: q.designer.unwrap_or_default(),
        designer_bcin: q.bcin.unwrap_or_default(),
        ..Default::default()
    };

    let docs = match &validation {
        Some(v) => qbd::generate_documentation_with_validation_for_project(&doc, project_info, v),
        None => qbd::generate_documentation_for_project(&doc, project_info),
    };

    let mut sheets: BTreeMap<String, String> = BTreeMap::new();
    let mut insert = |name: &str, svg: &str| {
        if !svg.is_empty() {
            sheets.insert(name.to_string(), svg.to_string());
        }
    };
    insert("01_site_plan.svg", &docs.site_plan_svg);
    insert("02_floor_plan.svg", &docs.floor_plan_svg);
    insert("04_section_aa.svg", &docs.section_svg);
    insert("05_door_schedule.svg", &docs.door_schedule_svg);
    insert("05_window_schedule.svg", &docs.window_schedule_svg);
    insert("06_roof_plan.svg", &docs.roof_plan_svg);
    insert("08_foundation_plan.svg", &docs.foundation_plan_svg);
    insert("09_compliance_report.svg", &docs.compliance_report_svg);
    insert("10_framing_plan.svg", &docs.framing_plan_svg);
    insert("11_footing_detail.svg", &docs.footing_detail_svg);
    for elev in &docs.elevations {
        let name = drawing::elevation_sheet_name(elev.direction);
        insert(&name, &elev.svg);
    }
    for (i, detail) in docs.wall_details.iter().enumerate() {
        let name = format!(
            "07_wall_detail_{:02}_{}.svg",
            i + 1,
            detail.detail.wall_type_id
        );
        insert(&name, &detail.svg);
    }

    let ifc = if q.include_ifc.unwrap_or(false) {
        Some(qbd::ifc::to_ifc(&doc, &project_name, &docs.generated_date))
    } else {
        None
    };

    let dxf = if q.include_dxf.unwrap_or(false) {
        let mut map: BTreeMap<String, String> = BTreeMap::new();
        if !docs.floor_plan_dxf.is_empty() {
            map.insert(
                "02_floor_plan.dxf".into(),
                String::from_utf8_lossy(&docs.floor_plan_dxf).into_owned(),
            );
        }
        for elev in &docs.elevations {
            if !elev.dxf.is_empty() {
                let name = drawing::elevation_sheet_name(elev.direction).replace(".svg", ".dxf");
                map.insert(name, String::from_utf8_lossy(&elev.dxf).into_owned());
            }
        }
        if map.is_empty() { None } else { Some(map) }
    } else {
        None
    };

    Ok(Json(DrawResponse {
        project: docs.project_name.clone(),
        generated_date: docs.generated_date.clone(),
        sheets,
        ifc,
        dxf,
        validation: validation.as_ref().map(ValidationSummary::from),
    }))
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::{Body, to_bytes};
    use axum::http::Request;
    use tower::ServiceExt;

    async fn json_body(resp: axum::response::Response) -> serde_json::Value {
        let bytes = to_bytes(resp.into_body(), usize::MAX).await.unwrap();
        serde_json::from_slice(&bytes).unwrap()
    }

    fn small_answers() -> solver::Answers {
        solver::Answers {
            bedrooms: 1,
            bathrooms: 1,
            sqft: 800.0,
            garage: "none".into(),
            storeys: 1,
            window_intent: "balanced".into(),
            style: "ranch".into(),
            ..Default::default()
        }
    }

    #[tokio::test]
    async fn health_returns_ok() {
        let app = router();
        let resp = app
            .oneshot(
                Request::builder()
                    .uri("/health")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let body = json_body(resp).await;
        assert_eq!(body["status"], "ok");
        assert_eq!(body["service"], "ls-api");
    }

    #[tokio::test]
    async fn solve_then_draw_round_trips_to_a_bundle() {
        let app = router();

        // /solve
        let answers = small_answers();
        let solve_req = Request::builder()
            .method("POST")
            .uri("/solve")
            .header("content-type", "application/json")
            .body(Body::from(serde_json::to_vec(&answers).unwrap()))
            .unwrap();
        let solve_resp = app.clone().oneshot(solve_req).await.unwrap();
        assert_eq!(solve_resp.status(), StatusCode::OK);
        let building = json_body(solve_resp).await;
        assert_eq!(building["success"], true);
        assert!(building["summary"]["total_walls"].as_u64().unwrap_or(0) > 0);

        // /draw — feed the building JSON straight back in.
        let draw_req = Request::builder()
            .method("POST")
            .uri("/draw?project=Smoke&designer=API+TEST&bcin=BCIN+99999")
            .header("content-type", "application/json")
            .body(Body::from(serde_json::to_vec(&building).unwrap()))
            .unwrap();
        let draw_resp = app.oneshot(draw_req).await.unwrap();
        assert_eq!(draw_resp.status(), StatusCode::OK);
        let bundle = json_body(draw_resp).await;
        assert_eq!(bundle["project"], "Smoke");
        // Core sheets must be present and SVG-shaped.
        let sheets = bundle["sheets"].as_object().expect("sheets is an object");
        assert!(sheets.contains_key("02_floor_plan.svg"));
        assert!(sheets.contains_key("08_foundation_plan.svg"));
        assert!(sheets.contains_key("11_footing_detail.svg"));
        for (name, svg) in sheets {
            let s = svg.as_str().unwrap_or("");
            // Some sheets emit a bare `<svg ...>` root (site plan, roof
            // plan, schedules); others start with the XML prolog. Accept
            // both — the only universal invariant is that every sheet
            // closes its root element.
            assert!(
                s.starts_with("<?xml") || s.starts_with("<svg"),
                "{name} doesn't look like SVG: starts with {:?}",
                &s[..s.len().min(30)],
            );
            assert!(s.contains("</svg>"), "{name} missing closing tag");
        }
        // Designer info should appear on the floor plan title block.
        let fp = sheets["02_floor_plan.svg"].as_str().unwrap();
        assert!(fp.contains("API TEST"), "designer should be on title block");
        assert!(fp.contains("BCIN 99999"));
        // No validation requested → omitted from the response.
        assert!(bundle.get("validation").is_none() || bundle["validation"].is_null());
        // No IFC requested → omitted.
        assert!(bundle.get("ifc").is_none() || bundle["ifc"].is_null());
    }

    #[tokio::test]
    async fn draw_with_include_ifc_returns_ifc_payload() {
        let app = router();
        let building = solver::building_json(&small_answers());
        let req = Request::builder()
            .method("POST")
            .uri("/draw?include_ifc=true")
            .header("content-type", "application/json")
            .body(Body::from(serde_json::to_vec(&building).unwrap()))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let bundle = json_body(resp).await;
        let ifc = bundle["ifc"].as_str().expect("ifc field must be a string");
        assert!(ifc.starts_with("ISO-10303-21;"));
        assert!(ifc.contains("FILE_SCHEMA(('IFC4'))"));
    }

    #[tokio::test]
    async fn solve_rejects_malformed_answers() {
        let app = router();
        // Not a JSON object at all.
        let req = Request::builder()
            .method("POST")
            .uri("/solve")
            .header("content-type", "application/json")
            .body(Body::from(b"not json".to_vec()))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        // axum's Json extractor rejects this with 400.
        assert!(
            resp.status() == StatusCode::BAD_REQUEST
                || resp.status() == StatusCode::UNPROCESSABLE_ENTITY,
            "expected 4xx, got {}",
            resp.status()
        );
    }

    #[tokio::test]
    async fn draw_with_empty_building_returns_minimal_bundle() {
        // `archgeometry::parse_json` is intentionally permissive: missing
        // fields default rather than erroring. Empty input is therefore a
        // valid (if uninteresting) building — the API just emits the
        // sheets that have content.
        let app = router();
        let req = Request::builder()
            .method("POST")
            .uri("/draw")
            .header("content-type", "application/json")
            .body(Body::from(b"{}".to_vec()))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let bundle = json_body(resp).await;
        // Whatever sheets render at all should still close cleanly.
        let sheets = bundle["sheets"].as_object().unwrap();
        for (name, svg) in sheets {
            let s = svg.as_str().unwrap();
            assert!(s.contains("</svg>"), "{name} missing </svg>");
        }
    }

    #[tokio::test]
    async fn draw_with_include_dxf_returns_dxf_payload() {
        let app = router();
        let building = solver::building_json(&small_answers());
        let req = Request::builder()
            .method("POST")
            .uri("/draw?include_dxf=true")
            .header("content-type", "application/json")
            .body(Body::from(serde_json::to_vec(&building).unwrap()))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let bundle = json_body(resp).await;
        let dxf_map = bundle["dxf"].as_object().expect("dxf field must be an object");
        assert!(dxf_map.contains_key("02_floor_plan.dxf"), "floor plan dxf missing");
        let fp = dxf_map["02_floor_plan.dxf"].as_str().unwrap();
        assert!(fp.contains("SECTION"), "DXF must contain SECTION");
        assert!(fp.contains("ENTITIES"), "DXF must contain ENTITIES");
        assert!(fp.contains("EOF"), "DXF must contain EOF");
        // At least one elevation DXF should be present.
        let elev_count = dxf_map
            .keys()
            .filter(|k| k.starts_with("03_elevation_"))
            .count();
        assert!(elev_count >= 1, "expected at least one elevation dxf");
    }

    #[tokio::test]
    async fn draw_rejects_unparseable_json_body() {
        // `Json` extractor itself rejects bytes that aren't valid JSON.
        let app = router();
        let req = Request::builder()
            .method("POST")
            .uri("/draw")
            .header("content-type", "application/json")
            .body(Body::from(b"not even json".to_vec()))
            .unwrap();
        let resp = app.oneshot(req).await.unwrap();
        assert!(resp.status().is_client_error(), "got {}", resp.status());
    }
}
