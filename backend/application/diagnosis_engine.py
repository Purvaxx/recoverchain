import uuid
from datetime import UTC, datetime
from typing import Any

from domain.models import (
    DiagnosisStatus,
    RecoveryCase,
    RiskCategory,
    RootCauseCategory,
    RootCauseDiagnosis,
)


class EvidenceBuilder:
    """Extracts structured evidence from the Case and its RevenueEvents."""

    @staticmethod
    def extract_evidence(case: RecoveryCase) -> dict[str, Any]:
        events = sorted(case.linked_events, key=lambda e: e.timestamp)

        evidence: dict[str, Any] = {
            "event_count": len(events),
            "failure_codes": [],
            "error_messages": [],
            "has_nsf_evidence": False,
            "has_network_timeout": False,
            "has_expired_card": False,
            "has_mandate_issue": False,
            "has_dispute": False,
            "has_ar_delay": False,
            "abandonment_stage": None,
            "promise_date_passed": False,
        }

        now = datetime.now(UTC)

        for e in events:
            payload = e.raw_payload or {}
            failure_code = payload.get("failure_code") or payload.get("decline_code")
            if failure_code:
                fc = str(failure_code).strip().lower()
                evidence["failure_codes"].append(fc)

                if fc in ["insufficient_funds", "nsf", "balance_too_low", "not_enough_balance"]:
                    evidence["has_nsf_evidence"] = True
                if fc in [
                    "network_error",
                    "timeout",
                    "gateway_timeout",
                    "processor_unavailable",
                    "3ds_failed",
                ]:
                    evidence["has_network_timeout"] = True
                if fc in ["expired_card", "invalid_expiry", "card_expired"]:
                    evidence["has_expired_card"] = True
                # M1d — mandate / authorisation problems (subscriptions, cards)
                if fc in [
                    "do_not_honor",
                    "card_declined",
                    "declined",
                    "authentication_required",
                    "mandate_cancelled",
                    "mandate_failure",
                    "revoked",
                    "pickup_card",
                    "restricted_card",
                ]:
                    evidence["has_mandate_issue"] = True
                # M1d — an open dispute on the obligation
                if fc in [
                    "dispute",
                    "disputed",
                    "payment_dispute",
                    "chargeback",
                    "under_review",
                    "contested",
                ]:
                    evidence["has_dispute"] = True
                # M1d — receivables / B2B collection delay
                if fc in [
                    "net_terms_pending",
                    "net_terms_exceeded",
                    "awaiting_approval",
                    "awaiting_po_number",
                    "no_response",
                    "budget_freeze",
                    "bank_rejected",
                    "account_closed",
                    "invalid_account_number",
                    "name_mismatch",
                ]:
                    evidence["has_ar_delay"] = True

            error_msg = payload.get("error_message")
            if error_msg:
                evidence["error_messages"].append(error_msg)

            stage = (
                payload.get("checkout_stage")
                or payload.get("checkout_phase")
                or payload.get("stage")
            )
            if stage:
                s = str(stage).strip().lower()
                evidence["abandonment_stage"] = (
                    "payment" if ("payment" in s or "pay_" in s or s == "pay") else s
                )

            promise_date_str = payload.get("promise_date")
            if promise_date_str:
                try:
                    promise_date = datetime.fromisoformat(promise_date_str)
                    if promise_date.tzinfo is None:
                        promise_date = promise_date.replace(tzinfo=UTC)
                    if promise_date < now:
                        evidence["promise_date_passed"] = True
                except ValueError:
                    pass

        return evidence


class DeterministicDiagnosisEngine:
    """Diagnoses the root cause deterministically based on structured evidence."""

    def __init__(self, version: str = "deterministic-v1.0"):
        self.version = version

    def diagnose(self, case: RecoveryCase) -> RootCauseDiagnosis:
        evidence = EvidenceBuilder.extract_evidence(case)
        event_ids = [e.event_id for e in case.linked_events]

        cause = RootCauseCategory.UNKNOWN
        status = DiagnosisStatus.UNKNOWN
        confidence = 0.0

        # Conflicting Evidence Check
        if evidence["has_nsf_evidence"] and evidence["has_expired_card"]:
            return RootCauseDiagnosis(
                diagnosis_id=f"diag_{uuid.uuid4().hex[:8]}",
                cause_category=RootCauseCategory.CONFLICTING_EVIDENCE,
                confidence=0.3,
                status=DiagnosisStatus.UNKNOWN,
                supporting_signals={"conflict": "NSF and Expired Card both present"},
                evidence_references=event_ids,
                diagnostic_method=self.version,
            )

        if case.risk_category == RiskCategory.FAILED_PAYMENT:
            if evidence["has_nsf_evidence"]:
                cause = RootCauseCategory.INSUFFICIENT_FUNDS
                status = DiagnosisStatus.CONFIRMED
                confidence = 0.95
            elif evidence["has_network_timeout"]:
                cause = RootCauseCategory.NETWORK_FAILURE
                status = DiagnosisStatus.INFERRED
                confidence = 0.70
            elif evidence["has_expired_card"]:
                cause = RootCauseCategory.PAYMENT_METHOD_INVALID
                status = DiagnosisStatus.CONFIRMED
                confidence = 0.95
            elif evidence["has_mandate_issue"]:
                cause = RootCauseCategory.MANDATE_FAILURE
                status = DiagnosisStatus.INFERRED
                confidence = 0.65

        elif case.risk_category == RiskCategory.CHECKOUT_ABANDONMENT:
            if evidence["abandonment_stage"] == "payment":
                cause = RootCauseCategory.PAYMENT_FRICTION
                status = DiagnosisStatus.INFERRED
                confidence = 0.80
            elif (
                evidence["has_nsf_evidence"]
                or evidence["has_expired_card"]
                or evidence["has_mandate_issue"]
            ):
                cause = RootCauseCategory.PAYMENT_METHOD_INVALID
                status = DiagnosisStatus.INFERRED
                confidence = 0.60
            elif evidence["abandonment_stage"] in (
                "address",
                "shipping",
                "billing",
                "details",
                "review",
                "confirmation",
            ):
                cause = RootCauseCategory.PAYMENT_FRICTION
                status = DiagnosisStatus.INFERRED
                confidence = 0.55

        elif case.risk_category == RiskCategory.FAILED_SUBSCRIPTION:
            if evidence["has_nsf_evidence"]:
                cause = RootCauseCategory.INSUFFICIENT_FUNDS
                status = DiagnosisStatus.CONFIRMED
                confidence = 0.95
            elif evidence["has_expired_card"]:
                cause = RootCauseCategory.PAYMENT_METHOD_INVALID
                status = DiagnosisStatus.CONFIRMED
                confidence = 0.90
            elif evidence["has_mandate_issue"] or evidence["failure_codes"]:
                cause = RootCauseCategory.MANDATE_FAILURE
                status = DiagnosisStatus.INFERRED
                confidence = 0.60

        elif case.risk_category == RiskCategory.OVERDUE_INVOICE:
            if evidence["has_dispute"]:
                cause = RootCauseCategory.UNRESOLVED_DISPUTE
                status = DiagnosisStatus.INFERRED
                confidence = 0.70
            elif evidence["has_ar_delay"] or evidence["failure_codes"]:
                cause = RootCauseCategory.MISSED_COMMITMENT
                status = DiagnosisStatus.INFERRED
                confidence = 0.55
            elif evidence["event_count"] > 1:
                cause = RootCauseCategory.UNRESOLVED_DISPUTE
                status = DiagnosisStatus.INFERRED
                confidence = 0.50

        elif case.risk_category == RiskCategory.BROKEN_PROMISE:
            if evidence["promise_date_passed"]:
                cause = RootCauseCategory.MISSED_COMMITMENT
                status = DiagnosisStatus.CONFIRMED
                confidence = 0.90
            elif evidence["failure_codes"]:
                cause = RootCauseCategory.MISSED_COMMITMENT
                status = DiagnosisStatus.INFERRED
                confidence = 0.55

        # M1d — generic fallback: a named failure code we didn't specifically
        # recognise still points at a mandate/authorisation problem, not "unknown".
        if cause == RootCauseCategory.UNKNOWN and evidence["failure_codes"]:
            cause = RootCauseCategory.MANDATE_FAILURE
            status = DiagnosisStatus.INFERRED
            confidence = 0.40

        return RootCauseDiagnosis(
            diagnosis_id=f"diag_{uuid.uuid4().hex[:8]}",
            cause_category=cause,
            confidence=confidence,
            status=status,
            supporting_signals=evidence,
            evidence_references=event_ids,
            diagnostic_method=self.version,
        )
