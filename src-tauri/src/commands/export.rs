/// Edeon Desktop — PDF Export Command
///
/// Generates a ranked compound summary report as an A4 PDF.
/// Layout: info header + table (Rank, Name, MW, LogP, TPSA,
///         Pesticide-likeness, Selectivity, Resistance, MPO Score).

use crate::AppState;
use crate::python::PythonEngine;
use chrono::Utc;
use printpdf::*;
use rusqlite::params;
use serde_json::Value;
use std::fs::File;
use std::io::BufWriter;
use tauri::State;

// ─── Layout constants (mm, f32; y=0 at page bottom) ─────────────────────────

const PAGE_W: f32 = 210.0;
const PAGE_H: f32 = 297.0;
const MARGIN_L: f32 = 15.0;
const MARGIN_B: f32 = 20.0;
const CONTENT_W: f32 = PAGE_W - MARGIN_L * 2.0; // 180 mm

const HEADER_ROW_H: f32 = 8.0;
const ROW_H: f32 = 7.0;
const FONT_SIZE_BODY: f32 = 7.5;
const FONT_SIZE_HEADER: f32 = 7.5;
const FONT_SIZE_TITLE: f32 = 14.0;
const FONT_SIZE_META: f32 = 9.0;

// Column x-offsets from MARGIN_L (cumulative widths)
const COL_X: [f32; 9] = [
    0.0,   // Rank      w=10
    10.0,  // Name      w=42
    52.0,  // MW        w=18
    70.0,  // LogP      w=16
    86.0,  // TPSA      w=16
    102.0, // Pest      w=22
    124.0, // Selec     w=22
    146.0, // Resist    w=20
    166.0, // MPO       w=14
];

const COL_HEADERS: [&str; 9] = [
    "#", "NAME", "MW", "LOGP", "TPSA",
    "PEST-LIKE", "SELECTIVITY", "RESISTANCE", "MPO",
];

// Brand colours (f32 RGB 0–1)
const GREEN_DARK: (f32, f32, f32) = (0.090, 0.204, 0.016); // #173404
const GREEN_LIGHT: (f32, f32, f32) = (0.878, 0.949, 0.867); // ~#e0f2dd
const WHITE: (f32, f32, f32) = (1.0, 1.0, 1.0);
const GREY_TEXT: (f32, f32, f32) = (0.102, 0.102, 0.102); // #1a1a1a
const GREY_LIGHT: (f32, f32, f32) = (0.918, 0.918, 0.910); // #ebebe8

// ─── Helpers ─────────────────────────────────────────────────────────────────

fn set_fill(layer: &PdfLayerReference, (r, g, b): (f32, f32, f32)) {
    layer.set_fill_color(Color::Rgb(Rgb::new(r, g, b, None)));
}

fn set_stroke(layer: &PdfLayerReference, (r, g, b): (f32, f32, f32)) {
    layer.set_outline_color(Color::Rgb(Rgb::new(r, g, b, None)));
}

/// Draw a filled (no stroke) rectangle. y_top is the top edge.
fn fill_rect(layer: &PdfLayerReference, x: f32, y_top: f32, w: f32, h: f32) {
    layer.add_polygon(Polygon {
        rings: vec![vec![
            (Point::new(Mm(x), Mm(y_top)), false),
            (Point::new(Mm(x + w), Mm(y_top)), false),
            (Point::new(Mm(x + w), Mm(y_top - h)), false),
            (Point::new(Mm(x), Mm(y_top - h)), false),
        ]],
        mode: PolygonMode::Fill,
        winding_order: WindingOrder::NonZero,
    });
}

/// Draw a horizontal stroke line.
fn draw_hline(layer: &PdfLayerReference, x1: f32, x2: f32, y: f32) {
    layer.add_line(Line {
        points: vec![
            (Point::new(Mm(x1), Mm(y)), false),
            (Point::new(Mm(x2), Mm(y)), false),
        ],
        is_closed: false,
    });
}

fn truncate_str(s: &str, max: usize) -> String {
    let chars: Vec<char> = s.chars().collect();
    if chars.len() <= max {
        s.to_string()
    } else {
        format!("{}…", chars[..max - 1].iter().collect::<String>())
    }
}

fn fmt_opt_f64(v: Option<f64>, decimals: usize) -> String {
    match v {
        Some(f) => format!("{:.prec$}", f, prec = decimals),
        None => "—".to_string(),
    }
}

fn json_str_val(v: &Value, key: &str) -> String {
    v.get(key)
        .and_then(|x| x.as_str())
        .unwrap_or("—")
        .to_string()
}

// ─── Table header row ────────────────────────────────────────────────────────

fn draw_table_header(layer: &PdfLayerReference, y_top: f32, font_bold: &IndirectFontRef) {
    set_fill(layer, GREEN_DARK);
    fill_rect(layer, MARGIN_L, y_top, CONTENT_W, HEADER_ROW_H);
    set_fill(layer, WHITE);
    let text_y = y_top - HEADER_ROW_H + 2.0;
    for (i, label) in COL_HEADERS.iter().enumerate() {
        layer.use_text(
            *label,
            FONT_SIZE_HEADER,
            Mm(MARGIN_L + COL_X[i] + 1.0),
            Mm(text_y),
            font_bold,
        );
    }
}

// ─── Main command ─────────────────────────────────────────────────────────────

#[tauri::command]
pub fn export_workflow_pdf(
    state: State<'_, AppState>,
    workflow_id: String,
    output_path: String,
) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    // 1. Workflow + project metadata
    let (workflow_name, project_name, completed_at_raw, template_id) = db
        .query_row(
            "SELECT w.name, p.name, w.completed_at, w.workflow_id
             FROM workflows w
             JOIN projects p ON w.project_id = p.id
             WHERE w.id = ?1",
            params![workflow_id],
            |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, Option<String>>(2)?,
                    row.get::<_, Option<String>>(3)?,
                ))
            },
        )
        .map_err(|e| format!("Workflow not found: {}", e))?;

    // If it's a standard template-based workflow, route report rendering to Python's WeasyPrint engine
    let is_template_workflow = match template_id.as_deref() {
        Some("registration_readiness") |
        Some("pollinator_safety") |
        Some("tp_liability") |
        Some("lead_optimization") |
        Some("hit_triage") |
        Some("comparative_benchmarking") |
        Some("selectivity_optimization") |
        Some("scaffold_hop") => true,
        _ => false,
    };

    if is_template_workflow {
        // Fetch all compound results for this workflow run
        let mut per_compound = Vec::new();
        let mut stmt = db
            .prepare(
                "SELECT results_json FROM workflow_results WHERE workflow_id = ?1"
            )
            .map_err(|e| e.to_string())?;
        
        let rows = stmt
            .query_map(params![workflow_id], |r| r.get::<_, String>(0))
            .map_err(|e| e.to_string())?;
        
        for row in rows {
            let json_str = row.map_err(|e| e.to_string())?;
            let val: Value = serde_json::from_str(&json_str).map_err(|e| e.to_string())?;
            per_compound.push(val);
        }

        // Fetch the workflow's verdict and provenance json
        let (verdict_str, provenance_str) = db
            .query_row(
                "SELECT verdict_json, provenance_json FROM workflows WHERE id = ?1",
                params![workflow_id],
                |row| {
                    Ok((
                        row.get::<_, Option<String>>(0)?,
                        row.get::<_, Option<String>>(1)?,
                    ))
                },
            )
            .map_err(|e| e.to_string())?;

        let verdict_val: Value = verdict_str
            .as_deref()
            .and_then(|s| serde_json::from_str(s).ok())
            .unwrap_or(serde_json::json!({}));

        let provenance_val: Value = provenance_str
            .as_deref()
            .and_then(|s| serde_json::from_str(s).ok())
            .unwrap_or(serde_json::json!({}));

        // Reconstruct the WorkflowResult JSON for Python
        let result_payload = serde_json::json!({
            "result": {
                "workflow_id": template_id.unwrap_or_default(),
                "overall": verdict_val.get("overall"),
                "sections": verdict_val.get("sections"),
                "warnings": verdict_val.get("warnings"),
                "provenance": provenance_val,
                "per_compound": per_compound
            },
            "output_path": output_path,
            "format": "pdf"
        });

        // Call the Python engine RPC
        let mut engine = {
            let mut py = state.python.lock().map_err(|e| e.to_string())?;
            if py.is_none() {
                *py = Some(PythonEngine::spawn()?);
            }
            py.take().ok_or("Python engine not available")?
        };

        let result = engine.send_request("export_dossier", result_payload);

        // Put Python engine back
        {
            let mut py = state.python.lock().map_err(|e| e.to_string())?;
            *py = Some(engine);
        }

        let val = result?;
        // Check if there was an error in the RPC result
        if let Some(err) = val.get("error").and_then(|e| e.as_str()) {
            return Err(err.to_string());
        }
        return Ok(());
    }

    // 2. Ranked compound results
    let mut stmt = db
        .prepare(
            "SELECT c.name, c.mol_weight, c.logp, c.tpsa, wr.results_json, wr.score
             FROM workflow_results wr
             JOIN compounds c ON wr.compound_id = c.id
             WHERE wr.workflow_id = ?1
             ORDER BY wr.score DESC",
        )
        .map_err(|e| e.to_string())?;

    struct Row {
        name: String,
        mw: Option<f64>,
        logp: Option<f64>,
        tpsa: Option<f64>,
        results: Value,
        score: Option<f64>,
    }

    let rows: Vec<Row> = stmt
        .query_map(params![workflow_id], |row| {
            let json_str: Option<String> = row.get(4)?;
            let results = json_str
                .as_deref()
                .and_then(|s| serde_json::from_str(s).ok())
                .unwrap_or(Value::Object(Default::default()));
            Ok(Row {
                name: row.get(0)?,
                mw: row.get(1)?,
                logp: row.get(2)?,
                tpsa: row.get(3)?,
                results,
                score: row.get(5)?,
            })
        })
        .map_err(|e| e.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;

    let n_compounds = rows.len();
    let now_str = Utc::now().format("%Y-%m-%d").to_string();
    let generated = completed_at_raw
        .as_deref()
        .and_then(|s| s.get(..10))
        .unwrap_or(now_str.as_str());

    // 3. Build PDF
    let (doc, page1, layer1) =
        PdfDocument::new("Edeon Workflow Report", Mm(PAGE_W), Mm(PAGE_H), "Main");

    let font = doc
        .add_builtin_font(BuiltinFont::Helvetica)
        .map_err(|e| e.to_string())?;
    let font_bold = doc
        .add_builtin_font(BuiltinFont::HelveticaBold)
        .map_err(|e| e.to_string())?;

    let mut current_page = page1;
    let mut current_layer_idx = layer1;

    macro_rules! layer {
        () => {
            doc.get_page(current_page).get_layer(current_layer_idx)
        };
    }

    // ─── Info header (first page) ───────────────────────────────────────
    let lyr = layer!();

    // Branding strip
    set_fill(&lyr, GREEN_DARK);
    fill_rect(&lyr, MARGIN_L, PAGE_H - 10.0, CONTENT_W, 12.0);

    set_fill(&lyr, WHITE);
    lyr.use_text(
        "EDEON DESKTOP",
        FONT_SIZE_TITLE,
        Mm(MARGIN_L + 1.0),
        Mm(PAGE_H - 19.0),
        &font_bold,
    );
    lyr.use_text(
        "Workflow Analysis Report",
        FONT_SIZE_META,
        Mm(MARGIN_L + 110.0),
        Mm(PAGE_H - 19.0),
        &font,
    );

    set_fill(&lyr, GREY_TEXT);
    let meta_y_start = PAGE_H - 30.0;
    for (i, line) in [
        format!("Project:    {}", project_name),
        format!("Workflow:   {}", workflow_name),
        format!("Generated:  {}  ·  {} compounds", generated, n_compounds),
    ]
    .iter()
    .enumerate()
    {
        lyr.use_text(
            line.as_str(),
            FONT_SIZE_META,
            Mm(MARGIN_L + 1.0),
            Mm(meta_y_start - i as f32 * 7.0),
            &font,
        );
    }

    // Divider
    set_stroke(&lyr, GREEN_DARK);
    lyr.set_outline_thickness(0.5);
    draw_hline(&lyr, MARGIN_L, PAGE_W - MARGIN_L, PAGE_H - 52.0);

    // ─── Table ──────────────────────────────────────────────────────────
    let first_table_top = PAGE_H - 56.0;
    draw_table_header(&lyr, first_table_top, &font_bold);

    let mut y_cursor = first_table_top - HEADER_ROW_H;

    for (rank, row) in rows.iter().enumerate() {
        // Page break
        if y_cursor - ROW_H < MARGIN_B {
            let (new_page, new_layer) = doc.add_page(Mm(PAGE_W), Mm(PAGE_H), "Main");
            current_page = new_page;
            current_layer_idx = new_layer;
            let lyr = layer!();
            let table_top = PAGE_H - 15.0;
            draw_table_header(&lyr, table_top, &font_bold);
            y_cursor = table_top - HEADER_ROW_H;
        }

        let lyr = layer!();

        // Alternating row tint
        if rank % 2 == 1 {
            set_fill(&lyr, GREEN_LIGHT);
            fill_rect(&lyr, MARGIN_L, y_cursor, CONTENT_W, ROW_H);
        }

        // Extract science values
        let pest = json_str_val(&row.results, "pesticide_likeness");
        let sel_level = row
            .results
            .get("selectivity")
            .and_then(|s| s.get("overall_level"))
            .and_then(|v| v.as_str())
            .unwrap_or("—")
            .to_string();
        let res_level = row
            .results
            .get("resistance")
            .and_then(|r| r.get("level"))
            .and_then(|v| v.as_str())
            .unwrap_or("—")
            .to_string();

        let text_y = y_cursor - ROW_H + 1.8;
        set_fill(&lyr, GREY_TEXT);

        let cells: [String; 9] = [
            format!("{}", rank + 1),
            truncate_str(&row.name, 22),
            fmt_opt_f64(row.mw, 1),
            fmt_opt_f64(row.logp, 2),
            fmt_opt_f64(row.tpsa, 1),
            pest,
            sel_level,
            res_level,
            fmt_opt_f64(row.score, 2),
        ];

        for (i, cell) in cells.iter().enumerate() {
            lyr.use_text(
                cell.as_str(),
                FONT_SIZE_BODY,
                Mm(MARGIN_L + COL_X[i] + 1.0),
                Mm(text_y),
                &font,
            );
        }

        // Row separator
        set_stroke(&lyr, GREY_LIGHT);
        lyr.set_outline_thickness(0.2);
        draw_hline(&lyr, MARGIN_L, PAGE_W - MARGIN_L, y_cursor - ROW_H);

        y_cursor -= ROW_H;
    }

    // Footer on last page
    {
        let lyr = layer!();
        set_fill(&lyr, GREY_TEXT);
        lyr.use_text(
            "Generated by Edeon Desktop",
            7.0,
            Mm(MARGIN_L),
            Mm(12.0),
            &font,
        );
    }

    // 4. Write file
    let file = File::create(&output_path).map_err(|e| format!("Cannot create file: {}", e))?;
    doc.save(&mut BufWriter::new(file))
        .map_err(|e| format!("PDF save failed: {}", e))?;

    Ok(())
}

#[tauri::command]
pub fn export_environmental_dossier(
    state: State<'_, AppState>,
    workflow_id: String,
    output_path: String,
) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    // 1. Metadata
    let (workflow_name, project_name, completed_at_raw) = db
        .query_row(
            "SELECT w.name, p.name, w.completed_at
             FROM workflows w
             JOIN projects p ON w.project_id = p.id
             WHERE w.id = ?1",
            params![workflow_id],
            |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, Option<String>>(2)?,
                ))
            },
        )
        .map_err(|e| format!("Workflow not found: {}", e))?;

    // 2. Results
    let mut stmt = db
        .prepare(
            "SELECT c.name, c.mol_weight, c.logp, wr.results_json, wr.score
             FROM workflow_results wr
             JOIN compounds c ON wr.compound_id = c.id
             WHERE wr.workflow_id = ?1
             ORDER BY wr.score DESC",
        )
        .map_err(|e| e.to_string())?;

    struct Row {
        name: String,
        #[allow(dead_code)]
        mw: Option<f64>,
        logp: Option<f64>,
        results: Value,
        score: Option<f64>,
    }

    let rows: Vec<Row> = stmt
        .query_map(params![workflow_id], |row| {
            let json_str: Option<String> = row.get(3)?;
            let results = json_str
                .as_deref()
                .and_then(|s| serde_json::from_str(s).ok())
                .unwrap_or(Value::Object(Default::default()));
            Ok(Row {
                name: row.get(0)?,
                mw: row.get(1)?,
                logp: row.get(2)?,
                results,
                score: row.get(4)?,
            })
        })
        .map_err(|e| e.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;

    let n_compounds = rows.len();
    let now_str = Utc::now().format("%Y-%m-%d").to_string();
    let generated = completed_at_raw
        .as_deref()
        .and_then(|s| s.get(..10))
        .unwrap_or(now_str.as_str());

    // 3. Build PDF
    let (doc, page1, layer1) =
        PdfDocument::new("Edeon Environmental Dossier", Mm(PAGE_W), Mm(PAGE_H), "Main");

    let font = doc
        .add_builtin_font(BuiltinFont::Helvetica)
        .map_err(|e| e.to_string())?;
    let font_bold = doc
        .add_builtin_font(BuiltinFont::HelveticaBold)
        .map_err(|e| e.to_string())?;

    let mut current_page = page1;
    let mut current_layer_idx = layer1;

    macro_rules! layer {
        () => {
            doc.get_page(current_page).get_layer(current_layer_idx)
        };
    }

    let lyr = layer!();

    // Branding header
    set_fill(&lyr, GREEN_DARK);
    fill_rect(&lyr, MARGIN_L, PAGE_H - 10.0, CONTENT_W, 12.0);

    set_fill(&lyr, WHITE);
    lyr.use_text(
        "EDEON ENVIRONMENTAL & BEE SAFETY DOSSIER",
        11.0,
        Mm(MARGIN_L + 1.0),
        Mm(PAGE_H - 18.0),
        &font_bold,
    );
    lyr.use_text(
        "Ecotoxicology Assessment Sheet",
        FONT_SIZE_META,
        Mm(MARGIN_L + 130.0),
        Mm(PAGE_H - 18.0),
        &font,
    );

    set_fill(&lyr, GREY_TEXT);
    let meta_y_start = PAGE_H - 30.0;
    for (i, line) in [
        format!("Project:    {}", project_name),
        format!("Workflow:   {}", workflow_name),
        format!("Generated:  {}  ·  {} compounds assessed", generated, n_compounds),
    ]
    .iter()
    .enumerate()
    {
        lyr.use_text(
            line.as_str(),
            FONT_SIZE_META,
            Mm(MARGIN_L + 1.0),
            Mm(meta_y_start - i as f32 * 7.0),
            &font,
        );
    }

    // Divider
    set_stroke(&lyr, GREEN_DARK);
    lyr.set_outline_thickness(0.5);
    draw_hline(&lyr, MARGIN_L, PAGE_W - MARGIN_L, PAGE_H - 52.0);

    // Environmental Table Header
    let first_table_top = PAGE_H - 56.0;
    set_fill(&lyr, GREEN_DARK);
    fill_rect(&lyr, MARGIN_L, first_table_top, CONTENT_W, HEADER_ROW_H);
    set_fill(&lyr, WHITE);
    let text_y = first_table_top - HEADER_ROW_H + 2.0;

    let headers = ["#", "NAME", "LOGP", "BEE RISK", "FISH RISK", "BIRD RISK", "MAMMAL RISK", "PERSISTENCE", "SCORE"];
    // custom offsets
    let offsets = [0.0, 10.0, 45.0, 60.0, 80.0, 102.0, 124.0, 148.0, 168.0];

    for (i, label) in headers.iter().enumerate() {
        lyr.use_text(
            *label,
            6.5,
            Mm(MARGIN_L + offsets[i] + 1.0),
            Mm(text_y),
            &font_bold,
        );
    }

    let mut y_cursor = first_table_top - HEADER_ROW_H;

    for (rank, row) in rows.iter().enumerate() {
        if y_cursor - ROW_H < MARGIN_B {
            let (new_page, new_layer) = doc.add_page(Mm(PAGE_W), Mm(PAGE_H), "Main");
            current_page = new_page;
            current_layer_idx = new_layer;
            let lyr = layer!();
            let table_top = PAGE_H - 15.0;
            
            set_fill(&lyr, GREEN_DARK);
            fill_rect(&lyr, MARGIN_L, table_top, CONTENT_W, HEADER_ROW_H);
            set_fill(&lyr, WHITE);
            let text_y = table_top - HEADER_ROW_H + 2.0;
            for (i, label) in headers.iter().enumerate() {
                lyr.use_text(
                    *label,
                    6.5,
                    Mm(MARGIN_L + offsets[i] + 1.0),
                    Mm(text_y),
                    &font_bold,
                );
            }
            y_cursor = table_top - HEADER_ROW_H;
        }

        let lyr = layer!();

        if rank % 2 == 1 {
            set_fill(&lyr, GREEN_LIGHT);
            fill_rect(&lyr, MARGIN_L, y_cursor, CONTENT_W, ROW_H);
        }

        // Toxicity Predictions
        let tox_preds = row.results.get("toxicity").and_then(|t| t.get("predictions"));
        let mut bee = "Low".to_string();
        let mut fish = "Low".to_string();
        let mut bird = "Low".to_string();
        let mut mammal = "Low".to_string();

        if let Some(preds) = tox_preds.and_then(|p| p.as_array()) {
            for pred in preds {
                if let (Some(org), Some(lvl)) = (pred.get("organism").and_then(|o| o.as_str()), pred.get("level").and_then(|l| l.as_str())) {
                    if org.contains("Bee") { bee = lvl.to_string(); }
                    else if org.contains("Fish") { fish = lvl.to_string(); }
                    else if org.contains("Bird") { bird = lvl.to_string(); }
                    else if org.contains("Mammal") { mammal = lvl.to_string(); }
                }
            }
        }

        // Persistence heuristic based on LogP/TPSA
        let persistence = if row.logp.unwrap_or(0.0) > 4.0 {
            "High Persistence"
        } else if row.logp.unwrap_or(0.0) > 2.0 {
            "Moderate"
        } else {
            "Rapid Degradation"
        };

        let text_y = y_cursor - ROW_H + 1.8;
        set_fill(&lyr, GREY_TEXT);

        let cells = [
            format!("{}", rank + 1),
            truncate_str(&row.name, 18),
            fmt_opt_f64(row.logp, 2),
            bee,
            fish,
            bird,
            mammal,
            persistence.to_string(),
            fmt_opt_f64(row.score, 2),
        ];

        for (i, cell) in cells.iter().enumerate() {
            lyr.use_text(
                cell.as_str(),
                FONT_SIZE_BODY,
                Mm(MARGIN_L + offsets[i] + 1.0),
                Mm(text_y),
                &font,
            );
        }

        set_stroke(&lyr, GREY_LIGHT);
        lyr.set_outline_thickness(0.2);
        draw_hline(&lyr, MARGIN_L, PAGE_W - MARGIN_L, y_cursor - ROW_H);

        y_cursor -= ROW_H;
    }

    // 4. Decision Journal Audit Trail
    let project_id: String = db.query_row(
        "SELECT project_id FROM workflows WHERE id = ?1",
        params![workflow_id],
        |r| r.get(0),
    ).unwrap_or_default();

    let journal_rows: Vec<(String, String, String, String)> = if !project_id.is_empty() {
        let mut stmt = db.prepare(
            "SELECT created_at, actor, decision_kind, summary FROM decision_journal WHERE project_id = ?1 ORDER BY created_at ASC LIMIT 50"
        ).map_err(|e| e.to_string())?;
        let rows = stmt.query_map(params![project_id], |r| {
            Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?))
        }).map_err(|e| e.to_string())?;
        rows.collect::<Result<Vec<_>, _>>().unwrap_or_default()
    } else {
        Vec::new()
    };

    if !journal_rows.is_empty() {
        let (new_page, new_layer) = doc.add_page(Mm(PAGE_W), Mm(PAGE_H), "Main");
        current_page = new_page;
        current_layer_idx = new_layer;
        let lyr = layer!();

        set_fill(&lyr, GREEN_DARK);
        fill_rect(&lyr, MARGIN_L, PAGE_H - 10.0, CONTENT_W, 12.0);

        set_fill(&lyr, WHITE);
        lyr.use_text(
            "DECISION JOURNAL AUDIT TRAIL",
            11.0,
            Mm(MARGIN_L + 1.0),
            Mm(PAGE_H - 18.0),
            &font_bold,
        );

        let table_top = PAGE_H - 30.0;
        set_fill(&lyr, GREEN_DARK);
        fill_rect(&lyr, MARGIN_L, table_top, CONTENT_W, HEADER_ROW_H);
        set_fill(&lyr, WHITE);
        let text_y = table_top - HEADER_ROW_H + 2.0;

        let j_headers = ["TIMESTAMP", "ACTOR", "KIND", "SUMMARY"];
        let j_offsets = [0.0, 45.0, 65.0, 105.0];
        for (i, label) in j_headers.iter().enumerate() {
            lyr.use_text(
                *label,
                6.5,
                Mm(MARGIN_L + j_offsets[i] + 1.0),
                Mm(text_y),
                &font_bold,
            );
        }

        let mut j_y_cursor = table_top - HEADER_ROW_H;
        for (idx, (created_at, actor, kind, summary)) in journal_rows.iter().enumerate() {
            if j_y_cursor - ROW_H < MARGIN_B {
                let (np, nl) = doc.add_page(Mm(PAGE_W), Mm(PAGE_H), "Main");
                current_page = np;
                current_layer_idx = nl;
                let lyr = layer!();
                let table_top = PAGE_H - 15.0;
                set_fill(&lyr, GREEN_DARK);
                fill_rect(&lyr, MARGIN_L, table_top, CONTENT_W, HEADER_ROW_H);
                set_fill(&lyr, WHITE);
                let text_y = table_top - HEADER_ROW_H + 2.0;
                for (i, label) in j_headers.iter().enumerate() {
                    lyr.use_text(*label, 6.5, Mm(MARGIN_L + j_offsets[i] + 1.0), Mm(text_y), &font_bold);
                }
                j_y_cursor = table_top - HEADER_ROW_H;
            }

            let lyr = layer!();
            if idx % 2 == 1 {
                set_fill(&lyr, GREEN_LIGHT);
                fill_rect(&lyr, MARGIN_L, j_y_cursor, CONTENT_W, ROW_H);
            }

            let text_y = j_y_cursor - ROW_H + 1.8;
            set_fill(&lyr, GREY_TEXT);

            let time_short = truncate_str(created_at, 19);
            let summary_trunc = truncate_str(summary, 45);

            let j_cells = [time_short, actor.clone(), kind.clone(), summary_trunc];
            for (i, cell) in j_cells.iter().enumerate() {
                lyr.use_text(
                    cell.as_str(),
                    FONT_SIZE_BODY,
                    Mm(MARGIN_L + j_offsets[i] + 1.0),
                    Mm(text_y),
                    &font,
                );
            }

            set_stroke(&lyr, GREY_LIGHT);
            lyr.set_outline_thickness(0.2);
            draw_hline(&lyr, MARGIN_L, PAGE_W - MARGIN_L, j_y_cursor - ROW_H);

            j_y_cursor -= ROW_H;
        }
    }

    // Footer
    {
        let lyr = layer!();
        set_fill(&lyr, GREY_TEXT);
        lyr.use_text(
            "Regulatory Pre-screening Ecotox Dossier · Edeon Agrochemicals",
            7.0,
            Mm(MARGIN_L),
            Mm(12.0),
            &font,
        );
    }

    let file = File::create(&output_path).map_err(|e| format!("Cannot create file: {}", e))?;
    doc.save(&mut BufWriter::new(file))
        .map_err(|e| format!("PDF save failed: {}", e))?;

    Ok(())
}

#[tauri::command]
pub fn export_selectivity_chartbook(
    state: State<'_, AppState>,
    workflow_id: String,
    output_path: String,
) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    // 1. Metadata
    let (workflow_name, project_name, completed_at_raw) = db
        .query_row(
            "SELECT w.name, p.name, w.completed_at
             FROM workflows w
             JOIN projects p ON w.project_id = p.id
             WHERE w.id = ?1",
            params![workflow_id],
            |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, Option<String>>(2)?,
                ))
            },
        )
        .map_err(|e| format!("Workflow not found: {}", e))?;

    // 2. Results
    let mut stmt = db
        .prepare(
            "SELECT c.name, wr.results_json, wr.score
             FROM workflow_results wr
             JOIN compounds c ON wr.compound_id = c.id
             WHERE wr.workflow_id = ?1
             ORDER BY wr.score DESC",
        )
        .map_err(|e| e.to_string())?;

    struct Row {
        name: String,
        results: Value,
        score: Option<f64>,
    }

    let rows: Vec<Row> = stmt
        .query_map(params![workflow_id], |row| {
            let json_str: Option<String> = row.get(1)?;
            let results = json_str
                .as_deref()
                .and_then(|s| serde_json::from_str(s).ok())
                .unwrap_or(Value::Object(Default::default()));
            Ok(Row {
                name: row.get(0)?,
                results,
                score: row.get(2)?,
            })
        })
        .map_err(|e| e.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;

    let n_compounds = rows.len();
    let now_str = Utc::now().format("%Y-%m-%d").to_string();
    let generated = completed_at_raw
        .as_deref()
        .and_then(|s| s.get(..10))
        .unwrap_or(now_str.as_str());

    // 3. Build PDF
    let (doc, page1, layer1) =
        PdfDocument::new("Edeon Selectivity Chartbook", Mm(PAGE_W), Mm(PAGE_H), "Main");

    let font = doc
        .add_builtin_font(BuiltinFont::Helvetica)
        .map_err(|e| e.to_string())?;
    let font_bold = doc
        .add_builtin_font(BuiltinFont::HelveticaBold)
        .map_err(|e| e.to_string())?;

    let mut current_page = page1;
    let mut current_layer_idx = layer1;

    macro_rules! layer {
        () => {
            doc.get_page(current_page).get_layer(current_layer_idx)
        };
    }

    let lyr = layer!();

    // Branding header
    set_fill(&lyr, GREEN_DARK);
    fill_rect(&lyr, MARGIN_L, PAGE_H - 10.0, CONTENT_W, 12.0);

    set_fill(&lyr, WHITE);
    lyr.use_text(
        "EDEON OFF-TARGET SPECIES SELECTIVITY CHARTBOOK",
        10.5,
        Mm(MARGIN_L + 1.0),
        Mm(PAGE_H - 18.0),
        &font_bold,
    );
    lyr.use_text(
        "Target vs Indicator Organism safety ratios",
        FONT_SIZE_META,
        Mm(MARGIN_L + 130.0),
        Mm(PAGE_H - 18.0),
        &font,
    );

    set_fill(&lyr, GREY_TEXT);
    let meta_y_start = PAGE_H - 30.0;
    for (i, line) in [
        format!("Project:    {}", project_name),
        format!("Workflow:   {}", workflow_name),
        format!("Generated:  {}  ·  {} compounds assessed", generated, n_compounds),
    ]
    .iter()
    .enumerate()
    {
        lyr.use_text(
            line.as_str(),
            FONT_SIZE_META,
            Mm(MARGIN_L + 1.0),
            Mm(meta_y_start - i as f32 * 7.0),
            &font,
        );
    }

    // Divider
    set_stroke(&lyr, GREEN_DARK);
    lyr.set_outline_thickness(0.5);
    draw_hline(&lyr, MARGIN_L, PAGE_W - MARGIN_L, PAGE_H - 52.0);

    // Selectivity Table Header
    let first_table_top = PAGE_H - 56.0;
    set_fill(&lyr, GREEN_DARK);
    fill_rect(&lyr, MARGIN_L, first_table_top, CONTENT_W, HEADER_ROW_H);
    set_fill(&lyr, WHITE);
    let text_y = first_table_top - HEADER_ROW_H + 2.0;

    let headers = ["#", "NAME", "BEE", "WORM", "FISH", "BIRD", "DAPHNIA", "MAMMAL", "LEVEL", "SCORE"];
    // custom offsets (10 columns, fits content width 180)
    let offsets = [0.0, 8.0, 36.0, 52.0, 70.0, 88.0, 106.0, 126.0, 146.0, 166.0];

    for (i, label) in headers.iter().enumerate() {
        lyr.use_text(
            *label,
            6.5,
            Mm(MARGIN_L + offsets[i] + 1.0),
            Mm(text_y),
            &font_bold,
        );
    }

    let mut y_cursor = first_table_top - HEADER_ROW_H;

    for (rank, row) in rows.iter().enumerate() {
        if y_cursor - ROW_H < MARGIN_B {
            let (new_page, new_layer) = doc.add_page(Mm(PAGE_W), Mm(PAGE_H), "Main");
            current_page = new_page;
            current_layer_idx = new_layer;
            let lyr = layer!();
            let table_top = PAGE_H - 15.0;
            
            set_fill(&lyr, GREEN_DARK);
            fill_rect(&lyr, MARGIN_L, table_top, CONTENT_W, HEADER_ROW_H);
            set_fill(&lyr, WHITE);
            let text_y = table_top - HEADER_ROW_H + 2.0;
            for (i, label) in headers.iter().enumerate() {
                lyr.use_text(
                    *label,
                    6.5,
                    Mm(MARGIN_L + offsets[i] + 1.0),
                    Mm(text_y),
                    &font_bold,
                );
            }
            y_cursor = table_top - HEADER_ROW_H;
        }

        let lyr = layer!();

        if rank % 2 == 1 {
            set_fill(&lyr, GREEN_LIGHT);
            fill_rect(&lyr, MARGIN_L, y_cursor, CONTENT_W, ROW_H);
        }

        // Selectivity profiles
        let profiles = row.results.get("selectivity").and_then(|s| s.get("profiles"));
        let mut bee = "1.0x".to_string();
        let mut worm = "1.0x".to_string();
        let mut fish = "1.0x".to_string();
        let mut bird = "1.0x".to_string();
        let mut daphnia = "1.0x".to_string();
        let mut mammal = "1.0x".to_string();

        if let Some(list) = profiles.and_then(|p| p.as_array()) {
            for entry in list {
                if let (Some(org), Some(idx)) = (entry.get("organism").and_then(|o| o.as_str()), entry.get("selectivity_index")) {
                    let idx_str = match idx.as_f64() {
                        Some(f) => format!("{:.1}x", f),
                        None => "1.0x".to_string(),
                    };
                    if org.contains("Bee") { bee = idx_str; }
                    else if org.contains("Earthworm") { worm = idx_str; }
                    else if org.contains("Fish") { fish = idx_str; }
                    else if org.contains("Bird") { bird = idx_str; }
                    else if org.contains("Daphnia") { daphnia = idx_str; }
                    else if org.contains("Mammal") { mammal = idx_str; }
                }
            }
        }

        let overall = row.results.get("selectivity").and_then(|s| s.get("overall_level")).and_then(|o| o.as_str()).unwrap_or("Moderate");

        let text_y = y_cursor - ROW_H + 1.8;
        set_fill(&lyr, GREY_TEXT);

        let cells = [
            format!("{}", rank + 1),
            truncate_str(&row.name, 14),
            bee,
            worm,
            fish,
            bird,
            daphnia,
            mammal,
            overall.to_string(),
            fmt_opt_f64(row.score, 2),
        ];

        for (i, cell) in cells.iter().enumerate() {
            lyr.use_text(
                cell.as_str(),
                FONT_SIZE_BODY,
                Mm(MARGIN_L + offsets[i] + 1.0),
                Mm(text_y),
                &font,
            );
        }

        set_stroke(&lyr, GREY_LIGHT);
        lyr.set_outline_thickness(0.2);
        draw_hline(&lyr, MARGIN_L, PAGE_W - MARGIN_L, y_cursor - ROW_H);

        y_cursor -= ROW_H;
    }

    // Footer
    {
        let lyr = layer!();
        set_fill(&lyr, GREY_TEXT);
        lyr.use_text(
            "Target vs Non-Target Selectivity Indices · Edeon Agrochemicals",
            7.0,
            Mm(MARGIN_L),
            Mm(12.0),
            &font,
        );
    }

    let file = File::create(&output_path).map_err(|e| format!("Cannot create file: {}", e))?;
    doc.save(&mut BufWriter::new(file))
        .map_err(|e| format!("PDF save failed: {}", e))?;

    Ok(())
}

