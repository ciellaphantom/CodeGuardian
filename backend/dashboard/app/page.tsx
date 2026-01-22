"use client";

import { useEffect, useMemo, useState } from "react";

type ScanRow = {
  id: number;
  scanned_at: string;
  total_issues: number;
  high: number;
  medium: number;
  low: number;
};

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

function fmtDate(s: string) {
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString();
}

export default function Home() {
  const [payload, setPayload] = useState<string>('{"password":"1234","eval":"1+1"}');

  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<any>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [scans, setScans] = useState<ScanRow[]>([]);
  const [listError, setListError] = useState<string | null>(null);

  const count = useMemo(() => scans.length, [scans]);

  async function loadScans() {
    setLoading(true);
    setListError(null);
    try {
      const r = await fetch(`${BACKEND}/scans`, { cache: "no-store" });
      const text = await r.text();
      if (!r.ok) throw new Error(text || `HTTP ${r.status}`);

      // backend örneğinde { value: [...] } geliyor
      const data = JSON.parse(text);
      const list: ScanRow[] = Array.isArray(data?.value)
        ? data.value
        : Array.isArray(data)
        ? data
        : [];

      setScans(list);
    } catch (e: any) {
      setListError(String(e?.message || e));
      setScans([]);
    } finally {
      setLoading(false);
    }
  }

  async function runScan() {
    setSubmitError(null);
    setSubmitResult(null);

    let body: any;
    try {
      body = JSON.parse(payload);
    } catch {
      setSubmitError('Geçersiz JSON. Örnek: {"password":"1234","eval":"1+1"}');
      return;
    }

    setSubmitting(true);
    try {
      const r = await fetch(`${BACKEND}/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const text = await r.text();
      if (!r.ok) throw new Error(text || `HTTP ${r.status}`);

      let out: any = text;
      try {
        out = JSON.parse(text);
      } catch {}

      setSubmitResult(out);
      await loadScans();
    } catch (e: any) {
      setSubmitError(String(e?.message || e));
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    loadScans();
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Arial" }}>
      <div style={{ maxWidth: 980, margin: "40px auto", padding: "0 16px" }}>
        <h1 style={{ fontSize: 28, marginBottom: 6 }}>CodeGuardian Dashboard</h1>
        <div style={{ color: "#444", marginBottom: 18, fontSize: 14 }}>
          Backend: <code>{BACKEND}</code>
        </div>

        {/* Scan */}
        <section style={{ border: "1px solid #ddd", borderRadius: 10, padding: 16, marginBottom: 24 }}>
          <h2 style={{ fontSize: 18, marginTop: 0 }}>Scan</h2>

          <div style={{ fontSize: 13, color: "#444", marginBottom: 8 }}>
            POST <code>{BACKEND}/scan</code>
          </div>

          <textarea
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
            rows={8}
            style={{
              width: "100%",
              padding: 12,
              borderRadius: 8,
              border: "1px solid #ccc",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: 13,
            }}
          />

          <div style={{ display: "flex", gap: 12, marginTop: 12, alignItems: "center" }}>
            <button
              onClick={runScan}
              disabled={submitting}
              style={{
                padding: "10px 14px",
                borderRadius: 8,
                border: "1px solid #111",
                background: submitting ? "#eee" : "#111",
                color: submitting ? "#333" : "#fff",
                cursor: submitting ? "not-allowed" : "pointer",
              }}
            >
              {submitting ? "Scanning..." : "Run Scan"}
            </button>

            <button
              onClick={loadScans}
              disabled={loading}
              style={{
                padding: "10px 14px",
                borderRadius: 8,
                border: "1px solid #ccc",
                background: "#fff",
                cursor: loading ? "not-allowed" : "pointer",
              }}
            >
              {loading ? "Refreshing..." : "Refresh Scans"}
            </button>

            {submitError && <span style={{ color: "#b00020" }}>{submitError}</span>}
          </div>

          {submitResult !== null && (
            <pre
              style={{
                marginTop: 14,
                padding: 12,
                background: "#f7f7f7",
                borderRadius: 8,
                border: "1px solid #e5e5e5",
                overflowX: "auto",
                fontSize: 13,
              }}
            >
              {typeof submitResult === "string" ? submitResult : JSON.stringify(submitResult, null, 2)}
            </pre>
          )}
        </section>

        {/* Scans */}
        <section style={{ border: "1px solid #ddd", borderRadius: 10, padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
            <h2 style={{ fontSize: 18, marginTop: 0 }}>Scans</h2>
            <div style={{ color: "#444", fontSize: 13 }}>Count: {count}</div>
          </div>

          {listError && (
            <div style={{ color: "#b00020", marginBottom: 10 }}>
              Liste alınamadı: {listError}
            </div>
          )}

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: "8px 6px" }}>ID</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: "8px 6px" }}>Scanned At</th>
                  <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: "8px 6px" }}>Total</th>
                  <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: "8px 6px" }}>High</th>
                  <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: "8px 6px" }}>Medium</th>
                  <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: "8px 6px" }}>Low</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={6} style={{ padding: 10, color: "#444" }}>Loading...</td>
                  </tr>
                ) : scans.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ padding: 10, color: "#444" }}>Kayıt yok.</td>
                  </tr>
                ) : (
                  scans.map((s) => (
                    <tr key={s.id}>
                      <td style={{ borderBottom: "1px solid #f0f0f0", padding: "8px 6px" }}>{s.id}</td>
                      <td style={{ borderBottom: "1px solid #f0f0f0", padding: "8px 6px" }}>{fmtDate(s.scanned_at)}</td>
                      <td style={{ borderBottom: "1px solid #f0f0f0", padding: "8px 6px", textAlign: "right" }}>{s.total_issues}</td>
                      <td style={{ borderBottom: "1px solid #f0f0f0", padding: "8px 6px", textAlign: "right" }}>{s.high}</td>
                      <td style={{ borderBottom: "1px solid #f0f0f0", padding: "8px 6px", textAlign: "right" }}>{s.medium}</td>
                      <td style={{ borderBottom: "1px solid #f0f0f0", padding: "8px 6px", textAlign: "right" }}>{s.low}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}
