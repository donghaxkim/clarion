import Link from "next/link";

export default function NotFound() {
  return (
    <main
      id="main-content"
      className="relative min-h-screen overflow-hidden bg-ink text-paper"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(214,125,68,0.18),_transparent_45%),linear-gradient(180deg,_rgba(8,7,6,0.98),_rgba(18,15,13,1))]" />
      <div className="grain-overlay absolute inset-0 opacity-45" aria-hidden="true" />
      <section className="relative mx-auto flex min-h-screen max-w-3xl items-center px-4 py-12 md:px-6">
        <div className="rounded-[2rem] border border-paper/10 bg-paper/6 p-8 shadow-[0_32px_120px_rgba(0,0,0,0.3)] backdrop-blur">
          <p className="font-mono text-xs uppercase tracking-[0.35em] text-amber">
            Not Found
          </p>
          <h1 className="mt-4 font-display text-5xl leading-tight text-paper">
            Clarion could not find that report route.
          </h1>
          <p className="mt-4 text-base leading-7 text-paper/72">
            The requested job or report does not exist in the current backend
            store, or the identifier was mistyped.
          </p>
          <Link
            href="/"
            className="mt-8 inline-flex rounded-full border border-amber/30 bg-amber px-5 py-3 text-sm font-semibold text-ink transition-transform transition-colors duration-200 hover:-translate-y-0.5 hover:bg-amber-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-paper focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
          >
            Return Home
          </Link>
        </div>
      </section>
    </main>
  );
}
