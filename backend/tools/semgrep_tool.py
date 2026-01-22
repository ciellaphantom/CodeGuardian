from pathlib import Path
from typing import Any, Dict, List
import json
import subprocess
import tempfile

CONFIG_PATH = Path(__file__).with_name("semgrep_rules.yaml")


def run_semgrep_on_code(code: str) -> List[Dict[str, Any]]:
    """
    Runs Semgrep using our local semgrep_rules.yaml and returns findings
    normalized as:
    {tool, severity, policy, line, message, suggested_fix}
    """
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".py", mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                "semgrep",
                "--config",
                str(CONFIG_PATH),
                "--json",
                tmp_path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",     # <- EKLENDİ (Windows charmap hatası için)
            errors="ignore",      # <- EKLENDİ (bozuk byte'ları at)
            check=False,
        )

        if result.returncode not in (0, 1):
            print("Semgrep CLI error:", result.stderr)
            return []

        # stdout bazen boş/bozuk gelebilir; daha dayanıklı parse
        stdout = (result.stdout or "").strip()
        if not stdout:
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            # Nadiren encoding/semgrep output bozuk olursa backend patlamasın
            print("Semgrep JSON decode failed. Raw stdout head:", stdout[:200])
            return []

        findings: List[Dict[str, Any]] = []

        for r in data.get("results", []):
            extra = r.get("extra", {}) or {}
            severity = str(extra.get("severity", "LOW")).upper()

            # Semgrep ERROR -> MEDIUM map
            if severity == "ERROR":
                severity = "MEDIUM"

            check_id = (r.get("check_id") or "semgrep-rule")
            message = (extra.get("message") or "")

            # Boş/çöp kayıtları filtrele (istersen kaldırabilirsin)
            if not check_id and not message:
                continue

            findings.append(
                {
                    "tool": "semgrep",
                    "severity": severity,
                    "policy": check_id,
                    "line": (r.get("start") or {}).get("line", 0),
                    "message": message,
                    "suggested_fix": (extra.get("metadata") or {}).get(
                        "fix",
                        "Review this Semgrep finding and apply a secure fix.",
                    ),
                }
            )

        return findings

    except Exception as e:
        print("Semgrep exception:", e)
        return []


