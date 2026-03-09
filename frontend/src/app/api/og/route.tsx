import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

export const runtime = "edge";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const caseName = searchParams.get("caseName") ?? "Johnson v. Metro Transit";
  const contradictions = searchParams.get("contradictions") ?? "2";
  const gaps = searchParams.get("gaps") ?? "1";

  return new ImageResponse(
    (
      <div
        style={{
          background: "#0A0A0F",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          padding: "60px",
          position: "relative",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {/* Background gradient blobs */}
        <div
          style={{
            position: "absolute",
            top: "-100px",
            left: "-100px",
            width: "600px",
            height: "400px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(245,158,11,0.08) 0%, transparent 70%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: "-80px",
            right: "-80px",
            width: "500px",
            height: "350px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(99,102,241,0.07) 0%, transparent 70%)",
          }}
        />

        {/* Logo / brand */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginBottom: "auto",
          }}
        >
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "8px",
              background: "#F59E0B",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span style={{ color: "#0A0A0F", fontWeight: "900", fontSize: "18px" }}>C</span>
          </div>
          <span style={{ color: "#F8F8FC", fontWeight: "700", fontSize: "20px", letterSpacing: "-0.02em" }}>
            Clarion
          </span>
          <span
            style={{
              marginLeft: "8px",
              padding: "2px 10px",
              borderRadius: "20px",
              background: "rgba(245,158,11,0.12)",
              border: "1px solid rgba(245,158,11,0.25)",
              color: "#F59E0B",
              fontSize: "11px",
              fontWeight: "600",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            AI Litigation
          </span>
        </div>

        {/* Main content */}
        <div style={{ display: "flex", flexDirection: "column", marginTop: "60px" }}>
          <p
            style={{
              color: "#60607A",
              fontSize: "14px",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginBottom: "8px",
            }}
          >
            Case Analysis
          </p>
          <h1
            style={{
              color: "#F8F8FC",
              fontSize: "40px",
              fontWeight: "800",
              letterSpacing: "-0.025em",
              lineHeight: "1.15",
              marginBottom: "48px",
              maxWidth: "800px",
            }}
          >
            {caseName}
          </h1>

          {/* Stats row */}
          <div style={{ display: "flex", gap: "16px" }}>
            {/* Contradictions */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                padding: "20px 32px",
                borderRadius: "16px",
                background: "rgba(239,68,68,0.12)",
                border: "1px solid rgba(239,68,68,0.2)",
                minWidth: "160px",
              }}
            >
              <span style={{ color: "#EF4444", fontSize: "56px", fontWeight: "900", lineHeight: "1" }}>
                {contradictions}
              </span>
              <span style={{ color: "rgba(239,68,68,0.7)", fontSize: "13px", marginTop: "6px" }}>
                contradictions
              </span>
            </div>

            {/* Gaps */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                padding: "20px 32px",
                borderRadius: "16px",
                background: "rgba(245,158,11,0.1)",
                border: "1px solid rgba(245,158,11,0.2)",
                minWidth: "160px",
              }}
            >
              <span style={{ color: "#F59E0B", fontSize: "56px", fontWeight: "900", lineHeight: "1" }}>
                {gaps}
              </span>
              <span style={{ color: "rgba(245,158,11,0.7)", fontSize: "13px", marginTop: "6px" }}>
                evidence gaps
              </span>
            </div>

            {/* Impact */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "20px 32px",
                borderRadius: "16px",
                background: "rgba(239,68,68,0.08)",
                border: "1px solid rgba(239,68,68,0.15)",
                minWidth: "160px",
              }}
            >
              <span style={{ color: "#EF4444", fontSize: "28px", fontWeight: "900", letterSpacing: "0.06em" }}>
                HIGH
              </span>
              <span style={{ color: "rgba(239,68,68,0.6)", fontSize: "13px", marginTop: "6px" }}>
                outcome risk
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: "auto",
            paddingTop: "32px",
            borderTop: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <span style={{ color: "#60607A", fontSize: "13px" }}>
            Analyzed by Clarion AI in seconds
          </span>
          <span style={{ color: "#3A3A50", fontSize: "13px" }}>clarion.ai</span>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
    }
  );
}
