from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - environment-specific dependency gate
    TestClient = None

from internradar.core.database import complete_scan_run, create_scan_run, initialize_database, load_user_actions, upsert_jobs
from internradar.core.models import ClassifiedRole, EligibilityInfo, Job, JobScores, JobStatusInfo
if TestClient is not None:
    from internradar.dashboard.api import create_dashboard_app
else:  # pragma: no cover - environment-specific dependency gate
    create_dashboard_app = None


def make_job(
    *,
    job_id: str,
    title: str,
    company_name: str = "Example Firm",
    role_family: str = "software_engineer_trading",
    status: str = "open",
    hidden_gem_score: float = 40.0,
    opportunity_score: float = 80.0,
) -> Job:
    from datetime import UTC, datetime

    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    return Job(
        id=job_id,
        company_id=company_name.casefold().replace(" ", "-"),
        company_name=company_name,
        title=title,
        description="Build low latency market data systems in C++ and Python.",
        apply_url=f"https://example.com/{job_id}/apply",
        source_url=f"https://example.com/{job_id}",
        source_type="greenhouse",
        role=ClassifiedRole(
            role_family=role_family,
            confidence=0.9,
            evidence=["title matched strong keyword"],
        ),
        season="Summer",
        year=2027,
        locations=["New York, NY"],
        remote_type="onsite",
        status=JobStatusInfo(status=status, confidence=0.9, evidence=["signal"], checked_at=now),
        eligibility=EligibilityInfo(
            degree_levels=["bachelors"],
            graduation_years=[2027],
            majors=["computer science"],
            sponsorship="not_available",
            confidence=0.5,
            raw_evidence=["Bachelor's degree in Computer Science"],
        ),
        scores=JobScores(
            prestige_score=80,
            role_fit_score=90,
            technical_depth_score=85,
            hidden_gem_score=hidden_gem_score,
            freshness_score=95,
            eligibility_score=88,
            opportunity_score=opportunity_score,
            explanation=["Strong technical fit", "Fresh open role"],
        ),
        prestige_tier="A",
        tags=["systems"],
        first_seen=now,
        last_seen=now,
        last_verified=now,
        content_hash=f"hash-{job_id}",
    )


@unittest.skipIf(TestClient is None, "fastapi is not available in this interpreter")
class TestDashboardApi(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cwd = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_health_returns_ok(self) -> None:
        app = create_dashboard_app(cwd=self.cwd, serve_frontend=False)
        response = TestClient(app).get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)
        self.assertEqual(response.json()["database_ready"], False)

    def test_summary_returns_counts_from_test_db(self) -> None:
        client = self._seeded_client()

        response = client.get("/api/summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_jobs"], 3)
        self.assertEqual(payload["counts"]["open"], 1)
        self.assertEqual(payload["counts"]["coming_soon"], 1)
        self.assertEqual(payload["counts"]["hidden_gems"], 1)

    def test_jobs_returns_jobs_and_supports_filters_search_and_sort(self) -> None:
        client = self._seeded_client()

        response = client.get(
            "/api/jobs",
            params={
                "status": "open",
                "role_family": "software_engineer_trading",
                "search": "latency",
                "min_hidden_gem_score": 70,
                "sort": "hidden_gem_score",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["title"], "Open Hidden Gem")

    def test_jobs_endpoint_returns_detail(self) -> None:
        client = self._seeded_client()

        response = client.get("/api/jobs/job-open")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], "job-open")
        self.assertIn("raw_payload", payload)

    def test_action_endpoint_persists_saved_applied_and_ignore(self) -> None:
        client = self._seeded_client()

        response = client.post("/api/jobs/job-open/action", json={"action": "oa_received"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["application_status"], "oa_received")
        actions = load_user_actions(cwd=self.cwd)
        self.assertEqual(actions["job-open"]["application_status"], "oa_received")

    def test_action_endpoint_can_mark_reviewed(self) -> None:
        client = self._seeded_client()

        response = client.post("/api/jobs/job-open/action", json={"action": "mark_reviewed"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["reviewed"], True)
        actions = load_user_actions(cwd=self.cwd)
        self.assertEqual(actions["job-open"]["reviewed"], "true")

    def test_mark_reviewed_removes_job_from_review_queue(self) -> None:
        initialize_database(cwd=self.cwd)
        review_job = make_job(
            job_id="job-review",
            title="Review Me",
            status="unknown",
        )
        upsert_jobs([review_job], raw_records_by_id={review_job.id: {"source": review_job.source_type}}, cwd=self.cwd)
        client = TestClient(create_dashboard_app(cwd=self.cwd, serve_frontend=False))

        before = client.get("/api/jobs/job-review")
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.json()["needs_review"], True)

        marked = client.post("/api/jobs/job-review/action", json={"action": "mark_reviewed"})
        self.assertEqual(marked.status_code, 200)
        self.assertEqual(marked.json()["job"]["reviewed"], True)
        self.assertEqual(marked.json()["job"]["needs_review"], False)

        summary = client.get("/api/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["counts"]["review_needed"], 0)

    def test_ignore_action_removes_job_from_review_queue(self) -> None:
        initialize_database(cwd=self.cwd)
        review_job = make_job(
            job_id="job-ignore-review",
            title="Ignore Me",
            status="unknown",
        )
        upsert_jobs([review_job], raw_records_by_id={review_job.id: {"source": review_job.source_type}}, cwd=self.cwd)
        client = TestClient(create_dashboard_app(cwd=self.cwd, serve_frontend=False))

        marked = client.post("/api/jobs/job-ignore-review/action", json={"action": "ignore"})
        self.assertEqual(marked.status_code, 200)
        self.assertEqual(marked.json()["job"]["ignored"], True)
        self.assertEqual(marked.json()["job"]["needs_review"], False)

    def test_notes_endpoint_persists_notes(self) -> None:
        client = self._seeded_client()

        response = client.post("/api/jobs/job-open/notes", json={"notes": "Prioritize after finals"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["notes"], "Prioritize after finals")

    def test_export_endpoint_creates_file(self) -> None:
        client = self._seeded_client()

        response = client.post("/api/export", json={"format": "json", "hidden_gems": True})

        self.assertEqual(response.status_code, 200)
        path = Path(response.json()["paths"][0])
        self.assertTrue(path.exists())
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["count"], 1)

    def test_missing_db_returns_helpful_error(self) -> None:
        app = create_dashboard_app(cwd=self.cwd, serve_frontend=False)
        client = TestClient(app)

        response = client.get("/api/jobs")

        self.assertEqual(response.status_code, 503)
        self.assertIn("Run `internradar init` and `internradar scan` first", response.json()["detail"])

    def test_empty_db_returns_empty_state_response(self) -> None:
        initialize_database(cwd=self.cwd)
        app = create_dashboard_app(cwd=self.cwd, serve_frontend=False)
        client = TestClient(app)

        response = client.get("/api/jobs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(response.json()["total"], 0)

    def test_dashboard_hides_artificial_demo_rows(self) -> None:
        initialize_database(cwd=self.cwd)
        jobs = [
            make_job(job_id="job-real", title="Real Role"),
            make_job(job_id="job-demo", title="Demo Role"),
        ]
        upsert_jobs(
            jobs,
            raw_records_by_id={
                "job-real": {"source": "greenhouse"},
                "job-demo": {"artificial_demo_data": True, "source": "demo"},
            },
            cwd=self.cwd,
        )
        client = TestClient(create_dashboard_app(cwd=self.cwd, serve_frontend=False))

        response = client.get("/api/jobs")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], "job-real")

    def _seeded_client(self) -> TestClient:
        initialize_database(cwd=self.cwd)
        jobs = [
            make_job(job_id="job-open", title="Open Hidden Gem", hidden_gem_score=84, opportunity_score=94),
            make_job(
                job_id="job-coming",
                title="Coming Soon Radar Signal",
                status="coming_soon",
                role_family="quant_developer",
                hidden_gem_score=55,
                opportunity_score=71,
            ),
            make_job(
                job_id="job-closed",
                title="Closed Backfill",
                company_name="Another Firm",
                status="closed",
                role_family="market_data_engineer",
                hidden_gem_score=15,
                opportunity_score=40,
            ),
        ]
        upsert_jobs(jobs, raw_records_by_id={job.id: {"source": job.source_type} for job in jobs}, cwd=self.cwd)
        scan_run_id = create_scan_run(
            started_at=jobs[0].first_seen,
            pack="quant_engineering",
            trigger="scan:test",
            cwd=self.cwd,
        )
        complete_scan_run(
            scan_run_id=scan_run_id,
            completed_at=jobs[0].last_verified,
            status="completed",
            summary={
                "pack": "quant_engineering",
                "firms_selected": 3,
                "sources_attempted": 3,
                "raw_jobs_found": 3,
                "normalized_jobs": 3,
                "duplicates_merged": 0,
                "jobs_saved": 3,
                "collector_errors": 0,
            },
            cwd=self.cwd,
        )
        app = create_dashboard_app(cwd=self.cwd, serve_frontend=False)
        return TestClient(app)
