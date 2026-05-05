"""Dashboard server launcher and frontend asset helpers."""

from __future__ import annotations

from pathlib import Path
import webbrowser

DEFAULT_DASHBOARD_HOST = "127.0.0.1"
DEFAULT_DASHBOARD_PORT = 8765


def dashboard_frontend_dir() -> Path:
    """Return the frontend source directory."""
    return Path(__file__).resolve().parent / "frontend"


def dashboard_assets_dir() -> Path:
    """Return the built frontend asset directory."""
    return dashboard_frontend_dir() / "dist"


def dashboard_assets_ready() -> bool:
    """Return whether built frontend assets are available."""
    return (dashboard_assets_dir() / "index.html").exists()


def dashboard_url(*, host: str = DEFAULT_DASHBOARD_HOST, port: int = DEFAULT_DASHBOARD_PORT) -> str:
    """Build the local dashboard URL."""
    return f"http://{host}:{port}"


def launch_dashboard(
    *,
    host: str = DEFAULT_DASHBOARD_HOST,
    port: int = DEFAULT_DASHBOARD_PORT,
    cwd: Path | None = None,
    open_browser: bool = False,
) -> str:
    """Launch the FastAPI dashboard server."""
    if not dashboard_assets_ready():
        raise RuntimeError(
            "Dashboard frontend assets are missing. Run `npm install` and `npm run build` inside `internradar/dashboard/frontend` first.",
        )

    url = dashboard_url(host=host, port=port)
    if open_browser:
        webbrowser.open(url)

    from internradar.dashboard.api import create_dashboard_app
    import uvicorn

    app = create_dashboard_app(cwd=cwd, serve_frontend=True)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return url
