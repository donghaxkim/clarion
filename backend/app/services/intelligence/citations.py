# Citation system: link claims to source evidence and optional locator.
from app.models import Citation, ReportProvenance


def link_citation(claim: str, doc_id: str, page: int | None) -> dict:
    del claim
    return Citation(
        source_id=doc_id,
        page_number=page,
        provenance=ReportProvenance.evidence,
    ).model_dump(mode="json")
