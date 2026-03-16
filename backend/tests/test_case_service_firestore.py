import sys
from types import ModuleType

import google.cloud

from app.models.schema import CaseFile
from app.services.case_service import (
    ANALYSIS_STATUS_COMPLETED,
    CaseWorkspaceRecord,
    FirestoreCaseWorkspaceBackend,
)
from app.services.cloud.blob_store import InMemoryBlobStore
from app.services.intelligence.citations import CitationIndex


class _FakeSnapshot:
    def __init__(self, payload):
        self._payload = payload

    @property
    def exists(self) -> bool:
        return self._payload is not None

    def to_dict(self):
        return dict(self._payload) if self._payload is not None else None


class _FakeCaseRef:
    def __init__(self, client):
        self._client = client

    def get(self, transaction=None):
        payload = transaction.doc if transaction is not None else self._client.doc
        return _FakeSnapshot(payload)


class _FakeTransaction:
    def __init__(self, payload):
        self.doc = dict(payload)
        self.set_calls: list[dict[str, object]] = []

    def set(self, reference, document_data, merge=False):
        self.set_calls.append(
            {
                "reference": reference,
                "document_data": dict(document_data),
                "merge": merge,
            }
        )
        if merge:
            self.doc.update(document_data)
        else:
            self.doc = dict(document_data)


class _FakeClient:
    def __init__(self, payload):
        self.doc = dict(payload)
        self._transaction = _FakeTransaction(payload)

    def transaction(self):
        return self._transaction


def _install_fake_firestore(monkeypatch):
    fake_module = ModuleType("google.cloud.firestore")
    fake_module.transactional = lambda fn: fn
    monkeypatch.setattr(google.cloud, "firestore", fake_module, raising=False)
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", fake_module)


def _build_backend(monkeypatch, payload):
    _install_fake_firestore(monkeypatch)
    client = _FakeClient(payload)
    backend = FirestoreCaseWorkspaceBackend(
        blob_store=InMemoryBlobStore(),
        client=client,
        project_id="clarion-test",
    )
    case_ref = _FakeCaseRef(client)
    monkeypatch.setattr(backend, "_case_ref", lambda _client, _case_id: case_ref)
    return backend, client


def test_firestore_commit_analysis_result_merges_fields(monkeypatch):
    backend, client = _build_backend(
        monkeypatch,
        {
            "case_id": "case-123",
            "evidence_revision": 2,
            "status": "intake",
        },
    )
    expected_record = CaseWorkspaceRecord(
        case=CaseFile(id="case-123", status="analyzed"),
        evidence_revision=2,
        analysis_revision=2,
        analysis_status=ANALYSIS_STATUS_COMPLETED,
        citation_index=CitationIndex(),
    )
    monkeypatch.setattr(backend, "get_case_record", lambda case_id: expected_record)

    result = backend.commit_analysis_result(
        "case-123",
        expected_revision=2,
        contradictions=[],
        missing_info=[],
        citation_index=CitationIndex(),
    )

    assert result is expected_record
    assert len(client._transaction.set_calls) == 1
    write = client._transaction.set_calls[0]
    assert write["merge"] is True
    assert write["document_data"]["analysis_status"] == ANALYSIS_STATUS_COMPLETED
    assert write["document_data"]["analysis_revision"] == 2
    assert write["document_data"]["status"] == "analyzed"
    assert "citation_index_gcs_uri" in write["document_data"]


def test_firestore_commit_analysis_result_skips_stale_revision(monkeypatch):
    backend, client = _build_backend(
        monkeypatch,
        {
            "case_id": "case-123",
            "evidence_revision": 1,
            "status": "intake",
        },
    )
    stale_record = CaseWorkspaceRecord(
        case=CaseFile(id="case-123", status="intake"),
        evidence_revision=1,
    )
    monkeypatch.setattr(backend, "get_case_record", lambda case_id: stale_record)

    result = backend.commit_analysis_result(
        "case-123",
        expected_revision=2,
        contradictions=[],
        missing_info=[],
        citation_index=CitationIndex(),
    )

    assert result is stale_record
    assert client._transaction.set_calls == []
