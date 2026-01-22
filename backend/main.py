
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from llm_orchestrator import build_llm_summary
from tools.bandit_tool import run_bandit_on_code
from tools.semgrep_tool import run_semgrep_on_code


# =========================
# Policy Engine mappings
# =========================

POLICY_MAPPING: Dict[str, str] = {
    "B307": "OWASP A1: Injection (eval)",
    "B105": "CERT: Hard-coded secrets",
    "B404": "OWASP A6: Security Misconfiguration (subprocess module)",
    "B603": "CERT: Untrusted input to subprocess",
    "B607": "CERT: Partial executable path",
    "python-eval-detected": "OWASP A1: Injection (eval)",
}

SUGGESTED_FIXES: Dict[str, str] = {
    "B307": "Avoid eval(). Use ast.literal_eval or safer parsing with proper input validation.",
    "B105": "Remove hard-coded passwords. Use environment variables or a secrets manager.",
    "B404": "Avoid unsafe use of subprocess. Prefer higher-level library calls when possible.",
    "B603": "Do not pass untrusted input directly to subprocess. Use argument lists and strict validation.",
    "B607": "Use full, explicit paths for executables instead of partial or relative paths.",
}


# =========================
# FastAPI setup
# =========================

app = FastAPI()

# CORS: Browser'dan (localhost:3000) -> API (127.0.0.1:8000) fetch için şart.
# allow_credentials=True ile allow_origins="*" birlikte OLAMAZ.
ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Bazı ortamlarda preflight (OPTIONS) için explicit route gerekebiliyor.
@app.options("/{path:path}")
def preflight_handler(path: str):
    return {"ok": True}


# =========================
# Models
# =========================

class ScanSummary(BaseModel):
    id: int
    scanned_at: datetime
    total_issues: int
    high: int
    medium: int
    low: int


# =========================
# Health (debug)
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}


# =========================
# PostgreSQL connection
# =========================

conn = None  # global cache


def get_conn():
    """
    Returns a live PostgreSQL connection or None.
    """
    global conn

    if conn is not None and getattr(conn, "closed", 0) == 0:
        return conn

    try:
        password = os.getenv("CODEGUARDIAN_DB_PASSWORD")
        if not password:
            print("DB password env (CODEGUARDIAN_DB_PASSWORD) not set -> DB disabled")
            conn = None
            return None

        conn_local = psycopg2.connect(
            host="localhost",
            database="codeguardian",
            user="postgres",
            password=password,
        )
        conn_local.autocommit = True
        conn = conn_local
        print("DB OK")
    except Exception as e:
        print("DB connection failed:", e)
        conn = None

    return conn


# =========================
# Helpers
# =========================

def _extract_code_from_body(body: Dict[str, Any]) -> str:
    """
    Dashboard textarea JSON gönderiyor.
    Örnek: {"code":"..."} veya başka json.
    """
    if isinstance(body, dict) and "code" in body and isinstance(body["code"], str):
        return body["code"]
    return str(body)


# =========================
# /scan endpoint
# =========================

@app.post("/scan")
def scan_code(body: Dict[str, Any]):
    code_str = _extract_code_from_body(body)

    # 1) Statik analiz
    bandit_raw = run_bandit_on_code(code_str)
    semgrep_raw = run_semgrep_on_code(code_str)

    # 2) Bandit normalize
    bandit_findings: List[Dict[str, Any]] = []
    for issue in bandit_raw:
        test_id = issue.get("test_id", "UNKNOWN")

        mapped_policy = POLICY_MAPPING.get(test_id, test_id)
        suggested_fix = SUGGESTED_FIXES.get(
            test_id,
            "Review Bandit's documentation for this rule and apply a secure alternative.",
        )

        bandit_findings.append(
            {
                "tool": "bandit",
                "severity": issue.get("issue_severity", "LOW"),
                "policy": mapped_policy,
                "line": issue.get("line_number", 0),
                "message": issue.get("issue_text", ""),
                "suggested_fix": suggested_fix,
            }
        )

    # 3) Semgrep normalize
    # Not: semgrep_tool bazen RAW (check_id/extra/start) döndürür, bazen normalize edilmiş döndürüyor olabilir.
    # Bu blok her iki formatı da destekler ve boş kayıtları filtreler.
    semgrep_findings: List[Dict[str, Any]] = []

    for res in semgrep_raw:
        if not isinstance(res, dict):
            continue

        # CASE A: RAW Semgrep result
        if "check_id" in res or "extra" in res or "start" in res:
            extra = res.get("extra", {}) or {}
            metadata = extra.get("metadata", {}) or {}

            check_id = (res.get("check_id") or "").strip()
            message = (extra.get("message") or "").strip()

            if not check_id and not message:
                continue

            severity = str(extra.get("severity", "INFO")).upper()
            if severity == "ERROR":
                severity = "MEDIUM"

            semgrep_findings.append(
                {
                    "tool": "semgrep",
                    "severity": severity,
                    "policy": check_id,
                    "line": (res.get("start") or {}).get("line", 0),
                    "message": message,
                    "suggested_fix": (metadata.get("fix") or ""),
                }
            )

        # CASE B: Already-normalized Semgrep finding
        else:
            tool = (res.get("tool") or "").strip()
            if tool != "semgrep":
                continue

            policy = (res.get("policy") or "").strip()
            message = (res.get("message") or "").strip()

            if not policy and not message:
                continue

            severity = str(res.get("severity", "INFO")).upper()
            if severity == "ERROR":
                severity = "MEDIUM"

            semgrep_findings.append(
                {
                    "tool": "semgrep",
                    "severity": severity,
                    "policy": policy,
                    "line": int(res.get("line") or 0),
                    "message": message,
                    "suggested_fix": (res.get("suggested_fix") or ""),
                }
            )

    # 4) Findings birleştir
    findings: List[Dict[str, Any]] = bandit_findings + semgrep_findings

    # 5) DB'ye kaydet (varsa)
    scan_id: Optional[int] = None
    scanned_at: Optional[datetime] = None

    db = get_conn()
    if db is not None:
        try:
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO scans(code) VALUES (%s) RETURNING id, scanned_at",
                    (code_str,),
                )
                row = cur.fetchone()
                if row:
                    scan_id = row[0]
                    scanned_at = row[1]

                for f in findings:
                    cur.execute(
                        """
                        INSERT INTO findings
                            (scan_id, tool, severity, policy, line, message, suggested_fix)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            scan_id,
                            f["tool"],
                            f["severity"],
                            f["policy"],
                            f["line"],
                            f["message"],
                            f.get("suggested_fix", ""),
                        ),
                    )
        except Exception as e:
            print("DB insert failed:", e)

    # 6) LLM summary
    llm_summary = build_llm_summary(code_str, findings)

    return {
        "scan_id": scan_id,
        "scanned_at": scanned_at.isoformat() if scanned_at else None,
        "message": f"{len(findings)} issue(s) found.",
        "findings": findings,
        "llm_summary": llm_summary,
    }


# =========================
# /scans summary endpoint
# =========================

@app.get("/scans")
def list_scans():
    """
    Dashboard'un beklediği format:
    { "value": [ {id, scanned_at, total_issues, high, medium, low}, ... ] }
    """
    db = get_conn()
    if db is None:
        return {"value": []}

    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.id,
                    s.scanned_at,
                    COUNT(f.id) AS total_issues,
                    COALESCE(SUM(CASE WHEN f.severity = 'HIGH' THEN 1 ELSE 0 END), 0) AS high,
                    COALESCE(SUM(CASE WHEN f.severity = 'MEDIUM' THEN 1 ELSE 0 END), 0) AS medium,
                    COALESCE(SUM(CASE WHEN f.severity = 'LOW' THEN 1 ELSE 0 END), 0) AS low
                FROM scans s
                LEFT JOIN findings f ON f.scan_id = s.id
                GROUP BY s.id, s.scanned_at
                ORDER BY s.scanned_at DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall()

        value = []
        for r in rows:
            value.append(
                {
                    "id": r[0],
                    "scanned_at": r[1].isoformat() if r[1] else None,
                    "total_issues": int(r[2] or 0),
                    "high": int(r[3] or 0),
                    "medium": int(r[4] or 0),
                    "low": int(r[5] or 0),
                }
            )

        return {"value": value}

    except Exception as e:
        print("DB query failed:", e)
        raise HTTPException(status_code=500, detail="Failed to load scan summary")
