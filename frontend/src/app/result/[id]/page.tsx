import type { Metadata } from "next";
import Link from "next/link";
import { AlertTriangle, FileSearch, Zap, ArrowLeft } from "lucide-react";
import { MOCK_CASE } from "@/lib/mock-case";

interface Props {
  params: { id: string };
}

function getMockResult(id: string) {
  if (id === MOCK_CASE.id) return MOCK_CASE;
  return null;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const result = getMockResult(params.id);

  if (!result) {
    return { title: "Result not found — Clarion" };
  }

  const ogUrl = `/api/og?caseName=${encodeURIComponent(result.title)}&contradictions=${result.result.contradictionCount}&gaps=${result.result.gapCount}`;

  return {
    title: `${result.title} — Clarion Analysis`,
    description: `AI detected ${result.result.contradictionCount} contradictions and ${result.result.gapCount} evidence gap in this case. See the full analysis.`,
    openGraph: {
      title: `${result.title} — Clarion AI Found ${result.result.contradictionCount} Contradictions`,
      description: `AI detected ${result.result.contradictionCount} contradictions and ${result.result.gapCount} critical evidence gap in ${result.title} in ${(result.analysisTimeMs / 1000).toFixed(1)} seconds.`,
      images: [{ url: ogUrl, width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title: `${result.title} — Clarion AI Found ${result.result.contradictionCount} Contradictions`,
      images: [ogUrl],
    },
  };
}

export default function ResultPage({ params }: Props) {
  const result = getMockResult(params.id);

  if (!result) {
    return (
      <main className="min-h-screen bg-background flex items-center justify-center px-4">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-text-primary mb-2">Result not found</h1>
          <p className="text-text-secondary mb-6">This analysis result may have expired.</p>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 text-background font-medium text-sm hover:bg-amber-400 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
            Try the demo
          </Link>
        </div>
      </main>
    );
  }

  const { contradictions, missingInfo, title, result: res, analysisTimeMs } = result;

  return (
    <main className="min-h-screen bg-background py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Back link */}
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-amber-400 transition-colors mb-8"
          aria-label="Back to demo"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          Back to demo
        </Link>

        {/* Result card */}
        <div className="rounded-2xl border border-amber-500/30 bg-surface shadow-glass-amber overflow-hidden mb-6">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-background/40">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" aria-hidden="true" />
              <span className="text-xs font-bold text-amber-400 tracking-wider uppercase">
                Clarion AI · Shared Analysis
              </span>
            </div>
            <span className="text-xs text-text-muted font-mono">
              {(analysisTimeMs / 1000).toFixed(1)}s
            </span>
          </div>

          <div className="p-6">
            <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Case</p>
            <h1 className="text-xl font-bold text-text-primary mb-6">{title}</h1>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3 mb-6">
              <div className="flex flex-col items-center p-3 rounded-xl bg-danger-muted border border-danger/20 text-center">
                <AlertTriangle className="w-4 h-4 text-danger mb-1" aria-hidden="true" />
                <div className="text-3xl font-black text-danger">{res.contradictionCount}</div>
                <div className="text-[10px] text-danger/70">contradictions</div>
              </div>
              <div className="flex flex-col items-center p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-center">
                <FileSearch className="w-4 h-4 text-amber-400 mb-1" aria-hidden="true" />
                <div className="text-3xl font-black text-amber-400">{res.gapCount}</div>
                <div className="text-[10px] text-amber-400/70">evidence gaps</div>
              </div>
              <div className="flex flex-col items-center p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-center">
                <div className="text-3xl font-black text-indigo-400">{res.confidenceScore}%</div>
                <div className="text-[10px] text-indigo-400/70">AI confidence</div>
              </div>
            </div>

            {/* Contradictions */}
            <h2 className="text-sm font-semibold text-text-primary mb-3">
              Contradictions Found
            </h2>
            <div className="space-y-3 mb-6">
              {contradictions.map((c) => (
                <div
                  key={c.id}
                  className="rounded-xl border border-danger/20 bg-danger-muted p-4"
                >
                  <p className="text-xs font-bold text-danger mb-2 uppercase tracking-wide">
                    {c.label}
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <blockquote className="text-xs text-text-secondary border-l-2 border-indigo-500/50 pl-3">
                      &ldquo;{c.conflictingTextA}&rdquo;
                      <footer className="text-[10px] text-text-muted mt-1">
                        — {c.source_a.detail}
                      </footer>
                    </blockquote>
                    <blockquote className="text-xs text-text-secondary border-l-2 border-danger/50 pl-3">
                      &ldquo;{c.conflictingTextB}&rdquo;
                      <footer className="text-[10px] text-text-muted mt-1">
                        — {c.source_b.detail}
                      </footer>
                    </blockquote>
                  </div>
                </div>
              ))}
            </div>

            {/* Gaps */}
            <h2 className="text-sm font-semibold text-text-primary mb-3">
              Evidence Gaps
            </h2>
            <div className="space-y-3">
              {missingInfo.map((gap) => (
                <div
                  key={gap.id}
                  className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4"
                >
                  <p className="text-xs font-bold text-amber-400 mb-1 uppercase tracking-wide">
                    {gap.severity}
                  </p>
                  <p className="text-xs text-text-secondary">{gap.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="text-center">
          <p className="text-text-secondary text-sm mb-4">
            Want this for your cases?
          </p>
          <Link
            href="/#waitlist"
            className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-amber-500 text-background font-bold text-sm hover:bg-amber-400 active:scale-95 transition-all shadow-glow-amber min-h-[44px]"
          >
            Get Early Access
          </Link>
        </div>
      </div>
    </main>
  );
}
