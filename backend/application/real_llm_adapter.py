import json
import os
import time
from typing import Any

import httpx

from domain.llm_schemas import LLMActionRecommendation, LLMDiagnosisOutput
from domain.models import ActionType, RecoveryCase, RootCauseCategory


# Inheriting from object, keeping it parallel to SimulatedLLMAdapter
class RealGeminiAdapter:
    """
    REAL LLM Provider.
    Calls Gemini API via requests.
    Validates evidence natively.
    """

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model_version = "gemini-2.5-flash"
        self.available = bool(self.api_key)
        self.latency_ms = 0
        self.tokens_used = 0
        # Key travels in a header, never the URL/query string (which lands in
        # access logs and proxy caches).
        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_version}:generateContent"
        )

    def _validate_evidence(self, case: RecoveryCase, output: Any) -> Any:
        valid_event_ids = {e.event_id for e in case.linked_events}
        if isinstance(output, LLMDiagnosisOutput):
            for ev in output.evidence_references:
                if ev not in valid_event_ids:
                    raise ValueError(f"Hallucinated evidence reference: {ev}")
        elif isinstance(output, LLMActionRecommendation):
            for ev in output.supporting_evidence:
                if ev not in valid_event_ids:
                    raise ValueError(f"Hallucinated evidence reference: {ev}")
        return output

    def _call_gemini(self, prompt: str, schema: dict) -> dict:
        if not self.available:
            raise Exception("REAL_LLM_UNAVAILABLE")

        start = time.time()
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
                "temperature": 0.0,
            },
        }

        try:
            resp = httpx.post(
                self.url,
                json=payload,
                timeout=10,
                headers={"x-goog-api-key": self.api_key},
            )
            resp.raise_for_status()
            self.latency_ms += int((time.time() - start) * 1000)

            data = resp.json()
            usage = data.get("usageMetadata", {})
            self.tokens_used += usage.get("totalTokenCount", 0)

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as e:
            self.latency_ms += int((time.time() - start) * 1000)
            raise e

    def diagnose(self, case: RecoveryCase) -> LLMDiagnosisOutput:
        prompt = f"""
        Analyze this RecoveryCase and diagnose the root cause.
        Case ID: {case.case_id}
        Risk Category: {case.risk_category.value}
        Events: {json.dumps([e.model_dump(mode="json") for e in case.linked_events])}
        
        Valid Root Cause Categories: {[c.value for c in RootCauseCategory]}
        Provide diagnosis_category, confidence, evidence_references (exact event_ids), and reasoning_summary.
        """

        # Pydantic's JSON schema carries $defs/$ref that Gemini rejects, so hand a
        # flat schema in Gemini's OBJECT/STRING dialect instead.
        gemini_schema = {
            "type": "OBJECT",
            "properties": {
                "diagnosis_category": {"type": "STRING"},
                "confidence": {"type": "NUMBER"},
                "evidence_references": {"type": "ARRAY", "items": {"type": "STRING"}},
                "reasoning_summary": {"type": "STRING"},
            },
            "required": [
                "diagnosis_category",
                "confidence",
                "evidence_references",
                "reasoning_summary",
            ],
        }

        raw_out = self._call_gemini(prompt, gemini_schema)
        out = LLMDiagnosisOutput(**raw_out)
        return self._validate_evidence(case, out)

    def recommend(self, case: RecoveryCase) -> LLMActionRecommendation:
        prompt = f"""
        Analyze this RecoveryCase and recommend recovery actions.
        Case ID: {case.case_id}
        Risk Category: {case.risk_category.value}
        Diagnosis: {case.diagnosis.cause_category.value if case.diagnosis else "UNKNOWN"}
        Events: {json.dumps([e.model_dump(mode="json") for e in case.linked_events])}
        
        Valid Action Types: {[a.value for a in ActionType]}
        Provide a list of candidates (action_type, rationale, estimated_probability 0.0-1.0) and supporting_evidence (exact event_ids).
        """

        gemini_schema = {
            "type": "OBJECT",
            "properties": {
                "candidates": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "action_type": {"type": "STRING"},
                            "rationale": {"type": "STRING"},
                            "estimated_probability": {"type": "NUMBER"},
                        },
                        "required": ["action_type", "rationale", "estimated_probability"],
                    },
                },
                "supporting_evidence": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["candidates", "supporting_evidence"],
        }

        raw_out = self._call_gemini(prompt, gemini_schema)
        out = LLMActionRecommendation(**raw_out)
        return self._validate_evidence(case, out)
