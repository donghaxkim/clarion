export function ReportLoadingShell() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-ink text-paper">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(214,125,68,0.2),_transparent_45%),linear-gradient(180deg,_rgba(8,7,6,0.98),_rgba(18,15,13,1))]" />
      <div className="grain-overlay absolute inset-0 opacity-40" aria-hidden="true" />
      <main className="relative mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-6 px-4 py-6 md:px-6 xl:flex-row xl:gap-8 xl:px-10 xl:py-10">
        <aside className="hidden w-72 shrink-0 rounded-[2rem] border border-paper/10 bg-paper/5 p-6 xl:block">
          <div className="h-4 w-28 rounded-full bg-paper/10" />
          <div className="mt-6 space-y-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="h-11 rounded-2xl bg-paper/10"
              />
            ))}
          </div>
        </aside>
        <section className="min-w-0 flex-1 space-y-6">
          <div className="rounded-[2rem] border border-paper/10 bg-paper/6 p-6 backdrop-blur">
            <div className="h-4 w-36 rounded-full bg-paper/10" />
            <div className="mt-4 h-12 max-w-2xl rounded-[1.5rem] bg-paper/10" />
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={index}
                  className="h-24 rounded-[1.5rem] bg-paper/10"
                />
              ))}
            </div>
          </div>
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="rounded-[2rem] border border-paper/10 bg-paper/6 p-6"
            >
              <div className="h-3 w-24 rounded-full bg-paper/10" />
              <div className="mt-4 h-8 max-w-xl rounded-full bg-paper/10" />
              <div className="mt-4 space-y-3">
                <div className="h-3 rounded-full bg-paper/10" />
                <div className="h-3 rounded-full bg-paper/10" />
                <div className="h-3 w-3/4 rounded-full bg-paper/10" />
              </div>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
