"use client";

import Link from "next/link";

interface RouteErrorStateProps {
  title: string;
  message: string;
  reset: () => void;
}

export function RouteErrorState({
  title,
  message,
  reset,
}: RouteErrorStateProps) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-ink text-paper">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(214,125,68,0.24),_transparent_45%),linear-gradient(180deg,_rgba(8,7,6,0.98),_rgba(18,15,13,1))]" />
      <div className="grain-overlay absolute inset-0 opacity-45" aria-hidden="true" />
      <main className="relative mx-auto flex min-h-screen w-full max-w-3xl items-center px-4 py-12 md:px-6">
        <section className="w-full rounded-[2rem] border border-paper/10 bg-paper/8 p-8 shadow-[0_32px_120px_rgba(0,0,0,0.35)] backdrop-blur">
          <p className="font-mono text-xs uppercase tracking-[0.35em] text-amber">
            Clarion Recovery
          </p>
          <h1 className="mt-4 max-w-xl text-balance font-display text-4xl leading-tight text-paper md:text-5xl">
            {title}
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-paper/72 md:text-lg">
            {message}
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={reset}
              className="inline-flex items-center justify-center rounded-full border border-amber/40 bg-amber px-5 py-3 text-sm font-semibold text-ink transition-transform transition-colors duration-200 hover:-translate-y-0.5 hover:bg-amber-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
            >
              Try Again
            </button>
            <Link
              href="/"
              className="inline-flex items-center justify-center rounded-full border border-paper/20 px-5 py-3 text-sm font-semibold text-paper transition-transform transition-colors duration-200 hover:-translate-y-0.5 hover:border-paper/40 hover:bg-paper/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
            >
              Return Home
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
