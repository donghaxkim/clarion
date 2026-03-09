"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ChevronRight, CheckCircle, Loader2 } from "lucide-react";
import { EntityList } from "@/components/analysis/EntityList";
import { ContradictionCard } from "@/components/analysis/ContradictionCard";
import { MissingInfoCard } from "@/components/analysis/MissingInfoCard";
import { EntityPanel } from "@/components/entity/EntityPanel";
import { Button } from "@/components/ui/Button";
import { analyzeCase, generateReport } from "@/lib/api";
import type { AnalyzeResponse } from "@/lib/types";
import { MOCK_ANALYSIS } from "@/lib/mock-data";

export default function AnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const id = typeof params?.id === "string" ? params.id : "";
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [entityPanelName, setEntityPanelName] = useState<string | null>(null);

  const loadAnalysis = useCallback(async () => {
    setLoading(true);
    try {
      const res = await analyzeCase(id);
      setData(res);
    } catch {
      setData(MOCK_ANALYSIS);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) loadAnalysis();
  }, [id, loadAnalysis]);

  const handleGenerateReport = useCallback(async () => {
    setGenerating(true);
    try {
      const res = await generateReport(id);
      router.push(`/case/${id}/report?stream=${res.stream_url?.split("/").pop() ?? id}`);
    } catch {
      router.push(`/case/${id}/report?stream=${id}`);
    } finally {
      setGenerating(false);
    }
  }, [id, router]);

  const contradictions = data?.contradictions?.items ?? [];
  const missingInfo = data?.missing_info?.items ?? [];
  const entities = data?.entities ?? [];
  const severitySummary = data?.contradictions?.summary ?? "";
  const criticalCount = data?.missing_info?.critical ?? 0;
  const missingTotal = data?.missing_info?.total ?? 0;

  if (loading) {
    return (
      <main className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 text-gold-500 animate-spin" />
          <p className="text-sm text-text-muted">Analyzing evidence...</p>
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-text-muted">Unable to load analysis.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background flex flex-col">
      <header className="border-b border-border px-6 py-4">
        <h1 className="font-display text-xl text-text-primary">
          Intelligence Dashboard
        </h1>
        <p className="text-xs text-text-muted mt-0.5">
          {data.case_type_detected} · {data.total_facts_indexed} facts indexed
        </p>
      </header>

      <div className="flex-1 grid grid-cols-[25%_40%_35%] min-h-0 gap-0">
        {/* Column 1: Entities */}
        <div className="border-r border-border p-5 flex flex-col min-h-0">
          <EntityList
            entities={entities}
            onEntityClick={setEntityPanelName}
          />
        </div>

        {/* Column 2: Contradictions */}
        <div className="border-r border-border p-5 flex flex-col min-h-0 overflow-hidden">
          <div className="flex items-center justify-between gap-2 pb-3 border-b border-border">
            <h2 className="text-sm font-semibold text-text-primary">
              Contradictions Found
            </h2>
            {severitySummary ? (
              <span className="text-[10px] font-semibold text-text-muted uppercase">
                {severitySummary}
              </span>
            ) : null}
          </div>
          <div className="flex-1 overflow-y-auto space-y-3 pt-3">
            {contradictions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <CheckCircle className="w-10 h-10 text-success mb-3" />
                <p className="text-sm text-text-secondary">
                  No contradictions detected
                </p>
              </div>
            ) : (
              contradictions
                .sort((a, b) => {
                  const order = { high: 0, medium: 1, low: 2 };
                  return order[a.severity] - order[b.severity];
                })
                .map((c, i) => (
                  <ContradictionCard
                    key={c.id}
                    contradiction={c}
                    index={i}
                  />
                ))
            )}
          </div>
        </div>

        {/* Column 3: Missing Info */}
        <div className="p-5 flex flex-col min-h-0 overflow-hidden">
          <div className="flex items-center justify-between gap-2 pb-3 border-b border-border">
            <h2 className="text-sm font-semibold text-text-primary">
              Evidence Gaps
            </h2>
            <span className="px-2 py-0.5 rounded bg-surface-raised border border-border text-[10px] font-semibold text-text-muted tabular-nums">
              {missingTotal} · {criticalCount} critical
            </span>
          </div>
          <div className="flex-1 overflow-y-auto space-y-3 pt-3">
            {missingInfo.map((item, i) => (
              <MissingInfoCard key={item.id} item={item} index={i} />
            ))}
          </div>
        </div>
      </div>

      <div className="border-t border-border px-6 py-4 flex justify-end bg-surface/80">
        <Button
          variant="primary"
          size="lg"
          onClick={handleGenerateReport}
          isLoading={generating}
        >
          {generating ? "Generating..." : "Generate Report"}
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>

      {entityPanelName && (
        <EntityPanel
          caseId={id}
          entityName={entityPanelName}
          onClose={() => setEntityPanelName(null)}
        />
      )}
    </main>
  );
}
