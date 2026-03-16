from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceMention(BaseModel):
    evidence_id: str
    source: str | None = None
    page: int | None = None
    timestamp_start: float | None = None
    excerpt: str | None = None


class VoiceEvidence(BaseModel):
    evidence_id: str
    filename: str
    evidence_type: str
    summary: str | None = None
    content_text: str | None = None
    media_url: str | None = None


class VoiceSectionCitation(BaseModel):
    source_id: str
    source_label: str
    excerpt: str
    provenance: str = "evidence"
    uri: str | None = None


class VoiceEntityFact(BaseModel):
    fact: str
    dimension: str | None = None
    source: str
    evidence_id: str
    page: int | None = None
    timestamp_start: float | None = None
    excerpt: str
    reliability: float = 0.0


class VoiceEntity(BaseModel):
    entity_id: str | None = None
    entity_type: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    mentions: list[VoiceMention] = Field(default_factory=list)
    facts: list[VoiceEntityFact] = Field(default_factory=list)
    contradictions: list["VoiceContradiction"] = Field(default_factory=list)


class VoiceContradiction(BaseModel):
    contradiction_id: str
    severity: str
    description: str
    fact_a: str | None = None
    fact_b: str | None = None


class VoiceMissingInfo(BaseModel):
    item_id: str
    severity: str
    description: str
    recommendation: str


class VoiceReportSection(BaseModel):
    section_id: str
    kind: str
    canonical_block_id: str | None = None
    edit_target: str = "content"
    title: str | None = None
    text: str | None = None
    citations: list[VoiceSectionCitation] = Field(default_factory=list)


class VoiceSessionContext(BaseModel):
    report_id: str
    case_id: str | None = None
    title: str
    case_type: str | None = None
    status: str
    evidence: list[VoiceEvidence] = Field(default_factory=list)
    entities: list[VoiceEntity] = Field(default_factory=list)
    contradictions: list[VoiceContradiction] = Field(default_factory=list)
    missing_info: list[VoiceMissingInfo] = Field(default_factory=list)
    sections: list[VoiceReportSection] = Field(default_factory=list)
    focused_section: VoiceReportSection | None = None
