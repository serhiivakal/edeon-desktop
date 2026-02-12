import os
import sys
import yaml
import math
import numpy as np
import matplotlib
matplotlib.use('Agg') # Headless rendering
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon, Rectangle
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ValidationError

# Add python to sys.path to resolve edeon_models and edeon_engine
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from edeon_models import build_default_registry, Endpoint
from edeon_models.types import ADStatus, Prediction, PredictionValue
from edeon_engine.workflows.runner import run_workflow
from edeon_engine.regulatory.alerts import screen_structural_alerts

# Pydantic Schemas for YAML Validation
class MeasuredValue(BaseModel):
    value: float
    units: str
    source: str
    reference: str

class RegulatoryStatus(BaseModel):
    eu_1107_2009: Optional[str] = None
    us_epa: Optional[str] = None
    brazil: Optional[str] = None

class ReferenceCompound(BaseModel):
    id: str
    name: str
    chembl_id: str
    cas: str
    smiles_canonical: str
    class_: str = Field(alias="class")
    class_subtype: str
    irac_group: Optional[str] = None
    hrac_group: Optional[str] = None
    frac_group: Optional[str] = None
    measured_values: Dict[str, MeasuredValue]
    regulatory_status: RegulatoryStatus

class ReferenceManifest(BaseModel):
    reference_compounds: List[ReferenceCompound]


# Colors for visual excellence
COLOR_GREEN_FILL = "#E8F5E9"
COLOR_GREEN_BORDER = "#2E7D32"
COLOR_YELLOW_FILL = "#FFF3E0"
COLOR_YELLOW_BORDER = "#E65100"
COLOR_RED_FILL = "#FFEBEE"
COLOR_RED_BORDER = "#C62828"
COLOR_GREY_FILL = "#F5F5F5"
COLOR_GREY_BORDER = "#757575"

# Matplotlib Honeycomb Plotter
def plot_honeycomb(compound_name: str, predictions: Dict[str, Prediction], output_path: Path):
    """Renders a point-topped staggered 10-hexagon layout for ecotox/fate endpoints."""
    # Group logically: Row 0 (Aquatic), Row 1 (Terrestrial/Soil Ecotox), Row 2 (Fate)
    groups = [
        # Row 0: Aquatic
        ("fish_acute_lc50", "Fish LC50"),
        ("daphnia_acute_ec50", "Daphnia EC50"),
        ("algae_growth_ec50", "Algae EC50"),
        # Row 1: Terrestrial / Soil
        ("bee_acute_oral_ld50", "Bee Oral"),
        ("bee_acute_contact_ld50", "Bee Contact"),
        ("earthworm_acute_lc50", "Worm LC50"),
        ("bird_acute_oral_ld50", "Bird LD50"),
        # Row 2: Env Fate
        ("soil_koc", "Soil Koc"),
        ("soil_dt50", "Soil DT50"),
        ("gus_index", "GUS Index")
    ]

    R = 1.0
    col_spacing = 1.732 * R
    row_spacing = 1.5 * R

    # Coordinates mapping
    hex_positions = [
        # Row 0 (Y = 2)
        (0.5 * col_spacing, 2 * row_spacing),
        (1.5 * col_spacing, 2 * row_spacing),
        (2.5 * col_spacing, 2 * row_spacing),
        # Row 1 (Y = 1)
        (0.0 * col_spacing, 1 * row_spacing),
        (1.0 * col_spacing, 1 * row_spacing),
        (2.0 * col_spacing, 1 * row_spacing),
        (3.0 * col_spacing, 1 * row_spacing),
        # Row 2 (Y = 0)
        (0.5 * col_spacing, 0 * row_spacing),
        (1.5 * col_spacing, 0 * row_spacing),
        (2.5 * col_spacing, 0 * row_spacing),
    ]

    fig, ax = plt.subplots(figsize=(10, 8.5))
    ax.set_aspect('equal')
    
    # Hide axes
    ax.axis('off')
    
    for (ep_id, label), pos in zip(groups, hex_positions):
        pred = predictions.get(ep_id)
        if not pred:
            fill_c, border_c = COLOR_GREY_FILL, COLOR_GREY_BORDER
            val_text, ci_text = "N/A", "No data"
        else:
            # Color logic based on endpoint and risk
            is_out = pred.ad_status == ADStatus.OUT
            if is_out:
                fill_c, border_c = COLOR_GREY_FILL, COLOR_GREY_BORDER
                val_text, ci_text = "Out of Domain", "N/A"
            else:
                # Default colors
                fill_c, border_c = COLOR_GREEN_FILL, COLOR_GREEN_BORDER
                
                if pred.value.kind == "binary":
                    is_toxic = pred.value.binary
                    val_text = "Toxic" if is_toxic else "Non-Toxic"
                    prob = float(pred.ci_lower) if pred.ci_lower is not None else 0.5
                    ci_text = f"P(tox): {prob:.2f}"
                    if is_toxic:
                        fill_c, border_c = COLOR_RED_FILL, COLOR_RED_BORDER
                    else:
                        fill_c, border_c = COLOR_GREEN_FILL, COLOR_GREEN_BORDER
                else:
                    val = pred.value.numeric
                    unit = pred.units
                    val_text = f"{val:.2f} {unit}" if val is not None else "N/A"
                    ci_text = f"[{pred.ci_lower:.1f}, {pred.ci_upper:.1f}]" if pred.ci_lower is not None else "No CI"
                    
                    # Risk evaluation for numeric endpoints
                    if ep_id == "daphnia_acute_ec50":
                        if val <= 1.0: fill_c, border_c = COLOR_RED_FILL, COLOR_RED_BORDER
                        elif val <= 100.0: fill_c, border_c = COLOR_YELLOW_FILL, COLOR_YELLOW_BORDER
                    elif ep_id == "earthworm_acute_lc50":
                        if val <= 10.0: fill_c, border_c = COLOR_RED_FILL, COLOR_RED_BORDER
                        elif val <= 100.0: fill_c, border_c = COLOR_YELLOW_FILL, COLOR_YELLOW_BORDER
                    elif ep_id == "soil_koc":
                        if val <= 75.0: fill_c, border_c = COLOR_RED_FILL, COLOR_RED_BORDER
                        elif val <= 500.0: fill_c, border_c = COLOR_YELLOW_FILL, COLOR_YELLOW_BORDER
                    elif ep_id == "soil_dt50":
                        if val > 120.0: fill_c, border_c = COLOR_RED_FILL, COLOR_RED_BORDER
                        elif val > 90.0: fill_c, border_c = COLOR_YELLOW_FILL, COLOR_YELLOW_BORDER
                    elif ep_id == "gus_index":
                        if val > 2.8: fill_c, border_c = COLOR_RED_FILL, COLOR_RED_BORDER
                        elif val >= 1.8: fill_c, border_c = COLOR_YELLOW_FILL, COLOR_YELLOW_BORDER

        # Draw hexagon
        hexagon = RegularPolygon(
            pos, numVertices=6, radius=R * 0.95, orientation=0,
            facecolor=fill_c, edgecolor=border_c, linewidth=2.5
        )
        ax.add_patch(hexagon)
        
        # Add labels
        ax.text(
            pos[0], pos[1] + 0.25, label,
            ha='center', va='center', fontsize=11, weight='bold', color='#1A202C'
        )
        ax.text(
            pos[0], pos[1] - 0.05, val_text,
            ha='center', va='center', fontsize=10, weight='semibold', color=border_c
        )
        ax.text(
            pos[0], pos[1] - 0.35, ci_text,
            ha='center', va='center', fontsize=8.5, color='#4A5568'
        )

    # Set limits with generous padding
    ax.set_xlim(-0.8 * col_spacing, 3.8 * col_spacing)
    ax.set_ylim(-0.8 * row_spacing, 2.8 * row_spacing)
    
    plt.title(f"{compound_name} — QSAR Safety Profile", fontsize=15, weight='bold', pad=15, color='#2D3748')
    plt.tight_layout()
    plt.savefig(output_path, dpi=180, bbox_inches='tight')
    plt.close()


# Matplotlib Fate Gauge Plotter
def plot_fate_gauge(compound_name: str, predictions: Dict[str, Prediction], measured: Dict[str, float], output_path: Path):
    """Renders 3 stacked horizontal gauges representing Koc, Soil DT50, and GUS Index."""
    fig, axes = plt.subplots(3, 1, figsize=(9, 6.5))
    
    # 1. Soil Koc (log-scale)
    ax = axes[0]
    pred = predictions.get("soil_koc")
    meas_val = measured.get("soil_koc")
    
    ax.axvspan(1.0, math.log10(75), color=COLOR_RED_FILL, alpha=0.7)
    ax.axvspan(math.log10(75), math.log10(500), color=COLOR_YELLOW_FILL, alpha=0.7)
    ax.axvspan(math.log10(500), 5.0, color=COLOR_GREEN_FILL, alpha=0.7)
    
    ax.text(1.1, 0.8, "High Mobility\n(Leaching)", fontsize=9, color=COLOR_RED_BORDER, fontweight='bold')
    ax.text(math.log10(150), 0.8, "Moderate", fontsize=9, color=COLOR_YELLOW_BORDER, fontweight='bold')
    ax.text(3.5, 0.8, "Low Mobility\n(Sorption)", fontsize=9, color=COLOR_GREEN_BORDER, fontweight='bold')
    
    if pred and pred.value.numeric:
        log_pred = math.log10(pred.value.numeric)
        log_lower = math.log10(pred.ci_lower) if pred.ci_lower else log_pred
        log_upper = math.log10(pred.ci_upper) if pred.ci_upper else log_pred
        ax.plot(log_pred, 0.5, 'ko', markersize=8, label='Predicted')
        ax.errorbar(log_pred, 0.5, xerr=[[log_pred - log_lower], [log_upper - log_pred]], fmt='none', ecolor='black', capsize=5, elinewidth=2)
        ax.text(log_pred, 0.25, f"Pred: {pred.value.numeric:.0f} L/kg", ha='center', fontsize=9.5, fontweight='semibold')
        
    if meas_val:
        log_meas = math.log10(meas_val)
        ax.plot(log_meas, 0.5, 'r*', markersize=12, label='Measured')
        ax.text(log_meas, 0.65, f"Exp: {meas_val:.0f}", color='#B71C1C', ha='center', fontsize=9.5, fontweight='bold')

    ax.set_xlim(1.0, 5.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_yticks([])
    ax.set_title("Organic Carbon Partition Coefficient (Soil Koc)", fontsize=11, fontweight='bold', loc='left', color='#2D3748')
    ax.set_xlabel("log10 Koc (L/kg)", fontsize=9)
    
    # 2. Soil DT50
    ax = axes[1]
    pred = predictions.get("soil_dt50")
    meas_val = measured.get("soil_dt50")
    
    max_dt50 = max(240, (pred.ci_upper if pred and pred.ci_upper else 0), (meas_val if meas_val else 0)) + 30
    
    ax.axvspan(0, 30, color=COLOR_GREEN_FILL, alpha=0.7)
    ax.axvspan(30, 120, color=COLOR_YELLOW_FILL, alpha=0.7)
    ax.axvspan(120, max_dt50, color=COLOR_RED_FILL, alpha=0.7)
    
    ax.text(5, 0.8, "Non-persistent", fontsize=9, color=COLOR_GREEN_BORDER, fontweight='bold')
    ax.text(50, 0.8, "Moderate", fontsize=9, color=COLOR_YELLOW_BORDER, fontweight='bold')
    ax.text(140, 0.8, "Persistent (> 120d)", fontsize=9, color=COLOR_RED_BORDER, fontweight='bold')
    
    if pred and pred.value.numeric:
        val = pred.value.numeric
        lower = pred.ci_lower if pred.ci_lower else val
        upper = pred.ci_upper if pred.ci_upper else val
        ax.plot(val, 0.5, 'ko')
        ax.errorbar(val, 0.5, xerr=[[val - lower], [upper - val]], fmt='none', ecolor='black', capsize=5, elinewidth=2)
        ax.text(val, 0.25, f"Pred: {val:.1f} d", ha='center', fontsize=9.5, fontweight='semibold')
        
    if meas_val:
        ax.plot(meas_val, 0.5, 'r*', markersize=12)
        ax.text(meas_val, 0.65, f"Exp: {meas_val:.1f}d", color='#B71C1C', ha='center', fontsize=9.5, fontweight='bold')

    ax.set_xlim(0, max_dt50)
    ax.set_ylim(0.0, 1.0)
    ax.set_yticks([])
    ax.set_title("Soil Degradation Half-life (Soil DT50)", fontsize=11, fontweight='bold', loc='left', color='#2D3748')
    ax.set_xlabel("DT50 (days)", fontsize=9)
    
    # 3. GUS Index
    ax = axes[2]
    pred = predictions.get("gus_index")
    # No measured GUS, we calculate it if measured Koc & DT50 are available
    meas_val = None
    if measured.get("soil_koc") and measured.get("soil_dt50"):
        try:
            meas_val = math.log10(measured["soil_dt50"]) * (4 - math.log10(measured["soil_koc"]))
        except Exception:
            pass
            
    ax.axvspan(-1.0, 1.8, color=COLOR_GREEN_FILL, alpha=0.7)
    ax.axvspan(1.8, 2.8, color=COLOR_YELLOW_FILL, alpha=0.7)
    ax.axvspan(2.8, 6.0, color=COLOR_RED_FILL, alpha=0.7)
    
    ax.text(-0.8, 0.8, "Non-Leacher\n(GUS < 1.8)", fontsize=9, color=COLOR_GREEN_BORDER, fontweight='bold')
    ax.text(1.9, 0.8, "Transitional", fontsize=9, color=COLOR_YELLOW_BORDER, fontweight='bold')
    ax.text(3.2, 0.8, "Leacher\n(GUS > 2.8)", fontsize=9, color=COLOR_RED_BORDER, fontweight='bold')
    
    if pred and pred.value.numeric:
        val = pred.value.numeric
        lower = pred.ci_lower if pred.ci_lower else val
        upper = pred.ci_upper if pred.ci_upper else val
        ax.plot(val, 0.5, 'ko')
        ax.errorbar(val, 0.5, xerr=[[val - lower], [upper - val]], fmt='none', ecolor='black', capsize=5, elinewidth=2)
        ax.text(val, 0.25, f"Pred: {val:.2f}", ha='center', fontsize=9.5, fontweight='semibold')
        
    if meas_val is not None:
        ax.plot(meas_val, 0.5, 'r*', markersize=12)
        ax.text(meas_val, 0.65, f"Exp: {meas_val:.2f}", color='#B71C1C', ha='center', fontsize=9.5, fontweight='bold')

    ax.set_xlim(-1.0, 6.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_yticks([])
    ax.set_title("Gustafson Groundwater Leaching Index (GUS)", fontsize=11, fontweight='bold', loc='left', color='#2D3748')
    ax.set_xlabel("GUS Score", fontsize=9)
    
    fig.suptitle(f"{compound_name} — Environmental Fate Gauges", fontsize=14, weight='bold', color='#1A202C')
    plt.tight_layout()
    plt.savefig(output_path, dpi=180, bbox_inches='tight')
    plt.close()


# Matplotlib Toxicity Panel Plotter
def plot_toxicity_panel(compound_name: str, smiles: str, predictions: Dict[str, Prediction], output_path: Path):
    """Renders a grid of 4 cards showing mammalian oral, skin, eye, and Ames mutagenicity alerts."""
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.axis('off')
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    
    # Run alerts screening for mutagenicity
    alerts = screen_structural_alerts(smiles, categories=["genotoxicity"])
    n_alerts = len(alerts.get("alerts_fired", []))
    
    # 1. Card parameters
    # Top Left: Mammalian Oral
    # Top Right: Skin Sensitization
    # Bottom Left: Ames Mutagenicity
    # Bottom Right: Eye Irritation
    
    cards = [
        # Mammalian Oral
        {"title": "MAMMALIAN ACUTE ORAL", "ep": "rat_acute_oral_ld50", "x": 0.3, "y": 5.2, "w": 4.4, "h": 4.0},
        # Skin Sens
        {"title": "SKIN SENSITIZATION", "ep": "skin_sensitization", "x": 5.3, "y": 5.2, "w": 4.4, "h": 4.0},
        # Ames Mutagenicity
        {"title": "AMES MUTAGENICITY (ALERTS)", "ep": "mutagenicity", "x": 0.3, "y": 0.6, "w": 4.4, "h": 4.0},
        # Eye Irritation
        {"title": "EYE IRRITATION GHS CLASS", "ep": "eye_irritation", "x": 5.3, "y": 0.6, "w": 4.4, "h": 4.0},
    ]
    
    for c in cards:
        ep = c["ep"]
        if ep == "mutagenicity":
            if n_alerts > 0:
                fill, border = COLOR_RED_FILL, COLOR_RED_BORDER
                val = "Alert(s) Fired"
                detail = f"{n_alerts} genotoxic alerts detected\n(Benigni-Bossa rules)"
            else:
                fill, border = COLOR_GREEN_FILL, COLOR_GREEN_BORDER
                val = "No Alerts"
                detail = "No mutagenic structural\nalerts detected."
        else:
            pred = predictions.get(ep)
            if not pred:
                fill, border = COLOR_GREY_FILL, COLOR_GREY_BORDER
                val = "N/A"
                detail = "No prediction available"
            else:
                if ep == "rat_acute_oral_ld50":
                    ld50 = pred.value.numeric
                    if ld50 is None:
                        fill, border = COLOR_GREY_FILL, COLOR_GREY_BORDER
                        val = "N/A"
                        detail = "No point prediction"
                    else:
                        detail = f"Predicted LD50: {ld50:.0f} mg/kg bw\nCI: [{pred.ci_lower:.0f}, {pred.ci_upper:.0f}]"
                        if ld50 <= 50:
                            fill, border = COLOR_RED_FILL, COLOR_RED_BORDER
                            val = "Category 1/2 (Fatal)"
                        elif ld50 <= 2000:
                            fill, border = COLOR_YELLOW_FILL, COLOR_YELLOW_BORDER
                            val = "Category 3/4 (Harmful)"
                        else:
                            fill, border = COLOR_GREEN_FILL, COLOR_GREEN_BORDER
                            val = "Cat 5 / Unclassified"
                elif ep == "skin_sensitization":
                    cat = pred.value.categorical
                    val = cat
                    if cat == "Strong":
                        fill, border = COLOR_RED_FILL, COLOR_RED_BORDER
                        detail = "Strong skin sensitizer\npredicted."
                    elif cat == "Weak":
                        fill, border = COLOR_YELLOW_FILL, COLOR_YELLOW_BORDER
                        detail = "Weak skin sensitizer\npredicted."
                    else:
                        fill, border = COLOR_GREEN_FILL, COLOR_GREEN_BORDER
                        detail = "No skin sensitization\npotential."
                elif ep == "eye_irritation":
                    cat = pred.value.categorical
                    val = cat
                    if cat == "Severe Irritant":
                        fill, border = COLOR_RED_FILL, COLOR_RED_BORDER
                        detail = "Severe eye irritation / irreversible\ndamage predicted."
                    elif cat == "Irritant":
                        fill, border = COLOR_YELLOW_FILL, COLOR_YELLOW_BORDER
                        detail = "Reversible eye irritation\npredicted."
                    else:
                        fill, border = COLOR_GREEN_FILL, COLOR_GREEN_BORDER
                        detail = "Non-irritant to eyes\npredicted."
        
        # Draw Card Background
        rect = Rectangle((c["x"], c["y"]), c["w"], c["h"], facecolor=fill, edgecolor=border, linewidth=2)
        ax.add_patch(rect)
        
        # Card Text
        ax.text(c["x"] + 0.3, c["y"] + 3.4, c["title"], fontsize=9.5, fontweight='bold', color='#4A5568')
        ax.text(c["x"] + 0.3, c["y"] + 2.0, val, fontsize=12, fontweight='bold', color=border)
        ax.text(c["x"] + 0.3, c["y"] + 0.6, detail, fontsize=9.5, color='#2D3748', va='bottom')
        
    fig.suptitle(f"{compound_name} — Mammalian Toxicity Profile", fontsize=14, weight='bold', color='#1A202C')
    plt.savefig(output_path, dpi=180, bbox_inches='tight')
    plt.close()


# ReportLab PDF Dossier Generator
def generate_dossiers(compound: ReferenceCompound, w1_res: Any, w3_res: Any, out_dir: Path, plots: Dict[str, Path]):
    """Generates ReportLab PDF dossiers for W1 (Registration Readiness) and W3 (TP Sweep)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    styles = getSampleStyleSheet()
    
    # Custom Styles for Visual Appeal
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], fontSize=20, leading=24,
        textColor=colors.HexColor("#1B5E20"), spaceAfter=15, alignment=0
    )
    section_title = ParagraphStyle(
        'SecTitle', parent=styles['Heading2'], fontSize=13, leading=16,
        textColor=colors.HexColor("#2E7D32"), spaceBefore=15, spaceAfter=8, keepWithNext=True
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['BodyText'], fontSize=9.5, leading=13, textColor=colors.HexColor("#212121")
    )
    bold_style = ParagraphStyle(
        'BoldBody', parent=body_style, fontName='Helvetica-Bold'
    )
    disclaimer_style = ParagraphStyle(
        'Disclaimer', parent=styles['Italic'], fontSize=8.0, leading=11, textColor=colors.HexColor("#757575"), spaceBefore=15
    )

    # 1. W1 Registration Readiness PDF
    w1_pdf_path = out_dir / "W1_registration.pdf"
    doc1 = SimpleDocTemplate(str(w1_pdf_path), pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story1 = []
    
    # Header Title
    story1.append(Paragraph(f"Edeon — Registration Readiness Dossier", title_style))
    story1.append(Paragraph(f"<b>Compound:</b> {compound.name} (CAS: {compound.cas})", body_style))
    story1.append(Paragraph(f"<b>SMILES:</b> <font face='Courier'>{compound.smiles_canonical}</font>", body_style))
    story1.append(Spacer(1, 10))

    # Overall Verdict Box
    verdict = w1_res.per_compound[0]["verdict"]
    band = verdict["band"]
    driver = verdict["driver"]
    confidence = verdict["confidence"]
    rationale = verdict["rationale"]
    
    verdict_color = "#C8E6C9" if band == "APPROVED" else ("#FFE082" if band == "CONDITIONAL" else "#FFCDD2")
    border_color = "#2E7D32" if band == "APPROVED" else ("#E65100" if band == "CONDITIONAL" else "#B71C1C")
    
    verdict_text = f"<b>REGISTRATION READINESS VERDICT: {band}</b><br/>" \
                   f"<b>Driver:</b> {driver} | <b>Confidence:</b> {confidence}<br/>" \
                   f"<b>Rationale:</b> {rationale}"
                   
    verdict_p = Paragraph(verdict_text, ParagraphStyle('VerdText', parent=body_style, leading=14))
    verdict_table = Table([[verdict_p]], colWidths=[540])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(verdict_color)),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor(border_color)),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story1.append(verdict_table)
    story1.append(Spacer(1, 15))

    # Incorporate Honeycomb Plot
    story1.append(Paragraph("Tier-1 Predictive Honeycomb", section_title))
    if plots["honeycomb"].exists():
        img = Image(str(plots["honeycomb"]), width=320, height=270)
        img.hAlign = 'CENTER'
        story1.append(img)
    story1.append(Spacer(1, 10))
    
    story1.append(PageBreak())

    # Detailed Scorecard Criteria Table
    story1.append(Paragraph("Regulatory Cut-Offs & Criteria Evaluation", section_title))
    scorecard = w1_res.per_compound[0]["scorecard"]
    
    table_data = [[
        Paragraph("<b>Criterion / Endpoint</b>", bold_style),
        Paragraph("<b>Status</b>", bold_style),
        Paragraph("<b>Evidence & Details</b>", bold_style)
    ]]
    
    for crit in scorecard.get("criteria", []):
        status = crit["status"].upper()
        status_color = "#2E7D32" if status == "PASS" else ("#E65100" if status == "WATCH" else "#B71C1C")
        status_p = Paragraph(f"<font color='{status_color}'><b>{status}</b></font>", body_style)
        
        table_data.append([
            Paragraph(crit["criterion"], body_style),
            status_p,
            Paragraph("; ".join(crit["evidence"]), body_style)
        ])
        
    crit_table = Table(table_data, colWidths=[150, 80, 310])
    crit_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F5F5F5")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story1.append(crit_table)
    story1.append(Spacer(1, 10))

    # Disclaimer
    story1.append(Paragraph(w1_res.sections.get("disclaimer", ""), disclaimer_style))
    doc1.build(story1)

    # 2. W3 TP Sweep PDF
    w3_pdf_path = out_dir / "W3_tp_sweep.pdf"
    doc2 = SimpleDocTemplate(str(w3_pdf_path), pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story2 = []
    
    story2.append(Paragraph(f"Edeon — Transformation-Product Liability Sweep", title_style))
    story2.append(Paragraph(f"<b>Compound:</b> {compound.name} (CAS: {compound.cas})", body_style))
    story2.append(Paragraph(f"<b>SMILES:</b> <font face='Courier'>{compound.smiles_canonical}</font>", body_style))
    story2.append(Spacer(1, 10))

    # TP Overall Verdict
    w3_overall = w3_res.per_compound[0]["verdict"]
    band_w3 = w3_overall["band"]
    driver_w3 = w3_overall["driver"]
    rationale_w3 = w3_overall["rationale"]
    
    w3_color = "#C8E6C9" if band_w3 == "clean" else "#FFE082"
    w3_border = "#2E7D32" if band_w3 == "clean" else "#E65100"
    
    verdict_text_w3 = f"<b>METABOLITE SWEEP VERDICT: {band_w3.upper()}</b><br/>" \
                      f"<b>Driver:</b> {driver_w3}<br/>" \
                      f"<b>Rationale:</b> {rationale_w3}"
                      
    verdict_p_w3 = Paragraph(verdict_text_w3, ParagraphStyle('VerdTextW3', parent=body_style, leading=14))
    verdict_table_w3 = Table([[verdict_p_w3]], colWidths=[540])
    verdict_table_w3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(w3_color)),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor(w3_border)),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story2.append(verdict_table_w3)
    story2.append(Spacer(1, 15))

    # Add Fate Gauges to show mobility / persistence
    story2.append(Paragraph("Parent & TP Fate Profile", section_title))
    if plots["fate_gauge"].exists():
        img = Image(str(plots["fate_gauge"]), width=400, height=290)
        img.hAlign = 'CENTER'
        story2.append(img)
    story2.append(Spacer(1, 10))
    
    story2.append(PageBreak())

    # Flagged Transformation Products Table
    story2.append(Paragraph(f"Flagged Transformation Products & Liabilities (Total Predicted: {w3_res.per_compound[0]['total_tps']})", section_title))
    flagged_tps = w3_res.per_compound[0].get("flagged_tps", [])
    
    if not flagged_tps:
        story2.append(Paragraph("No transformation products with elevated liabilities compared to parent.", body_style))
    else:
        table_data_tps = [[
            Paragraph("<b>TP SMILES</b>", bold_style),
            Paragraph("<b>Prob</b>", bold_style),
            Paragraph("<b>Route / Rule</b>", bold_style),
            Paragraph("<b>Liabilities vs Parent</b>", bold_style)
        ]]
        
        for tp in flagged_tps:
            table_data_tps.append([
                Paragraph(f"<font size='7' face='Courier'>{tp['smiles']}</font>", body_style),
                Paragraph(f"{tp['probability']:.2f}", body_style),
                Paragraph(f"{tp['route']}<br/><font size='7'>{tp['rule']}</font>", body_style),
                Paragraph("; ".join(tp["liabilities"]), body_style)
            ])
            
        tp_table = Table(table_data_tps, colWidths=[160, 40, 140, 200])
        tp_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F5F5F5")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        story2.append(tp_table)

    story2.append(Spacer(1, 10))
    story2.append(Paragraph(w3_res.sections.get("disclaimer", ""), disclaimer_style))
    doc2.build(story2)


# Side-by-Side Comparison Tables (HTML & PDF)
def generate_comparison_tables(compound: ReferenceCompound, predictions: Dict[str, Prediction], out_dir: Path):
    """Generates predictions.html and predictions.pdf comparing predicted vs measured side-by-side."""
    # List endpoints to compare
    comp_list = [
        ("bee_acute_oral_ld50", "Bee Acute Oral", "ug/bee", "bee_acute_oral_ld50"),
        ("bee_acute_contact_ld50", "Bee Acute Contact", "ug/bee", "bee_acute_contact_ld50"),
        ("rat_acute_oral_ld50", "Rat Acute Oral", "mg/kg bw", "rat_acute_oral_ld50"),
        ("soil_dt50", "Soil DT50", "days", "soil_dt50"),
        ("soil_koc", "Soil organic carbon Koc", "L/kg", "soil_koc"),
        ("daphnia_acute_ec50", "Daphnia EC50", "mg/L", "daphnia_acute_ec50"),
    ]

    html_rows = []
    pdf_rows = []

    for ep_id, name, unit, yaml_key in comp_list:
        pred = predictions.get(ep_id)
        meas_obj = compound.measured_values.get(yaml_key)
        
        # 1. Format predicted
        if not pred:
            pred_str = "N/A"
        elif pred.value.kind == "binary":
            is_toxic = pred.value.binary
            pred_str = "Toxic" if is_toxic else "Non-toxic"
            if pred.ci_lower is not None:
                pred_str += f" (P:{pred.ci_lower:.2f})"
        else:
            pred_str = f"{pred.value.numeric:.2f}"
            if pred.ci_lower is not None:
                pred_str += f" [{pred.ci_lower:.1f}, {pred.ci_upper:.1f}]"
                
        # 2. Format measured
        if not meas_obj:
            meas_str = "N/A"
            source_str = "N/A"
            match_str = "N/A"
            match_color = "black"
        else:
            meas_val = meas_obj.value
            meas_str = f"{meas_val}"
            source_str = f"{meas_obj.source} ({meas_obj.reference})"
            
            # Compare logic
            if pred and pred.value.kind == "binary":
                # Ecotox classification comparison
                # Assume measured is toxic if bee LD50 <= 11.0 ug/bee
                is_meas_toxic = (meas_val <= 11.0)
                is_pred_toxic = pred.value.binary
                matched = (is_meas_toxic == is_pred_toxic)
            elif pred and pred.value.numeric is not None:
                # Numeric comparison: Check if measured lies inside predicted conformal interval
                matched = (pred.ci_lower <= meas_val <= pred.ci_upper) if pred.ci_lower else False
            else:
                matched = False
                
            match_str = "MATCH" if matched else "MISMATCH"
            match_color = "#2E7D32" if matched else "#C62828"

        html_rows.append(f"""
        <tr>
            <td><b>{name}</b></td>
            <td>{pred_str}</td>
            <td>{meas_str} {unit}</td>
            <td style="color: {match_color}; font-weight: bold;">{match_str}</td>
            <td><font size="2">{source_str}</font></td>
        </tr>
        """)
        
        pdf_rows.append((name, pred_str, f"{meas_str} {unit}", match_str, source_str))

    # 1. Output HTML
    html_content = f"""<!DOCTYPE html>
    <html>
    <head>
        <title>{compound.name} — Model Predictions vs. Measured Values</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 30px; background-color: #FAFAFA; color: #333; }}
            h2 {{ color: #1B5E20; border-bottom: 2px solid #2E7D32; padding-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); background-color: white; }}
            th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #E0E0E0; }}
            th {{ background-color: #2E7D32; color: white; text-transform: uppercase; font-size: 13px; letter-spacing: 0.5px; }}
            tr:hover {{ background-color: #F5F5F5; }}
            .disclaimer {{ margin-top: 30px; font-style: italic; font-size: 11px; color: #757575; }}
        </style>
    </head>
    <body>
        <h2>{compound.name} — QSAR Validation Table</h2>
        <p><b>CAS:</b> {compound.cas} | <b>Chemical Class:</b> {compound.class_subtype} ({compound.class_})</p>
        <table>
            <thead>
                <tr>
                    <th>Endpoint</th>
                    <th>Predicted (Tier-1 + Conformal CI)</th>
                    <th>Authoritative Measured</th>
                    <th>Match Status</th>
                    <th>Reference Source</th>
                </tr>
            </thead>
            <tbody>
                {"".join(html_rows)}
            </tbody>
        </table>
        <p class="disclaimer">IN-SILICO SCREENING ONLY — These results are computational triage signals. They are NOT regulatory determinations and cannot replace experimental studies.</p>
    </body>
    </html>
    """
    
    with open(out_dir / "predictions.html", "w") as f:
        f.write(html_content)

    # 2. Output PDF
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    
    doc = SimpleDocTemplate(str(out_dir / "predictions.pdf"), pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    title_p = Paragraph(f"{compound.name} — Model Predictions vs. Measured Values", ParagraphStyle('DocTitle', parent=styles['Heading2'], textColor=colors.HexColor("#1B5E20")))
    story.append(title_p)
    story.append(Spacer(1, 15))
    
    table_data = [[
        Paragraph("<b>Endpoint</b>", styles['Normal']),
        Paragraph("<b>Predicted (CI)</b>", styles['Normal']),
        Paragraph("<b>Measured</b>", styles['Normal']),
        Paragraph("<b>Match</b>", styles['Normal']),
        Paragraph("<b>Reference</b>", styles['Normal']),
    ]]
    
    for row in pdf_rows:
        m_color = "#2E7D32" if row[3] == "MATCH" else "#C62828"
        table_data.append([
            Paragraph(row[0], styles['Normal']),
            Paragraph(row[1], styles['Normal']),
            Paragraph(row[2], styles['Normal']),
            Paragraph(f"<font color='{m_color}'><b>{row[3]}</b></font>", styles['Normal']),
            Paragraph(f"<font size='7'>{row[4]}</font>", styles['Normal']),
        ])
        
    table = Table(table_data, colWidths=[120, 110, 80, 60, 170])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F5F5F5")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 20))
    story.append(Paragraph("IN-SILICO SCREENING ONLY — These results are computational triage signals.", ParagraphStyle('Disc', parent=styles['Italic'], fontSize=8.0, textColor=colors.HexColor("#757575"))))
    
    doc.build(story)


# Markdown summary file generator
def generate_summary_md(compound: ReferenceCompound, w1_res: Any, w3_res: Any, out_dir: Path):
    """Generates a summary markdown dossier in the compound directory."""
    verdict = w1_res.per_compound[0]["verdict"]
    w3_verdict = w3_res.per_compound[0]["verdict"]
    
    md_content = f"""# {compound.name} Demonstration Summary

This directory contains early-stage computational screening assets generated by Edeon's model registry and workflow engine.

## Compound Metadata
* **Name**: {compound.name}
* **CAS**: {compound.cas}
* **ChEMBL ID**: {compound.chembl_id}
* **Chemical Class**: {compound.class_subtype} ({compound.class_})
* **IRAC/FRAC/HRAC Classification**: {f"IRAC {compound.irac_group}" if compound.irac_group else (f"FRAC {compound.frac_group}" if compound.frac_group else f"HRAC {compound.hrac_group}")}

## Key Assessment Verdicts

### W1: Registration Readiness
* **Verdict Band**: **{verdict["band"]}**
* **Driver**: {verdict["driver"]}
* **Confidence**: {verdict["confidence"]}
* **Rationale**: {verdict["rationale"]}

### W3: Transformation Product Liability Sweep
* **Verdict Band**: **{w3_verdict["band"].upper()}**
* **Total TPs Analyzed**: {w3_res.per_compound[0]["total_tps"]}
* **Flagged liabilities**: {len(w3_res.per_compound[0].get("flagged_tps", []))} metabolites flagged with elevated persistence, mobility, bioaccumulation or toxicity vs. parent.

## Generated Assets
* [Model vs Measured Validation Table (HTML)](predictions.html)
* [Model vs Measured Validation Table (PDF)](predictions.pdf)
* [Toxicity & Fate Honeycomb Plot](honeycomb.png)
* [Environmental Fate Gauges](fate_gauge.png)
* [Mammalian Toxicity Grid](toxicity_panel.png)
* [Workflow Dossier: Registration Readiness Report](W1_registration.pdf)
* [Workflow Dossier: TP Liability Sweep Report](W3_tp_sweep.pdf)

> **Disclaimer**: IN-SILICO SCREENING ONLY — These results are computational triage signals. They are NOT regulatory determinations and cannot replace experimental studies.
"""
    with open(out_dir / "summary.md", "w") as f:
        f.write(md_content)


def main():
    print("=== Starting Edeon Demo Orchestrator ===")
    
    # 1. Paths Setup
    root_dir = Path(__file__).parent.parent
    yaml_path = root_dir / "data" / "demos" / "reference_compounds.yaml"
    output_base_dir = root_dir / "data" / "demos"
    output_base_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Load and Validate reference compounds YAML
    print(f"Loading reference manifest from: {yaml_path}")
    if not yaml_path.exists():
        print(f"ERROR: Manifest file not found at {yaml_path}")
        sys.exit(1)
        
    with open(yaml_path, 'r') as f:
        raw_manifest = yaml.safe_load(f)
        
    try:
        manifest = ReferenceManifest(**raw_manifest)
    except ValidationError as e:
        print("ERROR: Schema validation failed for reference_compounds.yaml")
        print(e)
        sys.exit(1)
        
    print(f"Validated {len(manifest.reference_compounds)} reference compounds successfully.")

    # 3. Initialize Model Registry
    print("Initializing QSAR Model Registry...")
    registry = build_default_registry()

    # 4. Process each compound
    for comp in manifest.reference_compounds:
        print(f"\n--- Processing Compound: {comp.name} ({comp.id}) ---")
        comp_dir = output_base_dir / comp.id
        comp_dir.mkdir(exist_ok=True)
        
        # 4a. Run point predictions on the 10 endpoints
        print("Running point predictions on endpoints...")
        predictions = {}
        for ep in Endpoint:
            # We only query the 10 endpoints used in T1
            if ep.value in [
                "bee_acute_oral_ld50", "bee_acute_contact_ld50", "fish_acute_lc50",
                "daphnia_acute_ec50", "algae_growth_ec50", "earthworm_acute_lc50",
                "bird_acute_oral_ld50", "soil_koc", "soil_dt50", "gus_index"
            ]:
                try:
                    backend = registry.get(ep)
                    pred = backend.predict([comp.smiles_canonical])[0]
                    predictions[ep.value] = pred
                except Exception as e:
                    print(f"Warning: failed prediction for {ep.value}: {e}")
                    
        # 4b. Draw head-less visualizations
        print("Generating visualizations...")
        honeycomb_path = comp_dir / "honeycomb.png"
        plot_honeycomb(comp.name, predictions, honeycomb_path)
        
        measured_fate = {}
        if "soil_koc" in comp.measured_values:
            measured_fate["soil_koc"] = comp.measured_values["soil_koc"].value
        if "soil_dt50" in comp.measured_values:
            measured_fate["soil_dt50"] = comp.measured_values["soil_dt50"].value
            
        fate_gauge_path = comp_dir / "fate_gauge.png"
        plot_fate_gauge(comp.name, predictions, measured_fate, fate_gauge_path)
        
        tox_panel_path = comp_dir / "toxicity_panel.png"
        plot_toxicity_panel(comp.name, comp.smiles_canonical, predictions, tox_panel_path)
        
        # 4c. Run workflows W1 & W3
        print("Running workflow W1 (registration_readiness)...")
        w1_res = run_workflow('registration_readiness', {'smiles': [comp.smiles_canonical]}, params={'num_workers': 4})
        
        print("Running workflow W3 (tp_liability)...")
        w3_res = run_workflow('tp_liability', {'smiles': [comp.smiles_canonical]}, params={'num_workers': 4})
        
        # 4d. Generate Reports & Dossiers
        print("Compiling dossier reports...")
        plots = {
            "honeycomb": honeycomb_path,
            "fate_gauge": fate_gauge_path,
            "toxicity_panel": tox_panel_path
        }
        generate_dossiers(comp, w1_res, w3_res, comp_dir, plots)
        
        # 4e. Generate Comparison HTML/PDF tables
        print("Generating validation tables...")
        generate_comparison_tables(comp, predictions, comp_dir)
        
        # 4f. Generate summary.md
        generate_summary_md(comp, w1_res, w3_res, comp_dir)
        
        print(f"Completed assets generation for {comp.name}.")

    print("\n=== Edeon Demo Orchestrator Completed Successfully ===")


if __name__ == "__main__":
    main()
