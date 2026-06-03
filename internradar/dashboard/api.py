"""FastAPI application for the local Intern Radar dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from internradar.commands.scan import ScanCommandError
from internradar.core.errors import DatabaseError
from internradar.core.pack_loader import PackLoaderError, PackValidationError
from internradar.dashboard.backend import (
    create_dashboard_export,
    filter_dashboard_jobs,
    load_dashboard_jobs,
    load_dashboard_settings,
    load_dashboard_summary,
    load_filter_options,
    load_job_detail,
    paginate_jobs,
    persist_dashboard_action,
    persist_dashboard_notes,
    run_dashboard_scan,
    sort_dashboard_jobs,
)
from internradar.review.overrides import OverrideError
from internradar.dashboard.server import dashboard_assets_dir, dashboard_assets_ready


def create_dashboard_app(
    *,
    cwd: Path | None = None,
    serve_frontend: bool = True,
) -> FastAPI:
    """Create the FastAPI dashboard application."""
    app = FastAPI(title="Intern Radar Dashboard", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "database_ready": _database_ready(cwd),
            "frontend_ready": dashboard_assets_ready(),
        }

    @app.get("/api/summary")
    def summary() -> dict[str, Any]:
        try:
            return load_dashboard_summary(cwd=cwd)
        except DatabaseError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/jobs")
    def jobs(
        status: str | None = None,
        role_family: str | None = None,
        company: str | None = None,
        prestige_tier: str | None = None,
        location: str | None = None,
        season: str | None = None,
        year: int | None = None,
        application_status: str | None = None,
        source_type: str | None = None,
        remote_type: str | None = None,
        sponsorship: str | None = None,
        is_internship: bool | None = None,
        min_opportunity_score: float | None = None,
        min_hidden_gem_score: float | None = None,
        min_eligibility_score: float | None = None,
        sort: str = "opportunity_score",
        limit: int | None = Query(default=100, ge=1),
        offset: int = Query(default=0, ge=0),
        search: str | None = None,
    ) -> dict[str, Any]:
        try:
            all_jobs = load_dashboard_jobs(cwd=cwd)
        except DatabaseError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        filtered = filter_dashboard_jobs(
            all_jobs,
            status=status,
            role_family=role_family,
            company=company,
            prestige_tier=prestige_tier,
            location=location,
            season=season,
            year=year,
            application_status=application_status,
            source_type=source_type,
            remote_type=remote_type,
            sponsorship=sponsorship,
            is_internship=is_internship,
            min_opportunity_score=min_opportunity_score,
            min_hidden_gem_score=min_hidden_gem_score,
            min_eligibility_score=min_eligibility_score,
            search=search,
        )
        sorted_jobs = sort_dashboard_jobs(filtered, sort=sort)
        paged = paginate_jobs(sorted_jobs, limit=limit, offset=offset)
        return {
            "items": paged,
            "total": len(filtered),
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/jobs/{job_id}")
    def job_detail(job_id: str) -> dict[str, Any]:
        try:
            detail = load_job_detail(job_id, cwd=cwd)
        except DatabaseError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if detail is None:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' was not found.")
        return detail

    @app.get("/api/filters")
    def filters() -> dict[str, Any]:
        try:
            return load_filter_options(cwd=cwd)
        except DatabaseError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/scan-runs/latest")
    def latest_scan() -> dict[str, Any]:
        try:
            summary = load_dashboard_summary(cwd=cwd)
        except DatabaseError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"latest_scan": summary.get("latest_scan")}

    @app.get("/api/settings")
    def settings() -> dict[str, Any]:
        return load_dashboard_settings(cwd=cwd)

    @app.post("/api/jobs/{job_id}/action")
    def job_action(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action", "")).strip()
        if not action:
            raise HTTPException(status_code=400, detail="Action is required.")
        try:
            detail = persist_dashboard_action(
                job_id,
                action=action,
                value=_optional_string(payload.get("value")),
                notes=_optional_string(payload.get("notes")),
                cwd=cwd,
            )
        except DatabaseError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"ok": True, "job": detail}

    @app.post("/api/jobs/{job_id}/notes")
    def job_notes(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        notes = _optional_string(payload.get("notes")) or ""
        try:
            detail = persist_dashboard_notes(job_id, notes=notes, cwd=cwd)
        except DatabaseError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"ok": True, "job": detail}

    @app.post("/api/export")
    def export(payload: dict[str, Any]) -> dict[str, Any]:
        format_name = _optional_string(payload.get("format"))
        all_formats = bool(payload.get("all", False))
        output = _optional_string(payload.get("output"))
        try:
            created = create_dashboard_export(
                format_name=format_name,
                all_formats=all_formats,
                output=Path(output) if output else None,
                status=_optional_string(payload.get("status")),
                hidden_gems=bool(payload.get("hidden_gems", False)),
                saved=bool(payload.get("saved", False)),
                applied=bool(payload.get("applied", False)),
                limit=int(payload["limit"]) if payload.get("limit") is not None else None,
                sort=_optional_string(payload.get("sort")) or "opportunity_score",
                pack=_optional_string(payload.get("pack")),
                include_closed=bool(payload.get("include_closed", False)),
                cwd=cwd,
            )
        except (DatabaseError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"ok": True, "paths": [str(path) for path in created]}

    @app.post("/api/scan")
    def scan(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = run_dashboard_scan(
                pack=_optional_string(payload.get("pack")),
                max_firms=int(payload["max_firms"]) if payload.get("max_firms") is not None else None,
                company=_optional_string(payload.get("company")),
                source=_optional_string(payload.get("source")),
                cwd=cwd,
            )
        except (
            DatabaseError,
            OverrideError,
            PackLoaderError,
            PackValidationError,
            ScanCommandError,
            ValueError,
        ) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"ok": True, "summary": result}

    if serve_frontend:
        _mount_frontend_routes(app)
    return app


def _mount_frontend_routes(app: FastAPI) -> None:
    dist_dir = dashboard_assets_dir()

    @app.get("/", include_in_schema=False)
    def frontend_root() -> FileResponse:
        if not dashboard_assets_ready():
            raise HTTPException(
                status_code=503,
                detail="Dashboard frontend assets are missing. Run `npm install` and `npm run build` inside `internradar/dashboard/frontend`.",
            )
        return FileResponse(dist_dir / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend_path(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        if not dashboard_assets_ready():
            raise HTTPException(
                status_code=503,
                detail="Dashboard frontend assets are missing. Run `npm install` and `npm run build` inside `internradar/dashboard/frontend`.",
            )
        candidate = dist_dir / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist_dir / "index.html")


def _database_ready(cwd: Path | None) -> bool:
    try:
        load_dashboard_jobs(cwd=cwd)
    except DatabaseError:
        return False
    return True


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
