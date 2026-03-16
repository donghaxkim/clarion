from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import case_workspace_service


def setup_function():
    case_workspace_service.clear()


def teardown_function():
    case_workspace_service.clear()


def test_app_registers_canonical_routes_once():
    paths = [route.path for route in app.routes if hasattr(route, "path")]

    assert paths.count("/upload/") == 1
    assert paths.count("/upload/cases/{case_id}") == 1
    assert paths.count("/generate/jobs") == 1
    assert paths.count("/reconstruction/jobs") == 1
    assert paths.count("/cases") == 1
    assert paths.count("/voice/ws/{report_id}") == 1
    assert paths.count("/health") == 1


def test_health_endpoint_reports_ok():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "cases_in_memory": 0}
