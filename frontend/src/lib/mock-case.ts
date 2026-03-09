// Mock data that mirrors the backend schema shapes for easy real-API swap later

export interface MockSourcePin {
  evidence_id: string;
  detail: string;
  excerpt: string;
}

export interface MockContradiction {
  id: string;
  severity: "low" | "medium" | "high";
  description: string;
  fact_a: string;
  fact_b: string;
  source_a: MockSourcePin;
  source_b: MockSourcePin;
  // Enriched for animation — the exact sentence that animates
  conflictingTextA: string;
  conflictingTextB: string;
  evidenceAId: string;
  evidenceBId: string;
  label: string;
}

export interface MockMissingInfo {
  id: string;
  severity: "suggestion" | "warning" | "critical";
  description: string;
  recommendation: string;
}

export interface MockEvidence {
  id: string;
  label: string;
  filename: string;
  type: "police_report" | "witness_statement" | "medical_record";
  icon: "file-text" | "user" | "shield";
  excerpt: string;
  contradictingTexts: string[];
  page: number;
}

export interface MockResult {
  contradictionCount: number;
  gapCount: number;
  confidenceScore: number;
  impactAssessment: "LOW" | "MEDIUM" | "HIGH";
  shareText: string;
}

export const MOCK_CASE = {
  id: "demo-johnson-v-metro-2024",
  title: "Johnson v. Metro Transit Authority",
  caseType: "personal_injury_auto_accident",
  analysisTimeMs: 3247,

  evidence: [
    {
      id: "ev-police-report",
      label: "Police Report",
      filename: "Metro_Transit_Incident_2024-0847.pdf",
      type: "police_report" as const,
      icon: "shield" as const,
      excerpt:
        "Vehicle speed estimated at 41 mph at point of impact per skid mark analysis and witness corroboration. Traffic signal status: red at time of entry per physical evidence.",
      contradictingTexts: [
        "Vehicle speed estimated at 41 mph at point of impact per skid mark analysis.",
      ],
      page: 3,
    },
    {
      id: "ev-driver-statement",
      label: "Driver Statement",
      filename: "Statement_Marcus_Webb_Driver.pdf",
      type: "witness_statement" as const,
      icon: "user" as const,
      excerpt:
        "I was traveling at approximately 25 miles per hour when the pedestrian entered the crosswalk. The signal was green at the time I entered the intersection.",
      contradictingTexts: [
        "I was traveling at approximately 25 miles per hour when the incident occurred.",
        "The signal was green at the time I entered the intersection.",
      ],
      page: 1,
    },
    {
      id: "ev-witness-statement",
      label: "Witness Statement",
      filename: "Statement_Sarah_Chen_Witness.pdf",
      type: "witness_statement" as const,
      icon: "user" as const,
      excerpt:
        "The bus was clearly moving very fast — I estimated at least 40 miles per hour. The light had been red for at least 5 seconds before the bus entered the intersection.",
      contradictingTexts: [
        "The bus was moving very fast — I estimated at least 40 miles per hour.",
        "The light had been red for at least 5 seconds before the bus entered the intersection.",
      ],
      page: 2,
    },
  ] as MockEvidence[],

  contradictions: [
    {
      id: "c-speed",
      severity: "high" as const,
      label: "Speed Discrepancy",
      description:
        "NUMERICAL DISCREPANCY — Police skid mark analysis measured 41 mph; driver claims 25 mph — a 64% discrepancy that directly affects liability calculation.",
      fact_a:
        "Vehicle speed estimated at 41 mph at point of impact per skid mark analysis.",
      fact_b:
        "I was traveling at approximately 25 miles per hour when the incident occurred.",
      source_a: {
        evidence_id: "ev-police-report",
        detail: "Police Report, Page 3",
        excerpt: "41 mph at point of impact",
      },
      source_b: {
        evidence_id: "ev-driver-statement",
        detail: "Driver Statement, Page 1",
        excerpt: "approximately 25 miles per hour",
      },
      conflictingTextA:
        "Vehicle speed estimated at 41 mph at point of impact.",
      conflictingTextB:
        "I was traveling at approximately 25 miles per hour.",
      evidenceAId: "ev-police-report",
      evidenceBId: "ev-driver-statement",
    },
    {
      id: "c-signal",
      severity: "high" as const,
      label: "Traffic Signal Status",
      description:
        "DIRECT CONFLICT — Driver claims signal was green; witness states signal had been red for 5+ seconds. This directly determines fault.",
      fact_a: "The signal was green at the time I entered the intersection.",
      fact_b:
        "The light had been red for at least 5 seconds before the bus entered the intersection.",
      source_a: {
        evidence_id: "ev-driver-statement",
        detail: "Driver Statement, Page 1",
        excerpt: "signal was green",
      },
      source_b: {
        evidence_id: "ev-witness-statement",
        detail: "Witness Statement, Page 2",
        excerpt: "red for at least 5 seconds",
      },
      conflictingTextA:
        "The signal was green at the time I entered the intersection.",
      conflictingTextB:
        "The light had been red for at least 5 seconds before the bus entered.",
      evidenceAId: "ev-driver-statement",
      evidenceBId: "ev-witness-statement",
    },
  ] as MockContradiction[],

  missingInfo: [
    {
      id: "m-dashcam",
      severity: "critical" as const,
      description:
        "No dashcam footage uploaded despite Metro Transit buses being equipped with forward-facing cameras as standard equipment since 2019.",
      recommendation:
        "Subpoena Metro Transit Authority for onboard camera footage from Bus #4471 for the period 2:15–2:30 PM on the date of incident.",
    },
  ] as MockMissingInfo[],

  result: {
    contradictionCount: 2,
    gapCount: 1,
    confidenceScore: 94,
    impactAssessment: "HIGH" as const,
    shareText: `Clarion AI detected 2 contradictions & 1 critical evidence gap in "Johnson v. Metro Transit" — in 3.2 seconds. This is what AI-powered litigation looks like.`,
  } as MockResult,
};

export const SOCIAL_PROOF = {
  casesAnalyzed: 4231,
  legalTeams: 47,
  waitlistSeed: 4231,
};

export const ANALYSIS_LOG_LINES = [
  "Parsing 3 evidence documents...",
  "Building citation index across sources...",
  "Running dimension classification via AI...",
  "Detecting contradictions between sources...",
  "Analyzing evidence coverage gaps...",
  "Ranking contradictions by severity...",
  "Analysis complete.",
];
