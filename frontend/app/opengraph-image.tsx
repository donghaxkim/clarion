import { ImageResponse } from "next/og";

export const runtime = "nodejs";
export const alt = "Clarion cinematic report viewer";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          padding: "56px",
          background:
            "linear-gradient(135deg, rgba(13,11,9,1) 0%, rgba(24,19,15,1) 100%)",
          color: "#f4ece0",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(circle at top right, rgba(214,125,68,0.38), transparent 34%)",
          }}
        />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            width: "100%",
            border: "1px solid rgba(244,236,224,0.12)",
            borderRadius: "32px",
            padding: "44px",
            background: "rgba(244,236,224,0.04)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span
              style={{
                fontSize: 20,
                letterSpacing: "0.35em",
                textTransform: "uppercase",
                color: "#e7c184",
              }}
            >
              Clarion
            </span>
            <span
              style={{
                fontSize: 20,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "rgba(244,236,224,0.64)",
              }}
            >
              Cinematic Report Viewer
            </span>
          </div>
          <div style={{ display: "flex", gap: 32 }}>
            <div style={{ width: "34%", display: "flex", flexDirection: "column", gap: 16 }}>
              {["Text", "Image", "Video", "Citations"].map((item, index) => (
                <div
                  key={item}
                  style={{
                    borderRadius: 24,
                    padding: "18px 22px",
                    background:
                      index === 2 ? "rgba(214,125,68,0.18)" : "rgba(244,236,224,0.06)",
                    border: "1px solid rgba(244,236,224,0.1)",
                    fontSize: 26,
                  }}
                >
                  {item}
                </div>
              ))}
            </div>
            <div style={{ width: "66%", display: "flex", flexDirection: "column", gap: 20 }}>
              <div
                style={{
                  fontSize: 78,
                  lineHeight: 1,
                  maxWidth: 620,
                }}
              >
                Evidence staged like a directed sequence.
              </div>
              <div
                style={{
                  fontSize: 28,
                  lineHeight: 1.4,
                  color: "rgba(244,236,224,0.72)",
                  maxWidth: 680,
                }}
              >
                Live chronology planning, text and media blocks, and
                section-scoped citations in a single courtroom-ready canvas.
              </div>
            </div>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
