"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Suspense,
  startTransition,
  type KeyboardEvent,
  type MouseEvent,
  useEffect,
  useEffectEvent,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  formatBlockType,
  formatCitationLocator,
  formatProvenance,
  formatStatusLabel,
  getPrimaryMedia,
} from "@/lib/clarion-format";
import type {
  Citation,
  MediaAsset,
  ReportBlock,
  ReportDocument,
  ReportGenerationActivity,
  ReportGenerationJobStatusResponse,
  ReportStatus,
} from "@/lib/clarion-types";

const streamEventTypes = [
  "job.started",
  "job.activity",
  "report.preview.updated",
  "timeline.ready",
  "block.created",
  "media.started",
  "block.updated",
  "media.completed",
  "job.completed",
  "job.failed",
] as const;

const emptySections: ReportBlock[] = [];

type StreamState = "live" | "reconnecting" | "closed";

interface JobReportExperienceBoundaryProps {
  initialJob: ReportGenerationJobStatusResponse;
}

interface StandaloneReportExperienceBoundaryProps {
  initialReport: ReportDocument;
}

interface ExperienceViewerProps {
  mode: "job" | "report";
  report: ReportDocument | null;
  warnings: string[];
  streamState: StreamState;
  progress?: number;
  status: string;
  reportId: string;
  jobId?: string;
  error?: string | null;
  activity?: ReportGenerationActivity | null;
}

export function JobReportExperienceBoundary({
  initialJob,
}: JobReportExperienceBoundaryProps) {
  return (
    <Suspense fallback={<ReportExperienceFallback />}>
      <LiveJobExperience initialJob={initialJob} />
    </Suspense>
  );
}

export function StandaloneReportExperienceBoundary({
  initialReport,
}: StandaloneReportExperienceBoundaryProps) {
  return (
    <Suspense fallback={<ReportExperienceFallback />}>
      <ExperienceViewer
        mode="report"
        report={initialReport}
        warnings={initialReport.warnings}
        streamState="closed"
        reportId={initialReport.report_id}
        status={initialReport.status}
        activity={null}
      />
    </Suspense>
  );
}

function LiveJobExperience({
  initialJob,
}: {
  initialJob: ReportGenerationJobStatusResponse;
}) {
  const [job, setJob] = useState(initialJob);
  const [streamState, setStreamState] = useState<StreamState>(
    isTerminalStatus(initialJob.status) ? "closed" : "live",
  );

  const syncLatestJob = useEffectEvent(async () => {
    try {
      const response = await fetch(`/api/report-jobs/${job.job_id}`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(await readResponseDetail(response));
      }

      const nextJob =
        (await response.json()) as ReportGenerationJobStatusResponse;

      startTransition(() => {
        setJob(nextJob);
        setStreamState(isTerminalStatus(nextJob.status) ? "closed" : "live");
      });
    } catch {
      startTransition(() => {
        setStreamState("reconnecting");
      });
    }
  });

  useEffect(() => {
    if (isTerminalStatus(job.status)) {
      return;
    }

    const eventSource = new EventSource(`/api/report-jobs/${job.job_id}/stream`);

    eventSource.onopen = () => {
      setStreamState("live");
    };

    const refreshFromEvent = () => {
      void syncLatestJob();
    };

    streamEventTypes.forEach((eventType) => {
      eventSource.addEventListener(eventType, refreshFromEvent);
    });

    eventSource.onerror = () => {
      setStreamState("reconnecting");
      void syncLatestJob();
    };

    return () => {
      eventSource.close();
    };
  }, [job.job_id, job.status]);

  return (
    <ExperienceViewer
      mode="job"
      report={job.report ?? null}
      warnings={dedupeWarnings(job.report?.warnings, job.warnings)}
      streamState={streamState}
      progress={job.progress}
      status={job.status}
      reportId={job.report_id}
      jobId={job.job_id}
      error={job.error}
      activity={job.activity ?? null}
    />
  );
}

function ExperienceViewer({
  mode,
  report,
  warnings,
  streamState,
  progress,
  status,
  reportId,
  jobId,
  error,
  activity,
}: ExperienceViewerProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const sections = report?.sections ?? emptySections;
  const selectedBlockId = searchParams.get("section");
  const selectedBlock =
    sections.find((block) => block.id === selectedBlockId) ?? null;

  const overviewItems = useMemo(
    () =>
      sections.map((block, index) => ({
        id: block.id,
        index: index + 1,
        label: block.title ?? fallbackBlockTitle(block),
        type: block.type,
      })),
    [sections],
  );

  const pendingCount = sections.filter((block) => block.state === "pending").length;
  const narrativeCount = sections.filter((block) => block.type === "text").length;
  const evidenceCount = sections.reduce(
    (total, block) => total + block.citations.length,
    0,
  );

  const liveAnnouncement = getLiveAnnouncement({
    mode,
    progress,
    sectionCount: sections.length,
    status,
    streamState,
    error,
    activity,
  });

  function setViewerState(nextSection: string | null) {
    const params = new URLSearchParams(searchParams.toString());

    if (nextSection) {
      params.set("section", nextSection);
      params.set("panel", "citations");
    } else {
      params.delete("section");
      params.delete("panel");
    }

    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, {
      scroll: false,
    });
  }

  function scrollToSection(blockId: string) {
    const target = document.getElementById(blockId);
    if (!target) {
      return;
    }

    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    target.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
      block: "start",
    });
  }

  function openSection(blockId: string) {
    setViewerState(blockId);
    scrollToSection(blockId);
  }

  function closePanel() {
    setViewerState(null);
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-ink text-paper">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(214,125,68,0.18),_transparent_45%),radial-gradient(circle_at_bottom_left,_rgba(181,76,36,0.16),_transparent_30%),linear-gradient(180deg,_rgba(8,7,6,0.98),_rgba(18,15,13,1))]" />
      <div className="grain-overlay absolute inset-0 opacity-45" aria-hidden="true" />
      <div className="sr-only" aria-live="polite">
        {liveAnnouncement}
      </div>

      <div className="relative mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-6 px-4 py-6 md:px-6 xl:flex-row xl:gap-8 xl:px-10 xl:py-10">
        <aside className="hidden w-72 shrink-0 xl:block">
          <nav
            aria-label="Report chronology"
            className="sticky top-6 rounded-[2rem] border border-paper/10 bg-paper/6 p-6 backdrop-blur"
          >
            <p className="font-mono text-xs uppercase tracking-[0.35em] text-amber">
              Chronology Rail
            </p>
            <ol className="mt-6 space-y-3">
              {overviewItems.map((item) => {
                const isSelected = item.id === selectedBlock?.id;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => openSection(item.id)}
                      aria-pressed={isSelected}
                      className={`group flex w-full items-start gap-3 rounded-[1.5rem] border px-4 py-3 text-left transition-transform transition-colors duration-200 hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2 focus-visible:ring-offset-ink ${
                        isSelected
                          ? "border-amber/40 bg-amber/12"
                          : "border-paper/10 bg-ink-soft hover:border-paper/25 hover:bg-paper/6"
                      }`}
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-paper/12 bg-paper/8 font-mono text-xs text-paper/70">
                        {item.index.toString().padStart(2, "0")}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-xs uppercase tracking-[0.24em] text-paper/50">
                          {formatBlockType(item.type)}
                        </span>
                        <span className="mt-1 block text-pretty text-sm font-medium text-paper">
                          {item.label}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>
        </aside>

        <main
          id="main-content"
          className="min-w-0 flex-1 pb-[max(8rem,env(safe-area-inset-bottom))]"
        >
          <section className="rounded-[2rem] border border-paper/10 bg-paper/6 p-6 shadow-[0_32px_120px_rgba(0,0,0,0.28)] backdrop-blur md:p-8">
            <div className="flex flex-wrap items-start justify-between gap-6">
              <div className="max-w-3xl">
                <p className="font-mono text-xs uppercase tracking-[0.35em] text-amber">
                  {mode === "job" ? "Director Console" : "Shareable Viewer"}
                </p>
                <h1 className="mt-4 max-w-3xl text-balance font-display text-4xl leading-tight text-paper md:text-6xl">
                  Clarion reframes the report as a living evidence sequence.
                </h1>
                <p className="mt-4 max-w-2xl text-base leading-7 text-paper/72 md:text-lg">
                  The left rail keeps the chronology legible while the report
                  itself stays continuous. Select any section to reveal its
                  source trail in the margin without breaking the reading flow.
                </p>
              </div>
              <StatusCard
                mode={mode}
                progress={progress}
                report={report}
                reportId={reportId}
                jobId={jobId}
                status={status}
                streamState={streamState}
                activity={activity}
              />
            </div>

            {warnings.length > 0 ? <WarningsBanner warnings={warnings} /> : null}

            {error ? (
              <p className="mt-6 rounded-[1.5rem] border border-rust/40 bg-rust/14 px-4 py-3 text-sm leading-6 text-paper">
                {error}
              </p>
            ) : null}

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <MetricCard
                label="Narrative Blocks"
                value={narrativeCount}
                note="Evidence-grounded scenes"
              />
              <MetricCard
                label="Citation Links"
                value={evidenceCount}
                note="Attached claim references"
              />
              <MetricCard
                label="Pending Media"
                value={pendingCount}
                note="Replaced as assets complete"
              />
            </div>
          </section>

          <div className="mt-6 flex gap-3 overflow-x-auto pb-1 xl:hidden">
            {overviewItems.map((item) => {
              const isSelected = item.id === selectedBlock?.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => openSection(item.id)}
                  className={`shrink-0 rounded-full border px-4 py-2 text-sm transition-transform transition-colors duration-200 hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2 focus-visible:ring-offset-ink ${
                    isSelected
                      ? "border-amber/40 bg-amber/12 text-paper"
                      : "border-paper/12 bg-paper/6 text-paper/70"
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>

          <section className="mt-8 overflow-hidden rounded-[2.25rem] border border-paper/12 bg-[#f6efe6] text-[#1b1510] shadow-[0_32px_120px_rgba(0,0,0,0.28)]">
            <div className="border-b border-[#ddcdbd] px-6 py-6 md:px-10 lg:px-12">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div className="max-w-3xl">
                  <p className="font-mono text-xs uppercase tracking-[0.35em] text-[#9a5a34]">
                    Report Document
                  </p>
                  <h2 className="mt-4 text-balance font-display text-4xl leading-tight text-[#1b1510] md:text-5xl">
                    Continuous narrative, citation-aware on demand.
                  </h2>
                  <p className="mt-4 max-w-2xl text-base leading-7 text-[#5f5144]">
                    The document reads as one uninterrupted sequence. When a
                    section is selected, Clarion opens its citations in the
                    margin beside that scene.
                  </p>
                </div>
                <div className="rounded-[1.5rem] border border-[#ddcdbd] bg-white/50 px-4 py-3 text-sm leading-6 text-[#5f5144]">
                  {selectedBlock
                    ? `${selectedBlock.citations.length} source(s) attached to the active section.`
                    : `${sections.length} section(s) staged in the document.`}
                </div>
              </div>
            </div>

            <div className="px-6 py-4 md:px-10 lg:px-12">
              {sections.length === 0 ? (
                <EmptyReportState
                  mode={mode}
                  streamState={streamState}
                  status={status}
                />
              ) : (
                sections.map((block) => {
                  const isSelected = block.id === selectedBlock?.id;
                  return (
                    <SectionCard
                      key={block.id}
                      block={block}
                      isSelected={isSelected}
                      onSelect={() => openSection(block.id)}
                      onCloseCitations={closePanel}
                    />
                  );
                })
              )}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

function ReportExperienceFallback() {
  return (
    <div className="relative min-h-screen bg-ink text-paper">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(214,125,68,0.18),_transparent_45%),linear-gradient(180deg,_rgba(8,7,6,0.98),_rgba(18,15,13,1))]" />
      <div className="grain-overlay absolute inset-0 opacity-40" aria-hidden="true" />
      <div className="relative mx-auto flex min-h-screen max-w-[1600px] items-center px-4 py-12 md:px-6 xl:px-10">
        <section className="w-full rounded-[2rem] border border-paper/10 bg-paper/6 p-8 backdrop-blur">
          <p className="font-mono text-xs uppercase tracking-[0.35em] text-amber">
            Clarion Viewer
          </p>
          <h1 className="mt-4 max-w-2xl font-display text-4xl leading-tight text-paper">
            Loading the active report{"\u2026"}
          </h1>
        </section>
      </div>
    </div>
  );
}

function StatusCard({
  mode,
  progress,
  report,
  reportId,
  jobId,
  status,
  streamState,
  activity,
}: {
  mode: "job" | "report";
  progress?: number;
  report: ReportDocument | null;
  reportId: string;
  jobId?: string;
  status: string;
  streamState: StreamState;
  activity?: ReportGenerationActivity | null;
}) {
  const animatedProgress = useAnimatedProgress(
    progress,
    status,
    jobId ?? reportId,
  );
  const roundedProgress =
    typeof animatedProgress === "number"
      ? Math.round(Math.max(0, Math.min(100, animatedProgress)))
      : undefined;
  const progressValue =
    typeof roundedProgress === "number"
      ? `${roundedProgress}%`
      : formatStatusLabel(report?.status ?? "running");

  return (
    <div className="w-full max-w-sm rounded-[1.75rem] border border-paper/12 bg-ink-soft p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-xs uppercase tracking-[0.28em] text-paper/52">
          {mode === "job" ? "Live Status" : "Report Status"}
        </p>
        <StatusBadge status={status} streamState={streamState} />
      </div>
      <div className="mt-4">
        <p className="text-4xl font-semibold text-paper">{progressValue}</p>
        {typeof roundedProgress === "number" ? (
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-paper/10">
            <div
              className="h-full rounded-full bg-[linear-gradient(90deg,_rgba(214,125,68,1),_rgba(231,193,132,1))]"
              style={{ width: `${animatedProgress}%` }}
            />
          </div>
        ) : null}
      </div>
      <dl className="mt-5 space-y-3 text-sm text-paper/70">
        {jobId ? (
          <div className="flex items-start justify-between gap-3">
            <dt>Job ID</dt>
            <dd className="font-mono text-xs text-paper/60">{jobId}</dd>
          </div>
        ) : null}
        <div className="flex items-start justify-between gap-3">
          <dt>Report ID</dt>
          <dd className="font-mono text-xs text-paper/60">{reportId}</dd>
        </div>
        <div className="flex items-start justify-between gap-3">
          <dt>Share View</dt>
          <dd>
            <Link
              href={`/reports/${reportId}`}
              className="text-amber transition-colors duration-200 hover:text-amber-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2 focus-visible:ring-offset-ink-soft"
            >
              Open Report
            </Link>
          </dd>
        </div>
        <div className="flex items-start justify-between gap-3">
          <dt>State</dt>
          <dd>{formatStatusLabel(report?.status ?? (status as ReportStatus))}</dd>
        </div>
      </dl>
      {mode === "job" ? (
        <div className="mt-5 rounded-[1.35rem] border border-paper/12 bg-paper/6 px-4 py-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-paper/48">
            Currently Working
          </p>
          <p className="mt-3 text-base leading-7 text-paper">
            {activity?.label ?? "Clarion is preparing the next report step."}
          </p>
          <p className="mt-2 text-sm leading-6 text-paper/60">
            {activity?.detail ??
              "The live console will surface the active agent as soon as the backend reports it."}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function SectionCard({
  block,
  isSelected,
  onSelect,
  onCloseCitations,
}: {
  block: ReportBlock;
  isSelected: boolean;
  onSelect: () => void;
  onCloseCitations: () => void;
}) {
  const media = getPrimaryMedia(block);
  const isPublicContext = block.provenance === "public_context";

  function handleSelectFromPointer(event: MouseEvent<HTMLElement>) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    if (target.closest("a, button, input, select, textarea, video, summary")) {
      return;
    }

    onSelect();
  }

  function handleSelectFromKeyboard(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }

    event.preventDefault();
    onSelect();
  }

  return (
    <article
      id={block.id}
      tabIndex={0}
      onClick={handleSelectFromPointer}
      onKeyDown={handleSelectFromKeyboard}
      className={`section-anchor relative py-10 outline-none transition-colors duration-200 first:pt-0 last:pb-0 focus-visible:ring-2 focus-visible:ring-[#c66f3d] focus-visible:ring-offset-4 focus-visible:ring-offset-[#f6efe6] ${
        isSelected
          ? "bg-[linear-gradient(90deg,rgba(214,125,68,0.1),rgba(214,125,68,0.03)_24%,transparent_48%)]"
          : "hover:bg-black/[0.02]"
      }`}
    >
      <div className="absolute inset-x-0 bottom-0 h-px bg-[#ddcdbd]" aria-hidden="true" />
      {isSelected ? (
        <div
          className="absolute bottom-6 left-0 top-6 w-px bg-[linear-gradient(180deg,rgba(214,125,68,0),rgba(214,125,68,0.7),rgba(214,125,68,0))]"
          aria-hidden="true"
        />
      ) : null}

      <div
        className={`relative ${isSelected ? "xl:grid xl:grid-cols-[minmax(0,1fr)_20rem] xl:items-start xl:gap-10" : ""}`}
      >
        <div className="min-w-0 pr-0 xl:pr-4">
          <header className="max-w-3xl">
            <h2 className="text-balance font-display text-3xl leading-tight text-[#1b1510] md:text-4xl">
              {block.title ?? fallbackBlockTitle(block)}
            </h2>
            {block.state === "pending" ? (
              <p className="mt-3 text-sm leading-6 text-[#7b6655]">
                {block.type === "image" || block.type === "video"
                  ? `Media for this section is still rendering${"\u2026"}`
                  : "This section is still updating."}
              </p>
            ) : null}
          </header>

          {isPublicContext ? (
            <div className="mt-5 rounded-[1.35rem] bg-[#eee3d7] px-5 py-4 text-sm leading-6 text-[#6d5b4c]">
              This passage provides public context for the chronology. It is
              visually separated from direct evidence-backed narration.
            </div>
          ) : null}

          {block.content ? (
            <div className="mt-6 max-w-none text-pretty text-lg leading-8 text-[#2e241c]">
              <p className="break-words whitespace-pre-wrap">{block.content}</p>
            </div>
          ) : null}

          <div className="mt-6">
            <MediaStage block={block} media={media} />
          </div>
        </div>

        {isSelected ? (
          <div className="mt-6 xl:mt-1">
            <CitationsPanel block={block} onClose={onCloseCitations} />
          </div>
        ) : null}
      </div>
    </article>
  );
}

function MediaStage({
  block,
  media,
}: {
  block: ReportBlock;
  media: MediaAsset | null;
}) {
  if (block.type === "image" && media?.kind === "image") {
    return (
      <div className="relative aspect-[16/9] overflow-hidden rounded-[1.75rem] border border-[#ddcdbd] bg-[#efe5d9]">
        <Image
          src={media.uri}
          alt={
            block.title
              ? `Generated illustration for ${block.title}`
              : "Generated report illustration"
          }
          fill
          priority={false}
          sizes="(max-width: 768px) 100vw, (max-width: 1400px) 68vw, 52vw"
          className="object-cover"
        />
        <MediaMeta generator={media.generator} manifestUri={media.manifest_uri} />
      </div>
    );
  }

  if (block.type === "video" && media?.kind === "video") {
    return (
      <div className="overflow-hidden rounded-[1.75rem] border border-[#ddcdbd] bg-[#efe5d9]">
        <div className="aspect-[16/9]">
          <video controls playsInline preload="metadata" className="h-full w-full">
            <source src={media.uri} />
          </video>
        </div>
        <MediaMeta generator={media.generator} manifestUri={media.manifest_uri} />
      </div>
    );
  }

  if (block.type === "image" || block.type === "video") {
    return (
      <div className="relative overflow-hidden rounded-[1.75rem] border border-[#ddcdbd] bg-[linear-gradient(135deg,_rgba(214,125,68,0.16),_rgba(255,255,255,0.72))] p-8">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(231,193,132,0.24),_transparent_32%)]" />
        <div className="relative flex min-h-56 flex-col justify-between gap-6">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.28em] text-[#8d6a53]">
              {block.type === "image" ? "Illustration Stage" : "Reconstruction Stage"}
            </p>
            <h3 className="mt-4 text-balance font-display text-3xl leading-tight text-[#1b1510]">
              {block.state === "pending"
                ? `Media is being woven into the sequence${"\u2026"}`
                : "Media asset not available."}
            </h3>
            <p className="mt-3 max-w-2xl text-base leading-7 text-[#5f5144]">
              {block.content ??
                "Clarion reserved this block for generated media tied to the chronology."}
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="h-16 rounded-[1.25rem] border border-[#ddcdbd] bg-white/55"
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return null;
}

function MediaMeta({
  generator,
  manifestUri,
}: {
  generator: string;
  manifestUri?: string | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-[#ddcdbd] bg-[#f1e7dc]/90 px-5 py-4 text-xs uppercase tracking-[0.2em] text-[#6d5b4c]">
      <span>Generated with {generator}</span>
      {manifestUri ? (
        <a
          href={manifestUri}
          className="text-[#9a5a34] transition-colors duration-200 hover:text-[#bc7441] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#c66f3d] focus-visible:ring-offset-2 focus-visible:ring-offset-[#f1e7dc]"
        >
          Manifest Reference
        </a>
      ) : null}
    </div>
  );
}

function CitationsPanel({
  block,
  onClose,
}: {
  block: ReportBlock;
  onClose: () => void;
}) {
  return (
    <aside className="rounded-[1.75rem] border border-[#ddcdbd] bg-[#fbf6ef] p-5 shadow-[0_16px_40px_rgba(0,0,0,0.08)]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-[#9a5a34]">
            Citations
          </p>
          <h3 className="mt-2 text-lg font-semibold text-[#1b1510]">
            Sources for this section
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center justify-center rounded-full border border-[#ddcdbd] bg-white/70 px-3 py-2 text-sm font-medium text-[#5f5144] transition-colors duration-200 hover:border-[#caa78d] hover:text-[#1b1510] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#c66f3d] focus-visible:ring-offset-2 focus-visible:ring-offset-[#fbf6ef]"
        >
          Hide
        </button>
      </div>
      <div className="mt-4 text-sm text-[#6d5b4c]">
        {block.citations.length} source(s)
      </div>
      <div className="mt-4 space-y-3">
        {block.citations.length > 0 ? (
          block.citations.map((citation, index) => (
            <CitationCard
              key={`${citation.source_id}-${index}`}
              citation={citation}
            />
          ))
        ) : (
          <p className="rounded-[1.5rem] border border-[#ddcdbd] bg-white/70 px-4 py-4 text-sm leading-6 text-[#6d5b4c]">
            This section has no structured citation payload yet.
          </p>
        )}
      </div>
    </aside>
  );
}

function CitationCard({ citation }: { citation: Citation }) {
  const locator = formatCitationLocator(citation);

  return (
    <article className="rounded-[1.5rem] border border-[#ddcdbd] bg-white/72 px-4 py-4">
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-[#8d6a53]">
          {formatProvenance(citation.provenance)}
        </span>
        <span className="rounded-full border border-[#ddcdbd] bg-[#f5ece2] px-3 py-1 font-mono text-[11px] uppercase tracking-[0.16em] text-[#6d5b4c]">
          {citation.source_id}
        </span>
      </div>
      {locator ? (
        <p className="mt-3 text-sm leading-6 text-[#6d5b4c]">{locator}</p>
      ) : null}
      {citation.snippet ? (
        <p className="mt-3 break-words text-base leading-7 text-[#2e241c]">
          {citation.snippet}
        </p>
      ) : (
        <p className="mt-3 text-sm leading-6 text-[#8d7a67]">
          No inline snippet was returned for this source.
        </p>
      )}
      {citation.uri ? (
        <a
          href={citation.uri}
          className="mt-4 inline-flex text-sm font-medium text-[#9a5a34] transition-colors duration-200 hover:text-[#bc7441] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#c66f3d] focus-visible:ring-offset-2 focus-visible:ring-offset-[#ffffff]"
        >
          Open Source Reference
        </a>
      ) : null}
    </article>
  );
}

function MetricCard({
  label,
  value,
  note,
}: {
  label: string;
  value: number;
  note: string;
}) {
  return (
    <div className="rounded-[1.5rem] border border-paper/12 bg-ink-soft p-4">
      <p className="text-sm uppercase tracking-[0.2em] text-paper/48">{label}</p>
      <p className="mt-3 text-3xl font-semibold text-paper">{value}</p>
      <p className="mt-2 text-sm leading-6 text-paper/60">{note}</p>
    </div>
  );
}

function WarningsBanner({ warnings }: { warnings: string[] }) {
  return (
    <div className="mt-6 rounded-[1.75rem] border border-rust/34 bg-rust/12 p-5">
      <p className="font-mono text-xs uppercase tracking-[0.3em] text-rust-light">
        Report Warnings
      </p>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-paper/78">
        {warnings.map((warning) => (
          <li key={warning} className="break-words">
            {warning}
          </li>
        ))}
      </ul>
    </div>
  );
}

function EmptyReportState({
  mode,
  streamState,
  status,
}: {
  mode: "job" | "report";
  streamState: StreamState;
  status: string;
}) {
  return (
    <section className="py-16 text-[#5f5144]">
      <p className="font-mono text-xs uppercase tracking-[0.3em] text-[#9a5a34]">
        {mode === "job" ? "Live Intake" : "Report Canvas"}
      </p>
      <h2 className="mt-4 font-display text-3xl text-[#1b1510]">
        {mode === "job"
          ? `Clarion is building the first report blocks${"\u2026"}`
          : "This report does not have any sections yet."}
      </h2>
      <p className="mt-4 max-w-2xl text-base leading-7">
        {mode === "job"
          ? `Current state: ${formatStatusLabel(status as ReportStatus)}. Stream status: ${streamState}.`
          : "Check the backend job record to confirm the report finished composing."}
      </p>
    </section>
  );
}

function StatusBadge({
  status,
  streamState,
}: {
  status: string;
  streamState: StreamState;
}) {
  const tone =
    status === "failed"
      ? "border-rust/40 bg-rust/16 text-rust-light"
      : status === "completed"
        ? "border-amber/30 bg-amber/12 text-amber-soft"
        : "border-paper/16 bg-paper/8 text-paper/72";

  return (
    <span
      className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${tone}`}
    >
      {streamState === "reconnecting" && status !== "completed"
        ? "Reconnecting"
        : formatStatusLabel(status as ReportStatus)}
    </span>
  );
}

function dedupeWarnings(
  reportWarnings: string[] | undefined,
  jobWarnings: string[] | undefined,
) {
  return Array.from(new Set([...(reportWarnings ?? []), ...(jobWarnings ?? [])]));
}

function getLiveAnnouncement({
  mode,
  progress,
  sectionCount,
  status,
  streamState,
  error,
  activity,
}: {
  mode: "job" | "report";
  progress?: number;
  sectionCount: number;
  status: string;
  streamState: StreamState;
  error?: string | null;
  activity?: ReportGenerationActivity | null;
}) {
  if (error) {
    return error;
  }

  if (mode === "report") {
    return `Report status ${formatStatusLabel(status as ReportStatus)} with ${sectionCount} section(s).`;
  }

  const progressLabel =
    typeof progress === "number"
      ? `${progress}%`
      : formatStatusLabel(status as ReportStatus);

  if (streamState === "reconnecting") {
    return `Live stream reconnecting. Latest status ${progressLabel}.`;
  }

  if (activity?.label) {
    return `${activity.label}. ${activity.detail ?? `Latest status ${progressLabel}.`}`;
  }

  return `Report ${formatStatusLabel(status as ReportStatus)} at ${progressLabel} with ${sectionCount} section(s).`;
}

function fallbackBlockTitle(block: ReportBlock) {
  return `${formatBlockType(block.type)} Block`;
}

function isTerminalStatus(status: string) {
  return status === "completed" || status === "failed";
}

function useAnimatedProgress(
  progress: number | undefined,
  status: string,
  identity: string,
) {
  const normalizedProgress =
    typeof progress === "number"
      ? Math.max(0, Math.min(100, progress))
      : undefined;
  const [displayProgress, setDisplayProgress] = useState<number | undefined>(
    normalizedProgress,
  );
  const displayProgressRef = useRef<number | undefined>(normalizedProgress);
  const normalizedProgressRef = useRef<number | undefined>(normalizedProgress);
  const animationFrameRef = useRef<number | null>(null);
  const syncFrameRef = useRef<number | null>(null);

  function scheduleProgressSync(nextProgress: number | undefined) {
    if (syncFrameRef.current !== null) {
      cancelAnimationFrame(syncFrameRef.current);
    }

    syncFrameRef.current = requestAnimationFrame(() => {
      displayProgressRef.current = nextProgress;
      startTransition(() => {
        setDisplayProgress(nextProgress);
      });
      syncFrameRef.current = null;
    });
  }

  useEffect(() => {
    displayProgressRef.current = displayProgress;
  }, [displayProgress]);

  useEffect(() => {
    normalizedProgressRef.current = normalizedProgress;
  }, [normalizedProgress]);

  useEffect(() => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    scheduleProgressSync(normalizedProgressRef.current);
  }, [identity]);

  useEffect(() => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    if (normalizedProgress === undefined) {
      scheduleProgressSync(undefined);
      return;
    }

    const currentProgress = displayProgressRef.current;
    if (status === "failed") {
      const frozenProgress = currentProgress ?? normalizedProgress;
      if (frozenProgress !== currentProgress) {
        scheduleProgressSync(frozenProgress);
      }
      return;
    }

    if (currentProgress === undefined) {
      scheduleProgressSync(normalizedProgress);
      return;
    }

    if (normalizedProgress <= currentProgress) {
      return;
    }

    if (
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      scheduleProgressSync(normalizedProgress);
      return;
    }

    let lastFrameAt: number | null = null;

    const tick = (frameAt: number) => {
      const previousValue = displayProgressRef.current ?? currentProgress;
      const elapsedMs = lastFrameAt === null ? 16 : frameAt - lastFrameAt;
      lastFrameAt = frameAt;

      const nextValue = Math.min(
        normalizedProgress,
        previousValue + Math.max(0.6, (elapsedMs / 1000) * 36),
      );

      displayProgressRef.current = nextValue;
      startTransition(() => {
        setDisplayProgress(nextValue);
      });

      if (nextValue >= normalizedProgress) {
        animationFrameRef.current = null;
        return;
      }

      animationFrameRef.current = requestAnimationFrame(tick);
    };

    animationFrameRef.current = requestAnimationFrame(tick);
    return () => {
      if (syncFrameRef.current !== null) {
        cancelAnimationFrame(syncFrameRef.current);
        syncFrameRef.current = null;
      }
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [normalizedProgress, status]);

  return displayProgress;
}

async function readResponseDetail(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? "Clarion did not return a usable response.";
  } catch {
    return "Clarion did not return a usable response.";
  }
}
