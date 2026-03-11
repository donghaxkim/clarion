import { LaunchDemoButton } from "@/app/_components/launch-demo-button";

const evidenceChips = [
  "Dashcam Sequence",
  "Witness Transcript",
  "Scene Photography",
  "Police Record",
  "Public Context Notes",
];

const featureCards = [
  {
    title: "Live Chronology",
    body: "Watch the report lock into place as timeline, narrative, image, and reconstruction blocks arrive.",
  },
  {
    title: "Margin Citations",
    body: "Select a scene and its source trail opens beside the active passage instead of dropping below it.",
  },
  {
    title: "Continuous Reading",
    body: "The report reads like a clean case memo, with media embedded inline instead of boxed-up cards.",
  },
];

export default function HomePage() {
  return (
    <main
      id="main-content"
      className="relative min-h-screen overflow-hidden bg-ink text-paper"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(214,125,68,0.2),_transparent_36%),radial-gradient(circle_at_bottom_left,_rgba(181,76,36,0.18),_transparent_30%),linear-gradient(180deg,_rgba(8,7,6,0.98),_rgba(18,15,13,1))]" />
      <div className="grain-overlay absolute inset-0 opacity-45" aria-hidden="true" />

      <section className="relative mx-auto flex min-h-screen w-full max-w-[1600px] flex-col justify-between gap-12 px-4 py-10 md:px-6 xl:flex-row xl:gap-16 xl:px-10 xl:py-14">
        <div className="max-w-2xl xl:py-12">
          <p className="font-mono text-xs uppercase tracking-[0.35em] text-amber">
            Clarion / Creative Director Track
          </p>
          <h1 className="mt-6 max-w-4xl text-balance font-display text-5xl leading-[0.95] text-paper md:text-7xl xl:text-[5.5rem]">
            A report viewer that stages evidence like a directed sequence.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-paper/74">
            Clarion turns a generated legal report into a cinematic narrative
            canvas: text, images, reconstruction video, and margin citations
            woven into a single live stream.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            {evidenceChips.map((chip) => (
              <span
                key={chip}
                className="rounded-full border border-paper/14 bg-paper/8 px-4 py-2 text-sm text-paper/72"
              >
                {chip}
              </span>
            ))}
          </div>

          <div className="mt-10">
            <LaunchDemoButton />
          </div>

          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {featureCards.map((card) => (
              <article
                key={card.title}
                className="rounded-[1.75rem] border border-paper/10 bg-paper/6 p-5 backdrop-blur"
              >
                <h2 className="text-2xl font-display text-paper">
                  {card.title}
                </h2>
                <p className="mt-3 text-sm leading-6 text-paper/68">
                  {card.body}
                </p>
              </article>
            ))}
          </div>
        </div>

        <div className="relative flex flex-1 items-center xl:justify-end">
          <div className="absolute left-1/2 top-1/2 h-[28rem] w-[28rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-amber/18 blur-3xl" />
          <div className="relative w-full max-w-[48rem] overflow-hidden rounded-[2.5rem] border border-paper/12 bg-paper/7 p-5 shadow-[0_32px_140px_rgba(0,0,0,0.36)] backdrop-blur md:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-paper/10 pb-4">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.35em] text-amber">
                  Demo Report Stage
                </p>
                <h2 className="mt-2 text-balance font-display text-3xl text-paper md:text-4xl">
                  Nighttime Intersection Reconstruction
                </h2>
              </div>
              <div className="rounded-full border border-amber/25 bg-amber/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-amber-soft">
                Live Preview
              </div>
            </div>

            <div className="mt-6 grid gap-5 xl:grid-cols-[1.05fr_1.4fr]">
              <aside className="rounded-[2rem] border border-paper/10 bg-ink-soft p-4">
                <p className="font-mono text-xs uppercase tracking-[0.28em] text-paper/48">
                  Chronology Rail
                </p>
                <ol className="mt-4 space-y-3">
                  {[
                    "Vehicles approach under active signals",
                    "Pickup commits to the turn",
                    "Impact & rest positions",
                    "Scene illustration",
                    "Reconstruction clip",
                  ].map((item, index) => (
                    <li
                      key={item}
                      className={`rounded-[1.5rem] border px-4 py-3 ${
                        index === 2
                          ? "border-amber/30 bg-amber/10"
                          : "border-paper/10 bg-paper/6"
                      }`}
                    >
                      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-paper/48">
                        Scene {(index + 1).toString().padStart(2, "0")}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-paper/82">
                        {item}
                      </p>
                    </li>
                  ))}
                </ol>
              </aside>

              <div className="space-y-5">
                <section className="overflow-hidden rounded-[2rem] border border-paper/10 bg-[linear-gradient(135deg,_rgba(214,125,68,0.16),_rgba(17,14,11,0.96))] p-5">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-mono text-xs uppercase tracking-[0.28em] text-paper/48">
                        Media Stage
                      </p>
                      <h3 className="mt-3 font-display text-3xl text-paper">
                        Reconstruction clip arrives after the narrative anchor.
                      </h3>
                    </div>
                    <span className="rounded-full border border-paper/12 bg-paper/8 px-3 py-1 text-xs uppercase tracking-[0.18em] text-paper/62">
                      {`Rendering${"\u2026"}`}
                    </span>
                  </div>
                  <div className="mt-5 grid gap-3 sm:grid-cols-3">
                    {Array.from({ length: 3 }).map((_, index) => (
                      <div
                        key={index}
                        className="aspect-[4/3] rounded-[1.4rem] border border-paper/10 bg-paper/7"
                      />
                    ))}
                  </div>
                </section>

                <section className="rounded-[2rem] border border-paper/10 bg-[#f6efe6] p-5 text-[#1b1510]">
                  <p className="font-mono text-xs uppercase tracking-[0.28em] text-[#9a5a34]">
                    Continuous Document
                  </p>
                  <div className="mt-5 space-y-5">
                    <article className="pb-5">
                      <h3 className="font-display text-3xl text-[#1b1510]">
                        Vehicles approach under active signals.
                      </h3>
                      <p className="mt-3 text-sm leading-7 text-[#5f5144]">
                        Traffic remains orderly until the pickup enters the
                        turn lane and commits across the sedan&apos;s path.
                      </p>
                    </article>
                    <article className="border-t border-[#ddcdbd] pt-5">
                      <div className="grid gap-4 xl:grid-cols-[1fr_14rem] xl:items-start">
                        <div>
                          <h3 className="font-display text-3xl text-[#1b1510]">
                            {"\u201cPickup Commits to the Turn\u201d"}
                          </h3>
                          <p className="mt-3 text-sm leading-7 text-[#5f5144]">
                            The active scene keeps its place in the narrative
                            while the source trail opens directly in the
                            document margin.
                          </p>
                        </div>
                        <aside className="rounded-[1.4rem] border border-[#ddcdbd] bg-white/72 p-4">
                          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#9a5a34]">
                            Citations
                          </p>
                          <p className="mt-3 text-sm leading-6 text-[#5f5144]">
                            Dashcam D2, witness transcript, and signal timing
                            notes stay pinned to the selected block.
                          </p>
                        </aside>
                      </div>
                    </article>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
