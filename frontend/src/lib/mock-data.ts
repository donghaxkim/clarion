import type {
  ParsedEvidence,
  AnalyzeResponse,
  ReportSection,
  Citation,
  EntityDetail,
} from "./types";

// ─── Mock Upload / Parsed Evidence ───────────────────────────────────────────

export const MOCK_PARSED_FILES: ParsedEvidence[] = [
  {
    evidence_id: "ev-001",
    filename: "Metro_Transit_Incident_2024-0847.pdf",
    evidence_type: "Police Report",
    labels: ["Incident Report", "Official", "Speed Analysis"],
    summary:
      "Official police incident report documenting the collision, including skid mark analysis estimating vehicle speed at 41 mph and traffic signal status.",
    entities: ["Marcus Webb", "Lisa Johnson", "Bus #4471", "Oak St & 5th Ave"],
    status: "parsed",
  },
  {
    evidence_id: "ev-002",
    filename: "Statement_Marcus_Webb_Driver.pdf",
    evidence_type: "Witness Statement",
    labels: ["Defendant Statement", "Self-Reported", "Speed Claim"],
    summary:
      "Driver Marcus Webb claims he was traveling at 25 mph and the traffic signal was green when he entered the intersection.",
    entities: ["Marcus Webb", "Lisa Johnson", "Oak St & 5th Ave"],
    status: "parsed",
  },
  {
    evidence_id: "ev-003",
    filename: "Statement_Sarah_Chen_Witness.pdf",
    evidence_type: "Witness Statement",
    labels: ["Third-Party Witness", "Signal Status", "Speed Estimate"],
    summary:
      "Independent witness Sarah Chen estimates bus speed at 40+ mph and confirms signal had been red for 5+ seconds before the bus entered.",
    entities: ["Sarah Chen", "Marcus Webb", "Bus #4471"],
    status: "parsed",
  },
  {
    evidence_id: "ev-004",
    filename: "Johnson_ER_Medical_Records.pdf",
    evidence_type: "Medical Record",
    labels: ["ER Report", "Injuries", "Prognosis"],
    summary:
      "Emergency room records documenting Lisa Johnson's injuries: fractured tibia, concussion, and soft tissue damage. Initial prognosis: 6-12 weeks recovery.",
    entities: ["Lisa Johnson", "Dr. Rebecca Torres"],
    status: "parsed",
  },
];

// ─── Mock Analysis Result ─────────────────────────────────────────────────────

export const MOCK_ANALYSIS: AnalyzeResponse = {
  case_id: "demo",
  case_type_detected: "Personal Injury — Auto Accident",
  dimensions_discovered: [
    "Vehicle Speed",
    "Traffic Signal Status",
    "Weather Conditions",
    "Witness Credibility",
    "Injury Causation",
  ],
  total_facts_indexed: 47,
  entities: [
    { name: "Marcus Webb", type: "person", aliases: ["Driver", "Defendant"] },
    {
      name: "Lisa Johnson",
      type: "person",
      aliases: ["Plaintiff", "Pedestrian"],
    },
    { name: "Sarah Chen", type: "person", aliases: ["Independent Witness"] },
    {
      name: "Bus #4471",
      type: "vehicle",
      aliases: ["Metro Transit Bus", "Subject Vehicle"],
    },
    {
      name: "Metro Transit Authority",
      type: "organization",
      aliases: ["MTA", "Defendant Employer"],
    },
    {
      name: "Oak St & 5th Ave",
      type: "location",
      aliases: ["Intersection", "Incident Location"],
    },
    {
      name: "Dr. Rebecca Torres",
      type: "person",
      aliases: ["Treating Physician"],
    },
  ],
  contradictions: {
    summary: "2 critical, 1 medium",
    items: [
      {
        id: "c-speed",
        severity: "high",
        description:
          "NUMERICAL DISCREPANCY — Police skid mark analysis measured 41 mph; driver claims 25 mph — a 64% discrepancy that directly affects liability calculation.",
        fact_a:
          "Vehicle speed estimated at 41 mph at point of impact per skid mark analysis.",
        fact_b:
          "I was traveling at approximately 25 miles per hour when the incident occurred.",
        source_a: {
          evidence_id: "ev-001",
          detail: "Police Report, Page 3",
          excerpt: "41 mph at point of impact",
        },
        source_b: {
          evidence_id: "ev-002",
          detail: "Driver Statement, Page 1",
          excerpt: "approximately 25 miles per hour",
        },
      },
      {
        id: "c-signal",
        severity: "high",
        description:
          "DIRECT CONFLICT — Driver claims signal was green; witness states signal had been red for 5+ seconds. This directly determines fault assignment.",
        fact_a: "The signal was green at the time I entered the intersection.",
        fact_b:
          "The light had been red for at least 5 seconds before the bus entered the intersection.",
        source_a: {
          evidence_id: "ev-002",
          detail: "Driver Statement, Page 1",
          excerpt: "signal was green",
        },
        source_b: {
          evidence_id: "ev-003",
          detail: "Witness Statement, Page 2",
          excerpt: "red for at least 5 seconds",
        },
      },
      {
        id: "c-weather",
        severity: "medium",
        description:
          "WEATHER INCONSISTENCY — Driver describes dry, clear conditions; police report notes light rain and wet road surface at time of incident.",
        fact_a: "Road conditions were dry and visibility was excellent.",
        fact_b: "Light precipitation at time of incident. Road surface: wet.",
        source_a: {
          evidence_id: "ev-002",
          detail: "Driver Statement, Page 2",
          excerpt: "dry conditions, excellent visibility",
        },
        source_b: {
          evidence_id: "ev-001",
          detail: "Police Report, Page 1",
          excerpt: "light precipitation, wet road surface",
        },
      },
    ],
  },
  missing_info: {
    total: 3,
    critical: 1,
    items: [
      {
        id: "m-dashcam",
        severity: "critical",
        description:
          "No dashcam footage uploaded despite Metro Transit buses being equipped with forward-facing cameras as standard equipment since 2019.",
        recommendation:
          "Subpoena Metro Transit Authority for onboard camera footage from Bus #4471 for the period 2:15–2:30 PM on the date of incident.",
      },
      {
        id: "m-medical-followup",
        severity: "warning",
        description:
          "No medical records beyond initial ER report. Long-term prognosis and rehabilitation needs are unestablished.",
        recommendation:
          "Obtain complete medical records from treating physicians including all follow-up visits, specialist referrals, and rehabilitation notes.",
      },
      {
        id: "m-traffic-cam",
        severity: "warning",
        description:
          "Traffic camera footage from the Oak St & 5th Ave intersection has not been obtained or confirmed unavailable.",
        recommendation:
          "File emergency preservation request with City DOT for traffic camera footage before standard 30-day retention period expires.",
      },
    ],
  },
};

// ─── Mock Report Sections ─────────────────────────────────────────────────────

export const MOCK_REPORT_SECTIONS: ReportSection[] = [
  {
    section_id: "sec-title",
    block_type: "heading",
    heading_level: 1,
    content: "Johnson v. Metro Transit Authority\nCase Analysis Report",
    citation_ids: [],
    contradiction_ids: [],
  },
  {
    section_id: "sec-exec-head",
    block_type: "heading",
    heading_level: 2,
    content: "Executive Summary",
    citation_ids: [],
    contradiction_ids: [],
  },
  {
    section_id: "sec-exec-body",
    block_type: "text",
    content:
      "On October 14, 2024, Lisa Johnson sustained serious injuries when Bus #4471, operated by Marcus Webb of Metro Transit Authority, struck her at the intersection of Oak Street and 5th Avenue. Analysis of four submitted evidence documents — a police incident report, two witness statements, and emergency medical records — reveals significant factual contradictions that substantially impact liability assessment. Two critical contradictions were identified regarding vehicle speed and traffic signal status, along with one medium-severity inconsistency in reported weather conditions.",
    citation_ids: ["cite-001", "cite-002", "cite-003"],
    contradiction_ids: [],
  },
  {
    section_id: "sec-timeline-head",
    block_type: "heading",
    heading_level: 2,
    content: "Incident Timeline",
    citation_ids: [],
    contradiction_ids: [],
  },
  {
    section_id: "sec-timeline",
    block_type: "timeline",
    content: "Reconstructed timeline of events on October 14, 2024",
    citation_ids: ["cite-001"],
    contradiction_ids: [],
    events: [
      {
        id: "evt-1",
        timestamp: "2:12 PM",
        label: "Johnson Enters Crosswalk",
        description: "Lisa Johnson begins crossing Oak St at the marked crosswalk with pedestrian signal active",
      },
      {
        id: "evt-2",
        timestamp: "2:14 PM",
        label: "Signal Changes",
        description: "Traffic signal at Oak St & 5th Ave cycles to red for vehicle traffic",
      },
      {
        id: "evt-3",
        timestamp: "2:15 PM",
        label: "Collision",
        description: "Bus #4471 enters intersection. Point of impact. Disputed: signal status and vehicle speed",
        section_id: "sec-contradictions",
      },
      {
        id: "evt-4",
        timestamp: "2:18 PM",
        label: "Emergency Call",
        description: "911 call placed by Sarah Chen (witness). Metro Transit Control Center notified",
      },
      {
        id: "evt-5",
        timestamp: "2:31 PM",
        label: "EMS Arrival",
        description: "Emergency medical services arrive on scene. Johnson transported to Metro General Hospital",
      },
      {
        id: "evt-6",
        timestamp: "4:45 PM",
        label: "ER Admission",
        description: "Lisa Johnson admitted to Metro General ER. Dr. Rebecca Torres attending physician",
      },
    ],
  },
  {
    section_id: "sec-speed-head",
    block_type: "heading",
    heading_level: 2,
    content: "Vehicle Speed Analysis",
    citation_ids: [],
    contradiction_ids: ["c-speed"],
  },
  {
    section_id: "sec-speed-body",
    block_type: "text",
    content:
      "The evidence presents a critical discrepancy in reported vehicle speed at the time of impact. The police incident report's skid mark analysis establishes an estimated speed of 41 mph, while defendant Marcus Webb's statement claims a speed of approximately 25 mph — a 64% variance that fundamentally affects both negligence determination and damage calculations.",
    citation_ids: ["cite-001", "cite-002"],
    contradiction_ids: ["c-speed"],
  },
  {
    section_id: "sec-speed-counter",
    block_type: "counter_argument",
    content:
      "Defense will likely argue that skid mark analysis is inherently imprecise and subject to road condition variables. The presence of light precipitation (disputed) could affect coefficient of friction calculations, potentially lowering the speed estimate derived from skid length.",
    citation_ids: [],
    contradiction_ids: [],
  },
  {
    section_id: "sec-signal-head",
    block_type: "heading",
    heading_level: 2,
    content: "Traffic Signal Status",
    citation_ids: [],
    contradiction_ids: ["c-signal"],
  },
  {
    section_id: "sec-signal-body",
    block_type: "text",
    content:
      "Signal status at time of entry is directly dispositive of fault. Independent witness Sarah Chen's statement provides the strongest evidence: she observed the signal had been red for a minimum of five seconds before Bus #4471 entered the intersection. This directly contradicts driver Webb's claim that the signal was green. The absence of traffic camera footage is a critical evidentiary gap that must be addressed immediately.",
    citation_ids: ["cite-002", "cite-003"],
    contradiction_ids: ["c-signal"],
  },
  {
    section_id: "sec-injuries-head",
    block_type: "heading",
    heading_level: 2,
    content: "Injuries & Medical Evidence",
    citation_ids: [],
    contradiction_ids: [],
  },
  {
    section_id: "sec-injuries-body",
    block_type: "text",
    content:
      "Emergency room records confirm Lisa Johnson sustained a fractured tibia, concussion, and soft tissue damage consistent with a high-velocity impact. Treating physician Dr. Rebecca Torres documented an initial recovery prognosis of 6–12 weeks. However, no follow-up medical records have been provided, leaving the full extent of damages — including potential permanent injury, lost wages, and rehabilitation costs — unestablished.",
    citation_ids: ["cite-004"],
    contradiction_ids: [],
  },
  {
    section_id: "sec-recommendations-head",
    block_type: "heading",
    heading_level: 2,
    content: "Recommended Actions",
    citation_ids: [],
    contradiction_ids: [],
  },
  {
    section_id: "sec-recommendations-body",
    block_type: "text",
    content:
      "Three immediate actions are required: (1) File emergency subpoena for Bus #4471 onboard camera footage — Metro Transit equipment retention policies require action within 30 days of incident. (2) File preservation request with City DOT for intersection traffic camera footage before automated deletion. (3) Retain independent accident reconstruction expert to rebut or confirm the 41 mph speed estimate derived from skid mark analysis.",
    citation_ids: [],
    contradiction_ids: [],
  },
];

// ─── Mock Citations ───────────────────────────────────────────────────────────

export const MOCK_CITATIONS: Record<string, Citation> = {
  "cite-001": {
    id: "cite-001",
    evidence_id: "ev-001",
    filename: "Metro_Transit_Incident_2024-0847.pdf",
    page: 3,
    excerpt:
      "Vehicle speed estimated at 41 mph at point of impact per skid mark analysis and witness corroboration. Traffic signal status: red.",
  },
  "cite-002": {
    id: "cite-002",
    evidence_id: "ev-002",
    filename: "Statement_Marcus_Webb_Driver.pdf",
    page: 1,
    excerpt:
      "I was traveling at approximately 25 miles per hour. The signal was green at the time I entered the intersection.",
  },
  "cite-003": {
    id: "cite-003",
    evidence_id: "ev-003",
    filename: "Statement_Sarah_Chen_Witness.pdf",
    page: 2,
    excerpt:
      "The bus was moving very fast — at least 40 mph. The light had been red for at least 5 seconds before the bus entered.",
  },
  "cite-004": {
    id: "cite-004",
    evidence_id: "ev-004",
    filename: "Johnson_ER_Medical_Records.pdf",
    page: 1,
    excerpt:
      "Diagnosis: fractured tibia (left), grade 2 concussion, soft tissue contusions. Estimated recovery: 6–12 weeks.",
  },
};

// ─── Mock Entity Detail ───────────────────────────────────────────────────────

export const MOCK_ENTITY_DETAILS: Record<string, EntityDetail> = {
  "Marcus Webb": {
    name: "Marcus Webb",
    type: "person",
    aliases: ["Driver", "Defendant"],
    facts: [
      {
        claim: "Claims vehicle speed was approximately 25 mph at time of impact",
        dimension: "Vehicle Speed",
        source_filename: "Statement_Marcus_Webb_Driver.pdf",
        reliability: 0.35,
      },
      {
        claim: "Claims traffic signal was green when entering the intersection",
        dimension: "Traffic Signal Status",
        source_filename: "Statement_Marcus_Webb_Driver.pdf",
        reliability: 0.2,
      },
      {
        claim: "Describes road conditions as dry with excellent visibility",
        dimension: "Weather Conditions",
        source_filename: "Statement_Marcus_Webb_Driver.pdf",
        reliability: 0.4,
      },
      {
        claim: "CDL license holder, employed by Metro Transit Authority for 7 years",
        dimension: "Driver Background",
        source_filename: "Statement_Marcus_Webb_Driver.pdf",
        reliability: 0.9,
      },
    ],
    contradictions: [MOCK_ANALYSIS.contradictions.items[0], MOCK_ANALYSIS.contradictions.items[1]],
    deposition_questions: [
      "At what speed were you traveling in the 30 seconds prior to the intersection?",
      "Did you observe any pedestrians in or approaching the crosswalk before entering the intersection?",
      "Describe your recollection of the traffic signal state and when you first observed it.",
      "When did you first apply the brakes, and what was the road surface condition?",
      "Have you reviewed the onboard camera footage from Bus #4471 for the date of the incident?",
    ],
  },
  "Lisa Johnson": {
    name: "Lisa Johnson",
    type: "person",
    aliases: ["Plaintiff", "Pedestrian"],
    facts: [
      {
        claim: "Fractured tibia, concussion, and soft tissue damage documented at Metro General ER",
        dimension: "Injuries",
        source_filename: "Johnson_ER_Medical_Records.pdf",
        reliability: 0.95,
      },
      {
        claim: "Estimated recovery of 6–12 weeks per initial ER assessment",
        dimension: "Damages",
        source_filename: "Johnson_ER_Medical_Records.pdf",
        reliability: 0.8,
      },
      {
        claim: "Was in marked crosswalk with pedestrian signal active at time of collision",
        dimension: "Plaintiff Position",
        source_filename: "Metro_Transit_Incident_2024-0847.pdf",
        reliability: 0.85,
      },
    ],
    contradictions: [],
    deposition_questions: [
      "Describe the state of the pedestrian crossing signal when you began crossing.",
      "What was your position in the crosswalk when you first observed Bus #4471?",
      "Detail all medical treatment received since the incident, including follow-up appointments.",
    ],
  },
};
