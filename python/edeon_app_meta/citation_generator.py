from typing import Literal
from datetime import datetime

def generate_citation(
    citation_target: Literal["edeon_app", "prediction", "workflow", "report"],
    target_metadata: dict,
    output_format: Literal["plain", "bibtex", "ris", "markdown"]
) -> str:
    """Generates citations in Plain text, BibTeX, RIS, or Markdown formats for predictions, workflows, or Edeon software."""
    now_year = datetime.utcnow().year
    
    if citation_target == "edeon_app":
        title = "Edeon Desktop: An open-uncertainty platform for agrochemical lead optimization"
        version = target_metadata.get("version", "1.0.0")
        commit = target_metadata.get("commit", "5a3f7b2")
        
        if output_format == "plain":
            return f"Sergio V. et al. ({now_year}). {title} (Version {version}, build {commit}). Journal of Chemical Information and Modeling (in submission)."
        elif output_format == "markdown":
            return f"Sergio V. et al. ({now_year}). *{title}* (Version {version}, build {commit}). Journal of Chemical Information and Modeling (in submission)."
        elif output_format == "bibtex":
            return f"""@manual{{edeonapp{now_year},
  title = {{{title}}},
  author = {{V., Sergio and Edeon Team}},
  year = {{{now_year}}},
  note = {{Version {version}, build {commit}}},
  url = {{https://github.com/edeon-ag/edeon-desktop}}
}}"""
        elif output_format == "ris":
            return f"""TY  - COMP
TI  - {title}
AU  - V., Sergio
AU  - Edeon Team
PY  - {now_year}
UR  - https://github.com/edeon-ag/edeon-desktop
N1  - Version {version}, build {commit}
ER  - """

    elif citation_target == "prediction":
        endpoint = target_metadata.get("endpoint", "unknown_endpoint")
        val = target_metadata.get("value", "N/A")
        model = target_metadata.get("model_id", "TrainedTier1Backend")
        ver = target_metadata.get("version", "1.0")
        
        title = f"Edeon prediction for {endpoint} ({val}) using model {model} v{ver}"
        
        if output_format == "plain":
            return f"Edeon Prediction Service ({now_year}). {title}. Edeon QSAR Registry."
        elif output_format == "markdown":
            return f"Edeon Prediction Service ({now_year}). *{title}*. Edeon QSAR Registry."
        elif output_format == "bibtex":
            return f"""@misc{{edeonpred{endpoint}{now_year},
  title = {{{title}}},
  author = {{Edeon Prediction Service}},
  year = {{{now_year}}},
  howpublished = {{Edeon QSAR Model Registry}},
  note = {{Model ID: {model}, version: {ver}}}
}}"""
        elif output_format == "ris":
            return f"""TY  - ELEC
TI  - {title}
AU  - Edeon Prediction Service
PY  - {now_year}
DP  - Edeon QSAR Model Registry
N1  - Model ID: {model}, version: {ver}
ER  - """

    elif citation_target == "workflow" or citation_target == "report":
        name = target_metadata.get("name", "Lead Optimization Screen")
        date_str = target_metadata.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        
        title = f"Edeon Workflow Report: {name} (Run Date: {date_str})"
        
        if output_format == "plain":
            return f"Edeon Reports Engine ({now_year}). {title}. Edeon Desktop Dossier."
        elif output_format == "markdown":
            return f"Edeon Reports Engine ({now_year}). *{title}*. Edeon Desktop Dossier."
        elif output_format == "bibtex":
            return f"""@techreport{{edeonreport{now_year},
  title = {{{title}}},
  author = {{Edeon Reports Engine}},
  year = {{{now_year}}},
  institution = {{Edeon Dossier Generator}},
  number = {{REF-{date_str}}}
}}"""
        elif output_format == "ris":
            return f"""TY  - RPRT
TI  - {title}
AU  - Edeon Reports Engine
PY  - {now_year}
PB  - Edeon Dossier Generator
ID  - REF-{date_str}
ER  - """

    return "Unsupported citation format or target."
