from fastapi.testclient import TestClient

from app.main import app
from app.models.schema import Entity, EvidenceItem, ExtractedContent, MediaRef, SourceLocation
from app.routers import upload
from app.services.case_service import case_workspace_service


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


def setup_function():
    case_workspace_service.clear()


def teardown_function():
    case_workspace_service.clear()


def test_upload_case_files_parses_and_merges_entities(monkeypatch):
    record = case_workspace_service.create_case(title="Smith v. Johnson")

    async def _fake_save_upload(file):
        del file
        return "/tmp/police_report.pdf", "file:///tmp/police_report.pdf"

    monkeypatch.setattr(upload, "_save_upload", _fake_save_upload)
    monkeypatch.setattr(upload, "_detect_file_type", lambda filename: "pdf")
    monkeypatch.setattr(upload, "_parse_evidence", lambda *args: _make_evidence())

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
        return "/tmp/dashcam.mp4", "file:///tmp/dashcam.mp4"

    monkeypatch.setattr(upload, "_save_upload", _fake_save_upload)
    monkeypatch.setattr(upload, "_detect_file_type", lambda filename: "video")

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
