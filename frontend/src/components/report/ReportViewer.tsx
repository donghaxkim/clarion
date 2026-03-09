"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { createEventSource } from "@/lib/api";
import type {
  ReportSection,
  StreamEventData,
  Citation,
  ContradictionItem,
} from "@/lib/types";
import { MOCK_REPORT_SECTIONS } from "@/lib/mock-data";
import { ReportBlock } from "./ReportBlock";

interface ReportViewerProps {
  streamId: string;
  caseId: string;
  citations: Record<string, Citation>;
  contradictions: ContradictionItem[];
  onContradictionClick?: (id: string) => void;
  onEditSection?: (sectionId: string) => void;
}

export function ReportViewer({
  streamId,
  caseId,
  citations,
  contradictions,
  onContradictionClick,
  onEditSection,
}: ReportViewerProps) {
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingBlockType, setStreamingBlockType] = useState<ReportSection["block_type"]>("text");
  const [streamingHeadingLevel, setStreamingHeadingLevel] = useState<number | undefined>();
  const [streamingCitationIds, setStreamingCitationIds] = useState<string[]>([]);
  const [streamingContradictionIds, setStreamingContradictionIds] = useState<string[]>([]);
  const [streamingEvents, setStreamingEvents] = useState<ReportSection["events"]>([]);
  const [done, setDone] = useState(false);
  const [useMock, setUseMock] = useState(false);

  const appendDelta = useCallback((delta: string) => {
    setStreamingContent((prev) => prev + delta);
  }, []);

  useEffect(() => {
    let es: EventSource | null = null;
    let mockTimeout: ReturnType<typeof setTimeout>[] = [];

    const runMockStream = () => {
      setUseMock(true);
      const mock = [...MOCK_REPORT_SECTIONS];
      mock.forEach((sec, i) => {
        mockTimeout.push(
          setTimeout(() => {
            setSections((prev) => [...prev, { ...sec, isStreaming: false }]);
          }, i * 400 + 200)
        );
      });
      mockTimeout.push(
        setTimeout(() => setDone(true), mock.length * 400 + 500)
      );
    };

    try {
      es = createEventSource(streamId);
      es.onmessage = (event) => {
        try {
          const data: StreamEventData = JSON.parse(event.data);
          switch (data.event) {
            case "section_start":
              setStreamingId(data.section_id ?? null);
              setStreamingContent("");
              setStreamingBlockType(data.block_type ?? "text");
              setStreamingHeadingLevel(data.heading_level);
              setStreamingCitationIds(data.citation_ids ?? []);
              setStreamingContradictionIds(data.contradiction_ids ?? []);
              setStreamingEvents(data.events ?? []);
              break;
            case "section_delta":
              if (data.delta) appendDelta(data.delta);
              break;
            case "section_complete": {
              const sid = data.section_id;
              if (sid) {
                setSections((prev) => [
                  ...prev,
                  {
                    section_id: sid,
                    block_type: data.block_type ?? "text",
                    heading_level: data.heading_level,
                    content: data.content ?? streamingContent,
                    citation_ids: data.citation_ids ?? [],
                    contradiction_ids: data.contradiction_ids ?? [],
                    events: data.events,
                  },
                ]);
              }
              setStreamingId(null);
              setStreamingContent("");
              break;
            }
            case "done":
              setDone(true);
              break;
            default:
              break;
          }
        } catch {
          // ignore parse errors
        }
      };
      es.onerror = () => {
        es?.close();
        runMockStream();
      };
    } catch {
      runMockStream();
    }

    return () => {
      es?.close();
      mockTimeout.forEach(clearTimeout);
    };
  }, [streamId, appendDelta, streamingBlockType, streamingHeadingLevel, streamingCitationIds, streamingContradictionIds, streamingEvents]);

  const streamingSection = streamingId
    ? {
        section_id: streamingId,
        block_type: streamingBlockType,
        heading_level: streamingHeadingLevel,
        content: streamingContent,
        citation_ids: streamingCitationIds,
        contradiction_ids: streamingContradictionIds,
        events: streamingEvents,
        isStreaming: true,
      }
    : null;

  return (
    <div className="max-w-[800px] mx-auto px-8 py-10">
      <AnimatePresence mode="popLayout">
        {sections.map((section) => (
          <ReportBlock
            key={section.section_id}
            section={section}
            citations={citations}
            contradictions={contradictions}
            onContradictionClick={onContradictionClick}
            onEditClick={onEditSection}
          />
        ))}
        {streamingSection && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mt-4"
          >
            {streamingSection.block_type === "heading" ? (
              <div
                className="font-display text-text-primary text-xl font-semibold"
                style={{
                  fontSize:
                    streamingSection.heading_level === 1
                      ? "1.5rem"
                      : streamingSection.heading_level === 2
                        ? "1.25rem"
                        : "1.125rem",
                }}
              >
                {streamingSection.content}
                <span className="inline-block w-2 h-4 ml-0.5 bg-gold-500/70 animate-pulse align-middle" />
              </div>
            ) : (
              <p className="text-sm text-text-secondary leading-relaxed">
                {streamingSection.content}
                <span className="inline-block w-2 h-4 ml-0.5 bg-gold-500/70 animate-pulse align-middle" />
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
      {done && sections.length === 0 && useMock && (
        <p className="text-text-muted text-sm">Loading report...</p>
      )}
    </div>
  );
}
