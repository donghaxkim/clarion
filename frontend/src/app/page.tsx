"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, Loader2 } from "lucide-react";
import { ChatInterface } from "@/components/chat/ChatInterface";
import type { Message } from "@/components/chat/ChatMessage";
import { DropZone } from "@/components/upload/DropZone";
import { ParsedEvidenceCard } from "@/components/upload/ParsedEvidenceCard";
import { Button } from "@/components/ui/Button";
import { createCase, uploadEvidence, analyzeCase } from "@/lib/api";
import type { ParsedEvidence } from "@/lib/types";
import { MOCK_PARSED_FILES } from "@/lib/mock-data";
import { cn } from "@/lib/utils";
import type { CaseTypeOption } from "@/components/chat/ChatInterface";

const ASSISTANT_REPLY = "Got it. Upload your evidence to get started.";

const CASE_TYPE_OPTIONS: CaseTypeOption[] = [
  {
    label: "Personal injury",
    description:
      "Personal injury case. Focus on liability, negligence, damages, and medical or accident evidence. Typical evidence: medical records, accident reports, witness statements, photos, insurance documents.",
  },
  {
    label: "Contract dispute",
    description:
      "Contract or commercial dispute. Focus on terms, breach, performance, and damages. Typical evidence: contracts, correspondence, invoices, meeting notes, expert reports.",
  },
  {
    label: "Employment law",
    description:
      "Employment matter. Focus on wrongful termination, discrimination, wages, or workplace issues. Typical evidence: HR records, policies, emails, performance reviews, pay stubs.",
  },
  {
    label: "Property & real estate",
    description:
      "Property or real estate dispute. Focus on ownership, leases, zoning, or transaction issues. Typical evidence: deeds, leases, surveys, correspondence, inspection reports.",
  },
  {
    label: "Criminal defense",
    description:
      "Criminal defense case. Focus on charges, evidence, procedure, and rights. Typical evidence: police reports, discovery, witness statements, forensic or expert reports.",
  },
  {
    label: "Family law",
    description:
      "Family law matter. Focus on divorce, custody, support, or related agreements. Typical evidence: financial disclosures, custody agreements, communications, expert evaluations.",
  },
];

export default function IntakePage() {
  const router = useRouter();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [parsedEvidence, setParsedEvidence] = useState<ParsedEvidence[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [useMock, setUseMock] = useState(false);
  const [selectedCaseType, setSelectedCaseType] = useState<string | null>(null);

  const hasParsedEvidence = parsedEvidence.length > 0;
  const anyParsed = parsedEvidence.some((e) => e.status === "parsed");

  const handleSendMessage = useCallback(
    async (text: string) => {
      setInputValue("");
      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: text,
      };
      setMessages((prev) => [...prev, userMsg]);

      let currentCaseId = caseId;
      if (!currentCaseId) {
        try {
          const res = await createCase({ description: text });
          currentCaseId = res.case_id;
          setCaseId(res.case_id);
        } catch {
          setUseMock(true);
          currentCaseId = "demo";
          setCaseId("demo");
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          role: "assistant",
          content: "",
          isTyping: true,
        },
      ]);

      setTimeout(() => {
        setMessages((prev) =>
          prev.map((m) =>
            m.isTyping
              ? { ...m, content: ASSISTANT_REPLY, isTyping: false }
              : m
          )
        );
      }, 600);
    },
    [caseId]
  );

  const handleSelectCaseType = useCallback(
    (option: CaseTypeOption) => {
      setSelectedCaseType(option.label);
      if (!caseId) {
        createCase({ description: option.description })
          .then((res) => setCaseId(res.case_id))
          .catch(() => {
            setUseMock(true);
            setCaseId("demo");
          });
      }
    },
    [caseId]
  );

  const handleFiles = useCallback(
    async (files: File[]) => {
      const id = caseId ?? "demo";
      if (!caseId) setCaseId("demo");
      setIsUploading(true);
      try {
        const res = await uploadEvidence(id, files);
        setCaseId(res.case_id);
        setParsedEvidence((prev) => {
          const byId = new Map(prev.map((e) => [e.evidence_id, e]));
          res.parsed.forEach((e) => byId.set(e.evidence_id, e));
          return Array.from(byId.values());
        });
      } catch {
        setUseMock(true);
        setParsedEvidence((prev) => [
          ...prev,
          ...MOCK_PARSED_FILES.slice(0, Math.min(files.length, 4)).map(
            (e, i) => ({
              ...e,
              evidence_id: `mock-${Date.now()}-${i}`,
              filename: files[i]?.name ?? e.filename,
            })
          ),
        ]);
      } finally {
        setIsUploading(false);
      }
    },
    [caseId]
  );

  const handleAnalyze = useCallback(async () => {
    const id = caseId ?? "demo";
    setIsAnalyzing(true);
    try {
      await analyzeCase(id);
      router.push(`/case/${id}/analysis`);
    } catch {
      setUseMock(true);
      router.push("/case/demo/analysis");
    } finally {
      setIsAnalyzing(false);
    }
  }, [caseId, router]);

  return (
    <main className="h-full flex flex-col min-h-0 bg-background">
      <div className="flex-1 grid grid-cols-[1fr_minmax(280px,38%)] min-h-0 gap-0">
        {/* Left: Chat */}
        <div className="border-r border-border flex flex-col min-h-0 overflow-hidden">
          <ChatInterface
            messages={messages}
            onSend={handleSendMessage}
            inputValue={inputValue}
            onInputChange={setInputValue}
            caseTypeOptions={CASE_TYPE_OPTIONS}
            selectedCaseType={selectedCaseType}
            onSelectCaseType={handleSelectCaseType}
          />
        </div>

        {/* Right: Upload + evidence cards */}
        <div className="flex flex-col min-h-0 bg-surface/50 overflow-hidden">
          <div className="shrink-0 px-3 py-2 border-b border-border flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
            <span className="text-[11px] font-semibold text-text-secondary tracking-wider uppercase">
              Evidence
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
            <DropZone onFiles={handleFiles} isDisabled={isUploading} />
            {isUploading && (
              <div className="flex items-center gap-2 text-text-muted text-xs">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Parsing files...
              </div>
            )}
            <AnimatePresence mode="popLayout">
              {parsedEvidence.map((evidence, index) => (
                <ParsedEvidenceCard
                  key={evidence.evidence_id}
                  evidence={evidence}
                  index={index}
                />
              ))}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="shrink-0 border-t border-border px-4 py-2.5 flex items-center justify-between bg-surface/80">
        <p className="text-[11px] text-text-muted">
          {hasParsedEvidence
            ? `${parsedEvidence.length} file(s) · ${parsedEvidence.filter((e) => e.status === "parsed").length} parsed`
            : "Upload at least one file to generate report"}
        </p>
        <Button
          variant="primary"
          size="md"
          disabled={!anyParsed || isAnalyzing}
          onClick={handleAnalyze}
          isLoading={isAnalyzing}
          className={cn(
            anyParsed &&
              "shadow-glow-gold animate-pulse-amber"
          )}
        >
          {isAnalyzing ? (
            "Generating..."
          ) : (
            <>
              Generate Report
              <ChevronRight className="w-4 h-4" />
            </>
          )}
        </Button>
      </div>
    </main>
  );
}
