"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { FileText, Users, AlertTriangle } from "lucide-react";
import { ReportViewer } from "@/components/report/ReportViewer";
import { SideEditor } from "@/components/report/SideEditor";
import { EntityPanel } from "@/components/entity/EntityPanel";
import { Button } from "@/components/ui/Button";
import { getCase, getEntity } from "@/lib/api";
import type { Citation, ContradictionItem, EntityItem } from "@/lib/types";
import {
  MOCK_CITATIONS,
  MOCK_ANALYSIS,
  MOCK_PARSED_FILES,
} from "@/lib/mock-data";
import { cn } from "@/lib/utils";

type TabId = "evidence" | "entities" | "issues";

export default function ReportPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const caseId = typeof params?.id === "string" ? params.id : "";
  const streamId = searchParams?.get("stream") ?? caseId;

  const [citations, setCitations] = useState<Record<string, Citation>>(MOCK_CITATIONS);
  const [contradictions, setContradictions] = useState<ContradictionItem[]>(
    MOCK_ANALYSIS.contradictions.items
  );
  const [entities, setEntities] = useState<EntityItem[]>(MOCK_ANALYSIS.entities);
  const [evidence, setEvidence] = useState(MOCK_PARSED_FILES);
  const [tab, setTab] = useState<TabId>("evidence");
  const [editorSectionId, setEditorSectionId] = useState<string | null>(null);
  const [entityPanelName, setEntityPanelName] = useState<string | null>(null);

  useEffect(() => {
    getCase(caseId)
      .then((data: Record<string, unknown>) => {
        if (data.citations && typeof data.citations === "object") {
          setCitations(data.citations as Record<string, Citation>);
        }
        if (Array.isArray(data.contradictions)) {
          setContradictions(data.contradictions as ContradictionItem[]);
        }
        if (Array.isArray(data.entities)) {
          setEntities(data.entities as EntityItem[]);
        }
        if (Array.isArray(data.parsed)) {
          setEvidence(data.parsed as typeof evidence);
        }
      })
      .catch(() => {
        // keep mock data
      });
  }, [caseId]);

  const openEditor = useCallback((sectionId: string) => {
    setEditorSectionId(sectionId);
  }, []);

  const closeEditor = useCallback(() => {
    setEditorSectionId(null);
  }, []);

  const openEntity = useCallback((name: string) => {
    setEntityPanelName(name);
  }, []);

  const closeEntity = useCallback(() => {
    setEntityPanelName(null);
  }, []);

  const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
    { id: "evidence", label: "Evidence", icon: FileText },
    { id: "entities", label: "Entities", icon: Users },
    { id: "issues", label: "Issues", icon: AlertTriangle },
  ];

  return (
    <main className="min-h-screen bg-background flex">
      {/* Center: Report */}
      <div className="flex-1 min-w-0">
        <ReportViewer
          streamId={streamId}
          caseId={caseId}
          citations={citations}
          contradictions={contradictions}
          onEditSection={openEditor}
          onContradictionClick={(id) => {
            // could scroll to or expand contradiction
          }}
        />
      </div>

      {/* Right sidebar: Context */}
      <aside className="w-[30%] min-w-[260px] max-w-[360px] border-l border-border flex flex-col bg-surface/50">
        <div className="flex border-b border-border">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 py-3 text-[11px] font-semibold uppercase tracking-wider transition-colors",
                tab === id
                  ? "text-gold-400 border-b-2 border-gold-500 bg-surface-raised/50"
                  : "text-text-muted hover:text-text-secondary"
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {tab === "evidence" && (
            <ul className="space-y-2">
              {evidence.map((e) => (
                <li
                  key={e.evidence_id}
                  className="text-xs text-text-secondary truncate px-2 py-1.5 rounded bg-surface border border-border"
                >
                  {e.filename}
                </li>
              ))}
            </ul>
          )}
          {tab === "entities" && (
            <ul className="space-y-1">
              {entities.map((e) => (
                <li key={e.name}>
                  <button
                    type="button"
                    onClick={() => openEntity(e.name)}
                    className="w-full text-left text-xs text-text-secondary hover:text-gold-400 px-2 py-1.5 rounded hover:bg-surface-raised transition-colors"
                  >
                    {e.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {tab === "issues" && (
            <div className="space-y-3">
              <div>
                <p className="text-[10px] font-semibold text-text-muted uppercase mb-2">
                  Contradictions
                </p>
                <ul className="space-y-1.5">
                  {contradictions.slice(0, 5).map((c) => (
                    <li
                      key={c.id}
                      className="text-[11px] text-text-secondary line-clamp-2 px-2 py-1.5 rounded border border-border"
                    >
                      {c.description}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-text-muted uppercase mb-2">
                  Missing info
                </p>
                <ul className="space-y-1.5">
                  {MOCK_ANALYSIS.missing_info.items.slice(0, 3).map((m) => (
                    <li
                      key={m.id}
                      className="text-[11px] text-text-muted line-clamp-2 px-2 py-1.5 rounded border border-border"
                    >
                      {m.description}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Overlays */}
      <AnimatePresence>
        {editorSectionId && (
          <SideEditor
            key={editorSectionId}
            caseId={caseId}
            sectionId={editorSectionId}
            onClose={closeEditor}
            onSaved={() => {
              closeEditor();
            }}
          />
        )}
        {entityPanelName && (
          <EntityPanel
            key={entityPanelName}
            caseId={caseId}
            entityName={entityPanelName}
            onClose={closeEntity}
          />
        )}
      </AnimatePresence>
    </main>
  );
}
