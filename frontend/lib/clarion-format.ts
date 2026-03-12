import type {
  Citation,
  ReportBlock,
  ReportBlockType,
  ReportGenerationJobStatus,
  ReportProvenance,
  ReportStatus,
} from "@/lib/clarion-types";

const percentFormatter = new Intl.NumberFormat("en-US", {
  style: "percent",
  maximumFractionDigits: 0,
});

const utcDateFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

export function formatConfidence(score: number): string {
  return percentFormatter.format(Math.min(1, Math.max(0, score)));
}

export function formatStatusLabel(
  status: ReportGenerationJobStatus | ReportStatus,
): string {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatGeneratedAt(value?: string | null): string | null {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return `${utcDateFormatter.format(parsed)} UTC`;
}

export function formatBlockType(type: ReportBlockType): string {
  switch (type) {
    case "image":
      return "Image";
    case "video":
      return "Video";
    default:
      return "Narrative";
  }
}

export function formatProvenance(provenance: ReportProvenance): string {
  return provenance === "public_context" ? "Public Context" : "Evidence";
}

export function getPrimaryMedia(block: ReportBlock) {
  return block.media[0] ?? null;
}

export function formatCitationLocator(citation: Citation): string | null {
  const parts: string[] = [];

  if (citation.page_number) {
    parts.push(`Page ${citation.page_number}`);
  }

  if (citation.time_range_ms) {
    parts.push(formatTimeRange(citation.time_range_ms));
  }

  if (citation.segment_id) {
    parts.push(`Segment ${citation.segment_id}`);
  }

  return parts.length > 0 ? parts.join(" \u00b7 ") : null;
}

function formatTimeRange([startMs, endMs]: [number, number]): string {
  return `${formatMilliseconds(startMs)} to ${formatMilliseconds(endMs)}`;
}

function formatMilliseconds(milliseconds: number): string {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
