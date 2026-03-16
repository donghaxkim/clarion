import {
  ParsedEvidence,
  AnalysisResponse,
  ReportSection,
  Entity,
  EntityDetailResponse,
  FullCase,
} from './types';

// ─── Case ──────────────────────────────────────────────────────────────────────

export const MOCK_CASE_ID = 'mock-chen-v-thompson-001';
export const MOCK_CASE_TITLE = 'Chen v. Thompson — Rear-End Collision';

// ─── Evidence ─────────────────────────────────────────────────────────────────

export const MOCK_EVIDENCE: ParsedEvidence[] = [
  {
    evidence_id: 'ev-001',
    filename: 'PD_Report_2024_0312.pdf',
    evidence_type: 'police_report',
    labels: ['Traffic Incident', 'Witness Statements', 'Diagram'],
    summary: 'Officer Miller responded at 14:22. Vehicle traveling northbound on Main St at estimated 35 mph struck stationary vehicle at intersection with 5th Ave.',
    entity_count: 6,
    entities: [
      { type: 'person', name: 'Sarah Chen' },
      { type: 'person', name: 'Marcus Thompson' },
      { type: 'person', name: 'Officer James Miller' },
      { type: 'vehicle', name: '2019 Honda Civic (Chen)' },
      { type: 'vehicle', name: '2021 Ford F-150 (Thompson)' },
      { type: 'location', name: 'Main St & 5th Ave' },
    ],
    status: 'parsed',
  },
  {
    evidence_id: 'ev-002',
    filename: 'Chen_Medical_Records.pdf',
    evidence_type: 'medical_record',
    labels: ['Emergency Visit', 'Spinal Assessment', 'Pain Management'],
    summary: 'ER visit on 03/12/2024. Complaint of cervical and lumbar pain. Physical exam revealed tenderness at C5-C6. X-rays ordered, MRI recommended but not performed.',
    entity_count: 3,
    entities: [
      { type: 'person', name: 'Sarah Chen' },
      { type: 'person', name: 'Dr. Patricia Novak' },
      { type: 'organization', name: 'St. Michael\'s Medical Center' },
    ],
    status: 'parsed',
  },
  {
    evidence_id: 'ev-003',
    filename: 'Chen_Audio_Statement.m4a',
    evidence_type: 'audio',
    labels: ['Client Statement', 'Injury Description', 'Impact Account'],
    summary: 'Client describes impact as sudden and violent. States Thompson was driving "way too fast" and texting. Estimated speed at 45–50 mph. Pain began immediately.',
    entity_count: 2,
    entities: [
      { type: 'person', name: 'Sarah Chen' },
      { type: 'person', name: 'Marcus Thompson' },
    ],
    status: 'parsed',
  },
  {
    evidence_id: 'ev-004',
    filename: 'damage_front_chen.jpg',
    evidence_type: 'photo',
    labels: ['Vehicle Damage', 'Rear Impact', 'Crush Zone'],
    summary: 'Significant rear-end damage to Chen\'s Honda Civic. Trunk collapse, bumper displacement consistent with moderate-to-high speed impact.',
    entity_count: 1,
    entities: [{ type: 'vehicle', name: '2019 Honda Civic (Chen)' }],
    status: 'parsed',
  },
  {
    evidence_id: 'ev-005',
    filename: 'damage_front_thompson.jpg',
    evidence_type: 'photo',
    labels: ['Vehicle Damage', 'Front Impact', 'Airbag Deployment'],
    summary: 'Front-end damage to Thompson\'s F-150. Hood crumple, radiator damage, and airbag deployment recorded. Impact severity indicator on airbag module required.',
    entity_count: 1,
    entities: [{ type: 'vehicle', name: '2021 Ford F-150 (Thompson)' }],
    status: 'parsed',
  },
  {
    evidence_id: 'ev-006',
    filename: 'dashcam_thompson.mp4',
    evidence_type: 'video',
    labels: ['Dashcam Footage', 'Pre-Collision', 'Speed Reference'],
    summary: 'Dashcam footage from Thompson vehicle. Covers period prior to collision. GPS overlay shows speed data. Video analysis pending frame-by-frame review.',
    entity_count: 2,
    entities: [
      { type: 'person', name: 'Marcus Thompson' },
      { type: 'location', name: 'Main St & 5th Ave' },
    ],
    status: 'parsed',
  },
];

// ─── Entities ─────────────────────────────────────────────────────────────────

export const MOCK_ENTITIES: Entity[] = [
  { id: 'ent-001', type: 'person', name: 'Sarah Chen', aliases: ['Plaintiff', 'Ms. Chen'] },
  { id: 'ent-002', type: 'person', name: 'Marcus Thompson', aliases: ['Defendant', 'Mr. Thompson'] },
  { id: 'ent-003', type: 'person', name: 'Officer James Miller', aliases: ['Officer Miller'] },
  { id: 'ent-004', type: 'person', name: 'Dr. Patricia Novak' },
  { id: 'ent-005', type: 'vehicle', name: '2019 Honda Civic', aliases: ['Chen vehicle', 'Plaintiff vehicle'] },
  { id: 'ent-006', type: 'vehicle', name: '2021 Ford F-150', aliases: ['Thompson vehicle', 'Defendant vehicle'] },
  { id: 'ent-007', type: 'location', name: 'Main St & 5th Ave', aliases: ['The intersection', 'Scene of incident'] },
  { id: 'ent-008', type: 'organization', name: 'St. Michael\'s Medical Center' },
];

// ─── Analysis ─────────────────────────────────────────────────────────────────

export const MOCK_ANALYSIS: AnalysisResponse = {
  case_id: MOCK_CASE_ID,
  case_type_detected: 'Personal Injury — Motor Vehicle Collision',
  dimensions_discovered: [
    { name: 'Speed & Velocity', description: 'Conflicting estimates of vehicle speed at time of impact', importance: 'high' },
    { name: 'Driver Conduct', description: 'Evidence of distracted driving and negligence', importance: 'high' },
    { name: 'Injury Causation', description: 'Medical evidence linking collision to claimed injuries', importance: 'high' },
    { name: 'Traffic Conditions', description: 'Road conditions, signaling, and right-of-way', importance: 'medium' },
    { name: 'Vehicle Damage Severity', description: 'Physical evidence of impact force', importance: 'medium' },
    { name: 'Liability Attribution', description: 'Allocation of fault between parties', importance: 'high' },
  ],
  total_facts_indexed: 47,
  total_entities: 8,
  entities: MOCK_ENTITIES,
  contradictions: {
    summary: { total: 3, high: 1, medium: 1, low: 1 },
    items: [
      {
        id: 'con-001',
        severity: 'high',
        description: 'Direction of travel at point of collision conflicts between police report and client statement',
        fact_a: {
          text: 'Thompson vehicle was traveling northbound on Main Street when it struck Chen\'s stationary vehicle.',
          source: 'PD_Report_2024_0312.pdf',
          evidence_id: 'ev-001',
        },
        fact_b: {
          text: 'The car hit me from behind. I was facing east on 5th, waiting for the light. He came from my left.',
          source: 'Chen_Audio_Statement.m4a',
          evidence_id: 'ev-003',
        },
      },
      {
        id: 'con-002',
        severity: 'medium',
        description: 'Speed estimate at time of impact differs significantly between official report and plaintiff\'s account',
        fact_a: {
          text: 'Responding officer estimated Thompson vehicle traveling at approximately 35 mph based on skid marks and vehicle damage assessment.',
          source: 'PD_Report_2024_0312.pdf',
          evidence_id: 'ev-001',
        },
        fact_b: {
          text: 'He was going way too fast — at least 45, maybe 50 miles per hour. I could tell by the sound before impact.',
          source: 'Chen_Audio_Statement.m4a',
          evidence_id: 'ev-003',
        },
      },
      {
        id: 'con-003',
        severity: 'low',
        description: 'Police report does not reference dashcam footage despite Thompson vehicle being equipped',
        fact_a: {
          text: 'No dashcam footage referenced or obtained during initial investigation.',
          source: 'PD_Report_2024_0312.pdf',
          evidence_id: 'ev-001',
        },
        fact_b: {
          text: 'Dashcam video retrieved from Thompson vehicle, GPS overlay confirms pre-collision speed and route.',
          source: 'dashcam_thompson.mp4',
          evidence_id: 'ev-006',
        },
      },
    ],
  },
  missing_info: {
    total: 3,
    critical: 1,
    items: [
      {
        id: 'gap-001',
        severity: 'high',
        description: 'No MRI or advanced imaging to substantiate claimed spinal injury at C5-C6',
        recommendation: 'Obtain MRI of cervical and lumbar spine immediately. Without imaging, causal link between collision and spinal injury will be challenged at trial.',
      },
      {
        id: 'gap-002',
        severity: 'medium',
        description: 'Speed determination relies on single-source police estimate; no independent reconstruction',
        recommendation: 'Retain a qualified accident reconstruction expert to analyze vehicle damage, skid marks, and dashcam GPS data to establish independent speed determination.',
      },
      {
        id: 'gap-003',
        severity: 'low',
        description: 'No witness statement collected from bystander mentioned in police report narrative',
        recommendation: 'Identify and interview the third-party witness referenced in section 4 of the police report. Statement could corroborate or clarify direction of travel.',
      },
    ],
  },
};

// ─── Report Sections ──────────────────────────────────────────────────────────

export const MOCK_REPORT_SECTIONS: ReportSection[] = [
  {
    id: 'sec-001',
    block_type: 'heading',
    order: 1,
    text: 'Chen v. Thompson: Litigation Intelligence Report',
    heading_level: 1,
  },
  {
    id: 'sec-002',
    block_type: 'heading',
    order: 2,
    text: 'Incident Summary',
    heading_level: 2,
  },
  {
    id: 'sec-003',
    block_type: 'text',
    order: 3,
    text: 'On March 12, 2024, at approximately 14:22 hours, a rear-end collision occurred at the intersection of Main Street and 5th Avenue. Sarah Chen[1], operating a 2019 Honda Civic, was stationary at a red light when her vehicle was struck from behind by a 2021 Ford F-150 operated by Marcus Thompson[2]. Officer James Miller[3] responded to the scene and completed the initial incident report.',
    citations: [
      { id: 'cit-001', source_id: 'ev-001', source_label: 'PD_Report_2024_0312.pdf', excerpt: 'Responding unit arrived at 14:22. Plaintiff vehicle stationary at intersection.' },
      { id: 'cit-002', source_id: 'ev-002', source_label: 'Chen_Audio_Statement.m4a', excerpt: 'I was sitting at the red light when he hit me.' },
      { id: 'cit-003', source_id: 'ev-003', source_label: 'PD_Report_2024_0312.pdf', excerpt: 'Officer Miller, Badge #4471, primary responding officer.' },
    ],
    entity_ids: ['ent-001', 'ent-002', 'ent-003'],
  },
  {
    id: 'sec-004',
    block_type: 'heading',
    order: 4,
    text: 'Incident Timeline',
    heading_level: 2,
  },
  {
    id: 'sec-005',
    block_type: 'timeline',
    order: 5,
    timeline_events: [
      { time: '14:15', label: 'Thompson departs workplace', detail: 'GPS data from dashcam confirms departure from 220 Commerce Blvd' },
      { time: '14:20', label: 'Chen stops at intersection', detail: 'Traffic signal cycle confirms red light phase' },
      { time: '14:22', label: 'Collision occurs', detail: 'Impact recorded; airbag module timestamp confirmed' },
      { time: '14:24', label: 'Officer Miller dispatched', detail: 'CAD log entry from dispatch center' },
      { time: '14:31', label: 'EMS arrives', detail: 'Ambulance unit #7 response time confirmed' },
      { time: '15:45', label: 'Chen admitted to St. Michael\'s ER', detail: 'Hospital intake timestamp' },
    ],
  },
  {
    id: 'sec-006',
    block_type: 'heading',
    order: 6,
    text: 'Parties & Witnesses',
    heading_level: 2,
  },
  {
    id: 'sec-007',
    block_type: 'text',
    order: 7,
    text: 'Sarah Chen (Plaintiff) is a 34-year-old marketing consultant residing at 847 Elm Court. She was traveling alone at the time of the incident and sustained cervical and lumbar injuries requiring emergency care[4]. Marcus Thompson (Defendant) is a 41-year-old contractor. Per the dashcam footage retrieved from his vehicle, Thompson was in possession of a mobile device in the minutes preceding impact[5]. Officer James Miller has 12 years with the department and completed the standard accident report, though his report contains material omissions regarding dashcam footage and direction of travel.',
    citations: [
      { id: 'cit-004', source_id: 'ev-004', source_label: 'Chen_Medical_Records.pdf', excerpt: 'Patient presents with cervical tenderness and reported lumbar pain following MVC.' },
      { id: 'cit-005', source_id: 'ev-005', source_label: 'dashcam_thompson.mp4', excerpt: 'Device visible in driver seat area prior to impact zone.' },
    ],
    entity_ids: ['ent-001', 'ent-002', 'ent-003'],
  },
  {
    id: 'sec-008',
    block_type: 'heading',
    order: 8,
    text: 'Evidence Analysis',
    heading_level: 2,
  },
  {
    id: 'sec-009',
    block_type: 'text',
    order: 9,
    text: 'Physical evidence is consistent with a moderate-to-high speed rear-end impact. Photographic documentation shows significant crush deformation to the Chen vehicle\'s trunk and rear quarter panels[6], with corresponding front-end damage and airbag deployment in the Thompson vehicle[7]. The airbag deployment threshold for the 2021 Ford F-150 is calibrated at approximately 12–14 mph; deployment is therefore confirmatory of substantial impact force. Taken together, the physical evidence supports a speed greater than the 35 mph estimate in the police report.',
    citations: [
      { id: 'cit-006', source_id: 'ev-006', source_label: 'damage_front_chen.jpg', excerpt: 'Trunk collapse visible; bumper fully displaced.' },
      { id: 'cit-007', source_id: 'ev-007', source_label: 'damage_front_thompson.jpg', excerpt: 'Airbag deployed; hood crumple indicates significant deceleration force.' },
    ],
    entity_ids: ['ent-005', 'ent-006'],
  },
  {
    id: 'sec-010',
    block_type: 'counter_argument',
    order: 10,
    text: 'Defense will likely argue that Chen\'s pre-existing lower back condition, documented in a 2021 chiropractic visit, was the source of her reported pain rather than the collision. They may also challenge the speed estimate, citing the police report\'s figure of 35 mph as authoritative and arguing that plaintiff\'s audio statement is emotionally biased and unreliable. The absence of MRI imaging will be highlighted as a gap in the injury causation chain.',
  },
  {
    id: 'sec-011',
    block_type: 'heading',
    order: 11,
    text: 'Recommendations',
    heading_level: 2,
  },
  {
    id: 'sec-012',
    block_type: 'text',
    order: 12,
    text: 'Immediate priorities: (1) Retain an accident reconstruction expert to perform independent speed analysis using dashcam GPS data and vehicle deformation modeling. (2) Order cervical and lumbar MRI within 30 days to establish objective imaging evidence of injury. (3) Identify and subpoena the third-party witness referenced in the police report. (4) Preserve the dashcam device and associated GPS data via litigation hold. The directional conflict between the police report and client statement requires resolution before any demand letter is issued — this discrepancy, if unresolved, represents a material vulnerability in the liability narrative.',
    citations: [],
    entity_ids: [],
  },
];

// ─── Entity Detail ─────────────────────────────────────────────────────────────

export const MOCK_ENTITY_DETAILS: Record<string, EntityDetailResponse> = {
  'ent-001': {
    entity: MOCK_ENTITIES[0],
    mentions: [],
    facts: [
      { fact: 'Was stationary at red light when collision occurred', dimension: 'Liability Attribution', source: 'Police report', evidence_id: 'ev-001', excerpt: 'Plaintiff vehicle stationary at intersection signal', reliability: 0.92 },
      { fact: 'Sustained cervical tenderness at C5-C6 level', dimension: 'Injury Causation', source: 'Medical record', evidence_id: 'ev-002', excerpt: 'Physical exam: cervical tenderness C5-C6', reliability: 0.88 },
      { fact: 'Estimated Thompson\'s speed at 45-50 mph', dimension: 'Speed & Velocity', source: 'Witness statement', evidence_id: 'ev-003', excerpt: 'He was going way too fast, at least 45 mph', reliability: 0.55 },
      { fact: 'Was driving alone at time of incident', dimension: 'Traffic Conditions', source: 'Police report', evidence_id: 'ev-001', excerpt: 'No passengers in plaintiff vehicle', reliability: 0.95 },
    ],
    contradictions: [MOCK_ANALYSIS.contradictions.items[0], MOCK_ANALYSIS.contradictions.items[1]],
  },
  'ent-002': {
    entity: MOCK_ENTITIES[1],
    mentions: [],
    facts: [
      { fact: 'Operating vehicle at time of collision', dimension: 'Liability Attribution', evidence_id: 'ev-001', excerpt: 'Thompson, Marcus — driver of striking vehicle', reliability: 0.98 },
      { fact: 'Speed estimated at 35 mph by police report', dimension: 'Speed & Velocity', evidence_id: 'ev-001', excerpt: 'Vehicle estimated at 35 mph based on physical evidence', reliability: 0.70 },
      { fact: 'Device visible in vehicle prior to impact', dimension: 'Driver Conduct', evidence_id: 'ev-006', excerpt: 'Device visible in driver seat area', reliability: 0.81 },
      { fact: 'Airbag deployed indicating significant impact', dimension: 'Vehicle Damage Severity', evidence_id: 'ev-005', excerpt: 'Airbag deployment confirmed post-collision', reliability: 0.96 },
    ],
    contradictions: [MOCK_ANALYSIS.contradictions.items[0], MOCK_ANALYSIS.contradictions.items[1]],
  },
};

// ─── Full Case ─────────────────────────────────────────────────────────────────

export const MOCK_FULL_CASE: FullCase = {
  case_id: MOCK_CASE_ID,
  title: MOCK_CASE_TITLE,
  case_type: 'Personal Injury — Motor Vehicle Collision',
  evidence: MOCK_EVIDENCE,
  entities: MOCK_ENTITIES,
  contradictions: MOCK_ANALYSIS.contradictions.items,
  missing_info: MOCK_ANALYSIS.missing_info.items,
  report_sections: MOCK_REPORT_SECTIONS,
};
