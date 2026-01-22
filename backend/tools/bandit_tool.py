# backend/tools/bandit_tool.py

from __future__ import annotations

import json
import subprocess
import tempfile
from typing import Any, Dict, List


def run_bandit_on_code(code: str) -> List[Dict[str, Any]]:
    """
    Runs Bandit on the given Python code and returns the raw JSON 'results' list.
    If anything goes wrong, returns [] (no exception raised).
    """
    tmp_path = None

    try:
        # Kodun geçici dosyaya yazılması
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".py", mode="w", encoding="utf-8", newline="\n"
        ) as tmp:
            tmp.write(code or "")
            tmp_path = tmp.name

        # Bandit çalıştır
        # -f json: JSON output
        # -q: quiet
        # Bandit returncode: 0 (no issues), 1 (issues found), diğerleri hata
        result = subprocess.run(
            ["python", "-m", "bandit", "-f", "json", "-q", tmp_path],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode not in (0, 1):
            # Bandit CLI hata verdi
            err = (result.stderr or "").strip()
            if err:
                print("Bandit CLI error:", err)
            return []

        stdout = (result.stdout or "").strip()
        if not stdout:
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            print("Bandit JSON decode error:", repr(e))
            return []

        results = data.get("results", [])
        if isinstance(results, list):
            return results

        return []

    except Exception as e:
        print("Bandit exception:", repr(e))
        return []
