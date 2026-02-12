"""
Edeon Dossier Report Renderer.

Renders WorkflowResult objects into branded HTML (and optionally PDF)
dossier documents using Jinja2 templates.

Usage:
    from edeon_engine.workflows.reports.renderer import render_dossier_html, render_dossier_pdf
    
    html = render_dossier_html(workflow_result)
    render_dossier_pdf(workflow_result, "/path/to/output.pdf")
"""

import os
import datetime
from dataclasses import asdict
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..contracts import WorkflowResult, Verdict


# ── Template directory ───────────────────────────────────────────────────────

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

# ── Template ID → filename mapping ───────────────────────────────────────────

TEMPLATE_MAP = {
    "w1_dossier":       "w1_dossier.html.j2",
    "w2_pollinator":    "w2_pollinator.html.j2",
    "w3_tp_report":     "w3_tp_report.html.j2",
    "w4_opt_proposal":  "w4_opt_proposal.html.j2",
    "w5_shortlist":     "w5_shortlist.html.j2",
    "w6_comparison":    "w6_comparison.html.j2",
    "w7_window":        "w7_window.html.j2",
    "w8_scaffold_hop":  "w8_scaffold_hop.html.j2",
}


def _get_jinja_env() -> Environment:
    """Create a configured Jinja2 environment."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Custom filters
    env.filters["fmt_float"] = lambda v, d=2: f"{v:.{d}f}" if v is not None else "—"
    env.filters["confidence_class"] = lambda c: {
        "high": "conf-high", "moderate": "conf-moderate", "low": "conf-low"
    }.get(c, "conf-unknown")
    env.filters["band_class"] = lambda b: {
        "GO": "band-go", "CONDITIONAL": "band-conditional", "NO_GO": "band-nogo",
        "High": "band-high", "Med": "band-med", "Low": "band-low",
        "clean": "band-go", "parent-OK-TP-liability": "band-conditional",
    }.get(b, "band-unknown")
    return env


def _result_to_dict(result: WorkflowResult) -> dict:
    """Convert WorkflowResult to a plain dict for template rendering."""
    d = {
        "workflow_id": result.workflow_id,
        "per_compound": result.per_compound,
        "sections": result.sections or {},
        "warnings": result.warnings or [],
        "provenance": result.provenance or {},
    }
    if result.overall:
        d["overall"] = {
            "band": result.overall.band,
            "driver": result.overall.driver,
            "confidence": result.overall.confidence,
            "rationale": result.overall.rationale,
        }
    else:
        d["overall"] = None
    return d


def render_dossier_html(
    result: WorkflowResult,
    template_id: Optional[str] = None,
) -> str:
    """
    Render a WorkflowResult to an HTML string.
    
    Args:
        result: The completed WorkflowResult from a workflow run.
        template_id: Template identifier (e.g. "w1_dossier"). If None,
                      looks up from TEMPLATE_MAP using result.workflow_id.
    
    Returns:
        Rendered HTML string.
    """
    if template_id is None:
        # Reverse-lookup from workflow registry
        from ..registry import REGISTRY
        for wf_id, spec in REGISTRY.items():
            if wf_id == result.workflow_id:
                template_id = spec.report_template
                break
    
    if template_id not in TEMPLATE_MAP:
        raise ValueError(
            f"Unknown template_id '{template_id}'. "
            f"Available: {list(TEMPLATE_MAP.keys())}"
        )
    
    env = _get_jinja_env()
    template = env.get_template(TEMPLATE_MAP[template_id])
    
    context = _result_to_dict(result)
    context["generated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    context["template_id"] = template_id
    
    return template.render(**context)


def render_dossier_pdf(
    result: WorkflowResult,
    output_path: str,
    template_id: Optional[str] = None,
) -> str:
    """
    Render a WorkflowResult to a PDF file.
    
    Requires weasyprint (install via: pip install edeon_engine[reports]).
    Falls back to writing HTML if weasyprint is not available.
    
    Args:
        result: The completed WorkflowResult from a workflow run.
        output_path: Path to write the PDF file.
        template_id: Template identifier. If None, auto-detected.
    
    Returns:
        The output_path that was written.
    """
    html_content = render_dossier_html(result, template_id)
    
    try:
        from weasyprint import HTML
        HTML(string=html_content, base_url=TEMPLATE_DIR).write_pdf(output_path)
    except ImportError:
        # Fallback: write HTML file with .html extension
        html_path = output_path.rsplit(".", 1)[0] + ".html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return html_path
    
    return output_path
