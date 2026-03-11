import { notFound } from "next/navigation";

import { StandaloneReportExperienceBoundary } from "@/app/_components/report-experience";
import { ClarionApiError, getReport } from "@/lib/clarion-api";

interface ReportPageProps {
  params: Promise<{
    reportId: string;
  }>;
}

export const runtime = "nodejs";

export default async function ReportPage({ params }: ReportPageProps) {
  const { reportId } = await params;
  let report;

  try {
    report = await getReport(reportId);
  } catch (error) {
    if (error instanceof ClarionApiError && error.status === 404) {
      notFound();
    }

    throw error;
  }

  return <StandaloneReportExperienceBoundary initialReport={report} />;
}
