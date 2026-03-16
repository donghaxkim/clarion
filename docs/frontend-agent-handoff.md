# Frontend Agent Handoff

This project now has a working Next.js frontend for launching report jobs, following live job progress, and viewing completed reports as a continuous narrative document with inline media and on-demand citations.

## What Exists

- `frontend/app/page.tsx`
  - Marketing/demo landing page for the current frontend direction.
  - Launches the built-in demo case through the frontend API proxy.
  - Mirrors the current report UX:
    - chronology rail
    - continuous document body
    - citations in the active section margin
- `frontend/app/jobs/[jobId]/page.tsx`
  - Server-rendered entry point for the live job experience.
  - Fetches initial job state from the backend via `getReportJob()`.
- `frontend/app/reports/[reportId]/page.tsx`
  - Server-rendered entry point for the standalone report viewer.
  - Fetches the completed report via `getReport()`.
- `frontend/app/_components/report-experience.tsx`
  - Main UI surface for both job and report routes.
  - Handles:
    - live SSE updates for jobs
    - refetch-on-event synchronization
    - chronology rail
    - continuous document rendering
    - media embedding
    - citation panel behavior
    - warnings, status, and empty states
- `frontend/app/_components/launch-demo-button.tsx`
  - Calls `POST /api/report-jobs` with no body to launch the built-in demo request.
  - Pushes the user into `/jobs/{jobId}` after the backend accepts the job.
- `frontend/app/_components/report-loading-shell.tsx`
  - Shared skeleton for both job and report loading routes.
- `frontend/app/_components/route-error-state.tsx`
  - Shared route-level error recovery UI for job/report route boundaries.
- `frontend/app/api/report-jobs/route.ts`
  - Frontend proxy route for launching report jobs.
  - Empty-body POST launches the demo case.
  - JSON-body POST forwards a real `GenerateReportRequest`.
- `frontend/app/api/report-jobs/[jobId]/route.ts`
  - Frontend proxy route for job status polling.
- `frontend/app/api/report-jobs/[jobId]/stream/route.ts`
  - Frontend proxy route for SSE job events.
- `frontend/app/api/reports/[reportId]/route.ts`
  - Frontend proxy route for fetching a report document.
- `frontend/lib/clarion-api.ts`
  - Server-only wrapper around backend calls.
  - Normalizes backend failures into `ClarionApiError`.
- `frontend/lib/clarion-types.ts`
  - TypeScript mirror of the report/job/media contract used by the backend.
- `frontend/lib/clarion-format.ts`
  - Small formatting helpers for labels, provenance, citation locators, and media selection.
- `frontend/app/layout.tsx`
  - Global metadata, fonts, skip link, and preconnect setup.
- `frontend/app/globals.css`
  - Current visual tokens and global interaction styling.
- `frontend/next.config.ts`
  - Allows remote media rendering from:
    - `storage.googleapis.com`
    - local backend artifact routes in dev

## Current Frontend UX

- The report UI is no longer a stack of bordered cards.
  - The main document is intended to read like one continuous memo/Notion-style document.
  - Sections are separated by subtle divider lines and selection background, not boxed cards.
- Per-block metadata chrome was intentionally removed.
  - No date line.
  - No type pill.
  - No `EVIDENCE` tag.
  - No confidence tag.
  - No "Edit this section" action.
- Citations no longer render at the bottom of each section.
  - Selecting a section opens its citations beside the active block on desktop.
  - On narrower layouts, the citations render below the selected block.
- The document still keeps a chronology navigation layer.
  - Desktop uses a sticky left rail.
  - Smaller screens use horizontal section pills above the document.
- Public-context passages remain visually distinguished from evidence-backed narration.
  - This is currently done with a muted contextual callout inside the section.
- Media blocks behave inline with the narrative.
  - Ready image/video assets render directly inside the document flow.
  - Pending media render as placeholder stages instead of collapsing the section.

## Current Data Flow

- The browser does not call the Python backend directly.
  - It talks to Next.js route handlers under `frontend/app/api/...`.
  - Those handlers call `frontend/lib/clarion-api.ts`.
  - `clarion-api.ts` talks to the backend using `CLARION_API_BASE_URL`.
- Job route flow:
  - `/jobs/[jobId]` fetches the initial job on the server.
  - `LiveJobExperience` opens `EventSource(/api/report-jobs/{jobId}/stream)`.
  - On each known event type, the client refetches `/api/report-jobs/{jobId}`.
  - If the stream errors, the UI falls back to `reconnecting` state and retries status reads.
- Report route flow:
  - `/reports/[reportId]` fetches the completed report on the server.
  - No live stream is attached to the standalone report page.
- Selection state is URL-driven.
  - Clicking a section sets `?section={blockId}&panel=citations`.
  - Closing the citation panel removes those params.
  - This gives deep-linkable section selection.

## Recent Frontend Work

- Reframed the report viewer around a continuous document instead of isolated cards.
- Removed section-level date/tag/confidence/edit controls.
- Moved citations from the bottom of each section into a contextual side panel for the selected block.
- Updated the landing page preview so the homepage reflects the current report interaction model.
- Kept the live job view and standalone report view on a shared rendering component so both surfaces stay visually aligned.
- Preserved streaming job updates and pending-media placeholders while changing the document presentation.

## Media Rendering and Backend Coupling

- The frontend assumes media URLs returned by the backend are browser-usable HTTPS URLs.
  - Images render through `next/image`.
  - Videos render through a native `<video>` element.
- Recent backend work changed the system to persist canonical `gs://...` paths and materialize browser URLs on read.
  - The frontend should not construct GCS URLs itself.
  - It should treat backend-returned `uri` values as final render URLs.
- `frontend/next.config.ts` must allow every host used for rendered images.
  - Current config allows `storage.googleapis.com`.
  - It also allows local backend artifact fallback routes on `localhost:8000` and `127.0.0.1:8000`.
- If a report/job fetch returns 500 after generation finishes, the root problem is often backend media materialization, not the frontend rendering code.
  - This already surfaced when required or optional GCS artifact URIs could not be signed locally.

## Config

- `frontend/.env`
  - Used for local frontend configuration.
- Important frontend env settings:
  - `CLARION_API_BASE_URL`
    - Backend origin used by `frontend/lib/clarion-api.ts`.
    - Defaults to `http://127.0.0.1:8000`.
  - `NEXT_PUBLIC_SITE_URL`
    - Used for metadata base/open graph URLs.

## Verification

- Current frontend validation path:
  - `npm run lint`
  - `npm run build`
- There is no dedicated frontend test suite yet.
  - No component tests.
  - No Playwright/E2E coverage.

## Known Gotchas

- `frontend/app/_components/report-experience.tsx` is the core viewer and is currently large.
  - Most report UX changes land here first.
  - Future agents should expect this file to be the main integration point for report layout, live state, and citations.
- The URL still writes `panel=citations`, and `frontend/lib/clarion-types.ts` still defines `ReportPanelMode = "citations" | "edit"`.
  - The edit UI has been removed.
  - `edit` is now stale type/query legacy and a cleanup candidate.
- The live job page can appear "stuck" even when the job is done if the backend status route starts failing.
  - In that case, inspect the frontend proxy route response first.
  - Then inspect backend report/job read failures, especially media URI materialization.
- Required media URLs must resolve before the report/job payload reaches the frontend.
  - The frontend has no special recovery path if a required image/video `uri` is missing or invalid.
- The viewer uses URL search params plus `router.replace()` for section selection.
  - Be careful not to break back/forward navigation or deep links when changing the selection model.
- `content-visibility: auto` is applied to `.section-anchor`.
  - Good for long documents.
  - Worth remembering if a future UI change seems to have odd layout/measurement timing.
- Route pages and API handlers are explicitly `runtime = "nodejs"`.
  - Keep that in mind before introducing edge-only assumptions or APIs.

## Current Limits

- The viewer is visually strong but not yet decomposed into smaller subcomponents.
- There is no report editing flow anymore, despite lingering type/query remnants.
- There is no frontend-side retry or partial-degradation UX for broken media beyond what the backend already returns.
- Citations only open for one selected section at a time.
- Mobile keeps the same selection model, but the citation panel falls below the block instead of acting like a real side rail.
- The frontend still depends heavily on backend contract stability.
  - There is no schema validation layer in the browser beyond TypeScript assumptions.

## Good Next Work

- Split `report-experience.tsx` into smaller viewer, rail, section, media, and citations components without changing behavior.
- Remove stale `edit` panel types/query handling if that feature is not coming back.
- Add frontend tests around:
  - job launch
  - live stream fallback behavior
  - selected-section URL state
  - citation panel rendering
  - pending/ready media transitions
- Improve surfaced error messages when backend media materialization fails, so the UI can distinguish "job still running" from "completed job cannot be rendered."
