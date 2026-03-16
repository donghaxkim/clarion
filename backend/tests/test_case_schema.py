from app.models.schema import CaseFile


def test_case_file_accepts_analyzed_status():
    case = CaseFile(status="analyzed")

    assert case.status == "analyzed"
