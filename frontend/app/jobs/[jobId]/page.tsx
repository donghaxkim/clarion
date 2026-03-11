import { notFound } from "next/navigation";

import { JobReportExperienceBoundary } from "@/app/_components/report-experience";
import { ClarionApiError, getReportJob } from "@/lib/clarion-api";

interface JobPageProps {
  params: Promise<{
    jobId: string;
  }>;
}

export const runtime = "nodejs";

export default async function JobPage({ params }: JobPageProps) {
  const { jobId } = await params;
  let job;

  try {
    job = await getReportJob(jobId);
  } catch (error) {
    if (error instanceof ClarionApiError && error.status === 404) {
      notFound();
    }

    throw error;
  }

  return <JobReportExperienceBoundary initialJob={job} />;
}
