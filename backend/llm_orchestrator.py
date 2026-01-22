# llm_orchestrator.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List


def build_llm_summary(code: str, findings: List[Dict[str, Any]]) -> str:
    """
    PDF / Tech stack uyumu:
    - LLM Orchestrator backend tarafında çalışır (FastAPI -> LLM -> summary).
    - OPENAI_API_KEY yoksa sistem LLM'siz çalışmaya devam eder (fallback).
    """

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "LLM summary disabled (OPENAI_API_KEY not set). Static analysis completed successfully."

    # OpenAI SDK import (PDF'ye uygun, ekstra yok)
    try:
        from openai import OpenAI
    except Exception as e:
        print("OPENAI_SDK_IMPORT_FAILED:", repr(e))
        return "LLM summary disabled (OpenAI SDK not available). Static analysis completed successfully."

    # Client init
    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        print("OPENAI_CLIENT_INIT_FAILED:", repr(e))
        return "LLM summary disabled (OpenAI client init failed). Static analysis completed successfully."

    # Findings JSON format
    try:
        findings_json = json.dumps(findings, ensure_ascii=False, indent=2)
    except Exception:
        findings_json = str(findings)

    prompt = (
        "You are CodeGuardian's LLM Orchestrator.\n"
        "Given the user's code and the static analysis findings (Bandit/Semgrep), produce:\n"
        "1) A concise executive summary (2-4 sentences)\n"
        "2) Severity breakdown (HIGH/MEDIUM/LOW counts)\n"
        "3) Remediation guidance grouped by severity\n"
        "4) Concrete safer alternatives (do NOT include insecure code)\n\n"
        "Return plain text with clear headings.\n\n"
        "CODE:\n"
        f"{code}\n\n"
        "FINDINGS (JSON):\n"
        f"{findings_json}\n"
    )

    # OpenAI request
    try:
        resp = client.responses.create(
            model="gpt-5-mini",
            input=prompt,
        )

        text = getattr(resp, "output_text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        output = getattr(resp, "output", None)
        if output:
            return str(output)

        return "LLM summary unavailable (empty response). Static analysis completed successfully."

    except Exception as e:
        print("OPENAI_CALL_FAILED:", repr(e))
        return "LLM summary disabled (OpenAI request failed). Static analysis completed successfully."


