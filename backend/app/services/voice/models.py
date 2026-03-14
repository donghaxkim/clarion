from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceMention(BaseModel):
    evidence_id: str
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


class VoiceEntity(BaseModel):
    entity_id: str | None = None
    entity_type: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    mentions: list[VoiceMention] = Field(default_factory=list)


class VoiceContradiction(BaseModel):
    contradiction_id: str
    severity: str
    description: str
    fact_a: str | None = None
    fact_b: str | None = None


class VoiceReportSection(BaseModel):
    section_id: str
    kind: str
    title: str | None = None
    text: str | None = None


class VoiceSessionContext(BaseModel):
    report_id: str
    case_id: str | None = None
    title: str
    case_type: str | None = None
    status: str
    evidence: list[VoiceEvidence] = Field(default_factory=list)
    entities: list[VoiceEntity] = Field(default_factory=list)
    contradictions: list[VoiceContradiction] = Field(default_factory=list)
    sections: list[VoiceReportSection] = Field(default_factory=list)
