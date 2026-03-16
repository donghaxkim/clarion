from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.models.schema import Entity, EvidenceItem, ExtractedContent, MediaRef, SourceLocation
from app.services import case_service as case_service_module
from app.routers import upload
from app.services.case_service import InMemoryCaseWorkspaceBackend, case_workspace_service
from app.services.intelligence.citations import CitationIndex


def _make_evidence() -> EvidenceItem:
    return EvidenceItem(
        id="ev_001",
        filename="police_report.pdf",
        evidence_type="police_report",
        media=MediaRef(url="file:///tmp/police_report.pdf", media_type="application/pdf"),
        content=ExtractedContent(text="Police report describes a rear-end collision."),
        summary="Police report",
        entities=[
            Entity(
                id="ent_001",
                type="person",
                name="John Smith",
                mentions=[
                    SourceLocation(
                        evidence_id="ev_001",
                        page=1,
                        excerpt="John Smith",
                    )
                ],
            )
        ],
    )


@pytest.fixture(autouse=True)
def _use_in_memory_case_workspace():
    original_backend = case_workspace_service._backend
    case_workspace_service._backend = InMemoryCaseWorkspaceBackend()
    case_workspace_service.clear()
    try:
        yield
    finally:
        case_workspace_service.clear()
        case_workspace_service._backend = original_backend


def test_upload_case_files_parses_and_merges_entities(monkeypatch):
    record = case_workspace_service.create_case(title="Smith v. Johnson")

    async def _fake_save_upload(file):
        del file
        return "/tmp/police_report.pdf", b"pdf bytes"

    monkeypatch.setattr(upload, "_save_upload", _fake_save_upload)
    monkeypatch.setattr(upload, "_detect_file_type", lambda filename: "pdf")
    monkeypatch.setattr(upload, "_parse_evidence", lambda *args: _make_evidence())
    monkeypatch.setattr(
        upload,
        "_persist_raw_upload",
        lambda **kwargs: f"gs://clarion-test/{kwargs['case_id']}/{kwargs['filename']}",
    )
    monkeypatch.setattr(upload, "_cleanup_upload", lambda path: None)

    client = TestClient(app)
    response = client.post(
        f"/upload/cases/{record.case.id}",
        files=[("files", ("police_report.pdf", b"pdf bytes", "application/pdf"))],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["case_id"] == record.case.id
    assert payload["total_evidence"] == 1
    assert payload["total_entities"] == 1
    assert payload["parsed"][0]["status"] == "parsed"
    assert payload["parsed"][0]["evidence_id"] == "ev_001"


def test_upload_case_files_tracks_pending_video(monkeypatch):
    record = case_workspace_service.create_case(title="Smith v. Johnson")

    async def _fake_save_upload(file):
        del file
        return "/tmp/dashcam.mp4", b"video bytes"

    monkeypatch.setattr(upload, "_save_upload", _fake_save_upload)
    monkeypatch.setattr(upload, "_detect_file_type", lambda filename: "video")
    monkeypatch.setattr(
        upload,
        "_persist_raw_upload",
        lambda **kwargs: f"gs://clarion-test/{kwargs['case_id']}/{kwargs['filename']}",
    )
    monkeypatch.setattr(upload, "_cleanup_upload", lambda path: None)

    client = TestClient(app)
    response = client.post(
        f"/upload/cases/{record.case.id}",
        files=[("files", ("dashcam.mp4", b"video bytes", "video/mp4"))],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"] == []
    assert payload["total_evidence"] == 0
    assert len(payload["video_pending"]) == 1
    assert payload["video_pending"][0]["status"] == "pending_video_analysis"
    assert payload["video_pending"][0]["media_url"].startswith("gs://clarion-test/")


def test_upload_marks_analysis_stale_when_new_evidence_arrives(monkeypatch):
    record = case_workspace_service.create_case(title="Smith v. Johnson")

    async def _fake_save_upload(file):
        del file
        return "/tmp/police_report.pdf", b"pdf bytes"

    monkeypatch.setattr(upload, "_save_upload", _fake_save_upload)
    monkeypatch.setattr(upload, "_detect_file_type", lambda filename: "pdf")
    monkeypatch.setattr(upload, "_parse_evidence", lambda *args: _make_evidence())
    monkeypatch.setattr(
        upload,
        "_persist_raw_upload",
        lambda **kwargs: f"gs://clarion-test/{kwargs['case_id']}/{kwargs['filename']}",
    )
    monkeypatch.setattr(upload, "_cleanup_upload", lambda path: None)
    monkeypatch.setattr(case_service_module, "build_citation_index", lambda case: CitationIndex())
    monkeypatch.setattr(case_service_module, "detect_contradictions", lambda case, index: [])

    client = TestClient(app)
    first = client.post(
        f"/upload/cases/{record.case.id}",
        files=[("files", ("police_report.pdf", b"pdf bytes", "application/pdf"))],
    )
    assert first.status_code == 200

    case_workspace_service.analyze_case(record.case.id)
    analyzed = case_workspace_service.require_case_record(record.case.id)
    assert analyzed.analysis_status == "completed"
    assert analyzed.evidence_revision == 1
    assert analyzed.analysis_revision == 1

    second = client.post(
        f"/upload/cases/{record.case.id}",
        files=[("files", ("police_report_2.pdf", b"pdf bytes", "application/pdf"))],
    )
    assert second.status_code == 200

    refreshed = case_workspace_service.require_case_record(record.case.id)
    assert refreshed.evidence_revision == 2
    assert refreshed.analysis_revision == 1
    assert refreshed.analysis_status == "stale"
