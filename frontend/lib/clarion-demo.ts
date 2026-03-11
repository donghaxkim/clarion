import type { GenerateReportRequest } from "@/lib/clarion-types";

export const demoReportRequest: GenerateReportRequest = {
  user_id: "clarion-creative-director-demo",
  enable_public_context: true,
  max_images: 2,
  max_reconstructions: 1,
  bundle: {
    case_id: "clarion-demo-collision-042",
    case_summary:
      "Multi-source collision review for a nighttime intersection crash, assembled for a polished courtroom narrative demo.",
    generation_instructions:
      "Write in a precise, courtroom-ready voice. Keep the chronology clear, cinematic, and evidence-grounded. Surface public context as separate context blocks only.",
    evidence_items: [
      {
        evidence_id: "ev-dashcam-01",
        kind: "video",
        title: "Dashcam Footage",
        summary:
          "The eastbound sedan enters the intersection on a yellow light as the northbound pickup turns across traffic.",
        extracted_text:
          "Timestamp overlay shows 9:18 PM. The sedan brakes late and impact occurs in the middle of the intersection.",
        media_uri: null,
        source_uri: null,
        source_spans: [
          {
            segment_id: "dashcam-impact",
            time_range_ms: [18000, 26500],
            snippet:
              "Sedan enters on yellow, pickup turns left, and the vehicles collide in the center lane.",
          },
        ],
        metadata: {
          source: "vehicle_dashcam",
          captured_at: "2025-11-14T21:18:00Z",
        },
        confidence_score: 0.96,
      },
      {
        evidence_id: "ev-witness-01",
        kind: "transcript",
        title: "Witness Transcript",
        summary:
          "A pedestrian reports seeing the pickup begin the turn before the intersection was clear.",
        extracted_text:
          "The truck moved into the turn while the sedan was already committed to the intersection.",
        media_uri: null,
        source_uri: null,
        source_spans: [
          {
            segment_id: "witness-turn",
            snippet:
              "The truck started turning before the path was open, and the car did not have room to avoid it.",
          },
        ],
        metadata: {
          source: "witness_statement",
        },
        confidence_score: 0.82,
      },
      {
        evidence_id: "ev-scene-photo-01",
        kind: "image",
        title: "Intersection Scene Photo",
        summary:
          "Police scene photo shows the resting positions of both vehicles and the lane markings.",
        extracted_text: null,
        media_uri: null,
        source_uri: null,
        source_spans: [
          {
            segment_id: "scene-photo-resting",
            snippet:
              "Both vehicles rest slightly north-east of the lane center after the collision.",
          },
        ],
        metadata: {
          source: "scene_photo",
        },
        confidence_score: 0.88,
      },
      {
        evidence_id: "ev-police-report-01",
        kind: "official_record",
        title: "Police Preliminary Report",
        summary:
          "The officer records moderate front-end damage to the sedan and right-side damage to the pickup.",
        extracted_text:
          "Road conditions were dry, visibility was clear, and traffic signals were functioning.",
        media_uri: null,
        source_uri: null,
        source_spans: [
          {
            page_number: 2,
            snippet:
              "Traffic signals functioning normally. Roadway dry. Moderate vehicle damage noted.",
          },
        ],
        metadata: {
          source: "police_report",
        },
        confidence_score: 0.9,
      },
    ],
    event_candidates: [
      {
        event_id: "approach",
        title: "Vehicles Approach the Intersection",
        description:
          "The sedan proceeds eastbound toward the intersection while the pickup approaches from the opposite direction and prepares for a left turn.",
        sort_key: "0001",
        timestamp_label: "9:18 PM",
        evidence_refs: ["ev-dashcam-01", "ev-police-report-01"],
        scene_description:
          "Nighttime intersection with active traffic signals, an eastbound sedan, and an oncoming pickup setting up for a left turn.",
        image_prompt_hint:
          "A documentary-style wide shot of a nighttime city intersection moments before a two-vehicle collision, with clear traffic lights and lane markings.",
        reference_image_uris: [],
        public_context_queries: [
          "standard yellow-light timing urban intersection",
          "left-turn collision right of way general guidance",
        ],
      },
      {
        event_id: "turn",
        title: "Pickup Commits to the Turn",
        description:
          "The pickup begins turning left across the sedan's lane before the path is fully clear, narrowing the sedan's available reaction window.",
        sort_key: "0002",
        timestamp_label: "9:18 PM",
        evidence_refs: ["ev-dashcam-01", "ev-witness-01"],
        scene_description:
          "The pickup enters a left turn across the sedan's path while the sedan continues through the intersection on a yellow light.",
        image_prompt_hint:
          "A tense, cinematic still of an oncoming pickup turning left across the path of an eastbound sedan in a lit urban intersection.",
        reference_image_uris: [],
        public_context_queries: [
          "common factors in intersection left-turn crashes",
        ],
      },
      {
        event_id: "impact",
        title: "Impact & Rest Positions",
        description:
          "The vehicles collide in the center of the intersection, then come to rest with damage patterns that match a crossing-path impact.",
        sort_key: "0003",
        timestamp_label: "9:18 PM",
        evidence_refs: [
          "ev-dashcam-01",
          "ev-scene-photo-01",
          "ev-police-report-01",
        ],
        scene_description:
          "Two vehicles collide at the center of a nighttime intersection and slide into their final resting positions under streetlights.",
        image_prompt_hint:
          "An evidence-board style overhead still of a nighttime intersection after a two-vehicle collision, showing resting positions and debris.",
        reference_image_uris: [],
        public_context_queries: [],
      },
    ],
    entities: [
      {
        entity_id: "entity-sedan-driver",
        name: "Sedan Driver",
        role: "Claimant",
        description:
          "Driver of the eastbound sedan shown in the dashcam sequence.",
      },
      {
        entity_id: "entity-pickup-driver",
        name: "Pickup Driver",
        role: "Opposing Driver",
        description:
          "Driver of the northbound pickup that initiated the left turn.",
      },
      {
        entity_id: "entity-witness-01",
        name: "Pedestrian Witness",
        role: "Witness",
        description:
          "Independent witness positioned near the south-west corner of the intersection.",
      },
    ],
  },
};
