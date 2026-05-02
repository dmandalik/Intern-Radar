"""Markdown export support."""

from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
from typing import Any

from internradar.export import ExportJobView


def export_markdown(
    records: list[ExportJobView],
    output_path: Path,
    *,
    metadata: dict[str, Any],
) -> Path:
    """Render GitHub-friendly markdown export."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    template = _template_path().read_text(encoding="utf-8")
    rendered = _render_template(
        template,
        {
            "metadata": metadata,
            "records": records,
            "top_open": [record for record in records if record.status in {"open", "likely_open"}][:15],
            "hidden_gems": [record for record in records if record.job.scores.hidden_gem_score >= 70][:15],
            "coming_soon": [record for record in records if record.status == "coming_soon"][:15],
            "all_jobs": records[:50],
        },
    )
    output_path.write_text(rendered, encoding="utf-8")
    return output_path


def _render_template(template: str, context: dict[str, Any]) -> str:
    try:
        from jinja2 import Environment, StrictUndefined
    except ModuleNotFoundError:
        return _render_with_venv(template, context)

    environment = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
    return environment.from_string(template).render(**context)


def _template_path() -> Path:
    return Path(__file__).resolve().parent / "templates" / "report.md.j2"


def _render_with_venv(template: str, context: dict[str, Any]) -> str:
    python_command = shutil.which("python3")
    if python_command is None:
        raise ModuleNotFoundError("jinja2 is not available and python3 could not be located for fallback rendering.")

    payload = {
        "template": template,
        "context": _serialize_context(context),
    }
    script = """
import json, sys
from jinja2 import Environment, StrictUndefined
payload = json.loads(sys.argv[1])
env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
print(env.from_string(payload["template"]).render(**payload["context"]))
"""
    result = subprocess.run(
        [python_command, "-c", script, json.dumps(payload)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _serialize_context(context: dict[str, Any]) -> dict[str, Any]:
    records = context["records"]
    return {
        "metadata": context["metadata"],
        "records": [_record_payload(record) for record in records],
        "top_open": [_record_payload(record) for record in context["top_open"]],
        "hidden_gems": [_record_payload(record) for record in context["hidden_gems"]],
        "coming_soon": [_record_payload(record) for record in context["coming_soon"]],
        "all_jobs": [_record_payload(record) for record in context["all_jobs"]],
    }


def _record_payload(record: ExportJobView) -> dict[str, Any]:
    return {
        "rank": record.rank,
        "company": record.company,
        "title": record.title,
        "status": record.status,
        "role_family": record.role_family,
        "why_ranked": record.why_ranked,
        "job": record.job.model_dump(mode="json"),
    }


__all__ = ["export_markdown"]
