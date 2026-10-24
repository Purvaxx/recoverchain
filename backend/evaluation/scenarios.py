from datetime import UTC, datetime, timedelta
from typing import Any

from domain.models import (
    ActionType,
    Money,
    PolicyDecisionStatus,
    RecoveryOutcomeStatus,
    RevenueEvent,
    RiskCategory,
)
from evaluation.models import EvaluationScenario, GoldExpectation

now = datetime.now(UTC)


def create_event(
    id_suffix: str,
    amount: float,
    time_offset_hours: int = 0,
    case_ref: str = None,
    category: RiskCategory = RiskCategory.FAILED_PAYMENT,
    payload: dict[str, Any] = None,
) -> RevenueEvent:
    if payload is None:
        payload = {"failure_code": "insufficient_funds"}
    return RevenueEvent(
        event_id=f"evt_{id_suffix}",
        customer_id=f"cust_{case_ref or id_suffix}",
        risk_category=category,
        external_system="system_test",
        external_event_id=f"ext_{id_suffix}",
        reference_id=f"ref_{case_ref or id_suffix}",
        amount=Money(amount=amount),
        timestamp=now - timedelta(hours=time_offset_hours),
        raw_payload=payload,
    )


SCENARIOS = [
    # --- FAILED_PAYMENT ---
    EvaluationScenario(
        scenario_id="FP_1_STANDARD",
        description="Standard retry for low value FAILED_PAYMENT within policy limits.",
        events=[
            create_event(
                "FP_1",
                100.0,
                25,
                "FP_1",
                RiskCategory.FAILED_PAYMENT,
                {"failure_code": "insufficient_funds"},
            )
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="INSUFFICIENT_FUNDS",
            expected_action_type=ActionType.RETRY_PAYMENT,
            expected_policy_status=PolicyDecisionStatus.PERMITTED,
            expected_execution_status="COMPLETED_SIMULATED",
            expected_outcome_status=RecoveryOutcomeStatus.FULLY_RECOVERED,
            expected_simulated_verification="sim_full",
        ),
    ),
    EvaluationScenario(
        scenario_id="FP_2_HIGH_VALUE",
        description="High value FAILED_PAYMENT, exceeds policy automated limit.",
        events=[
            create_event(
                "FP_2",
                15000.0,
                25,
                "FP_2",
                RiskCategory.FAILED_PAYMENT,
                {"failure_code": "insufficient_funds"},
            )
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="INSUFFICIENT_FUNDS",
            expected_action_type=ActionType.RETRY_PAYMENT,
            expected_policy_status=PolicyDecisionStatus.ESCALATE,
            expected_execution_status="REJECTED",
            expected_outcome_status=RecoveryOutcomeStatus.PENDING_VERIFICATION,
            expected_simulated_verification="sim_pending",
        ),
    ),
    EvaluationScenario(
        scenario_id="FP_3_MAX_RETRIES",
        description="Exceeds retry limit for FAILED_PAYMENT.",
        events=[
            create_event(
                "FP_3_1",
                100.0,
                50,
                "FP_3",
                RiskCategory.FAILED_PAYMENT,
                {"failure_code": "insufficient_funds"},
            ),
            create_event(
                "FP_3_2",
                100.0,
                48,
                "FP_3",
                RiskCategory.FAILED_PAYMENT,
                {"failure_code": "insufficient_funds"},
            ),
            create_event(
                "FP_3_3",
                100.0,
                46,
                "FP_3",
                RiskCategory.FAILED_PAYMENT,
                {"failure_code": "insufficient_funds"},
            ),
            create_event(
                "FP_3_4",
                100.0,
                44,
                "FP_3",
                RiskCategory.FAILED_PAYMENT,
                {"failure_code": "insufficient_funds"},
            ),
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="INSUFFICIENT_FUNDS",
            expected_action_type=ActionType.RETRY_PAYMENT,
            expected_policy_status=PolicyDecisionStatus.DENIED,
            expected_execution_status="REJECTED",
            expected_outcome_status=RecoveryOutcomeStatus.PENDING_VERIFICATION,
            expected_simulated_verification="sim_pending",
        ),
    ),
    EvaluationScenario(
        scenario_id="FP_4_PARTIAL",
        description="Permitted retry resulting in partial payment.",
        events=[
            create_event(
                "FP_4",
                100.0,
                25,
                "FP_4",
                RiskCategory.FAILED_PAYMENT,
                {"failure_code": "insufficient_funds"},
            )
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="INSUFFICIENT_FUNDS",
            expected_action_type=ActionType.RETRY_PAYMENT,
            expected_policy_status=PolicyDecisionStatus.PERMITTED,
            expected_execution_status="COMPLETED_SIMULATED",
            expected_outcome_status=RecoveryOutcomeStatus.PARTIALLY_RECOVERED,
            expected_simulated_verification="sim_partial",
        ),
    ),
    EvaluationScenario(
        scenario_id="FP_5_FAILED",
        description="Permitted retry resulting in failed payment.",
        events=[
            create_event(
                "FP_5",
                100.0,
                25,
                "FP_5",
                RiskCategory.FAILED_PAYMENT,
                {"failure_code": "insufficient_funds"},
            )
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="INSUFFICIENT_FUNDS",
            expected_action_type=ActionType.RETRY_PAYMENT,
            expected_policy_status=PolicyDecisionStatus.PERMITTED,
            expected_execution_status="COMPLETED_SIMULATED",
            expected_outcome_status=RecoveryOutcomeStatus.NOT_RECOVERED,
            expected_simulated_verification="sim_fail",
        ),
    ),
    EvaluationScenario(
        scenario_id="FP_6_COOLDOWN",
        description="Cooldown period active for FAILED_PAYMENT, should wait.",
        events=[
            create_event(
                "FP_6",
                100.0,
                1,
                "FP_6",
                RiskCategory.FAILED_PAYMENT,
                {"failure_code": "insufficient_funds"},
            )
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="INSUFFICIENT_FUNDS",
            expected_action_type=ActionType.RETRY_PAYMENT,
            expected_policy_status=PolicyDecisionStatus.WAIT,
            expected_execution_status="REJECTED",
            expected_outcome_status=RecoveryOutcomeStatus.PENDING_VERIFICATION,
            expected_simulated_verification="sim_pending",
        ),
    ),
    # --- CHECKOUT_ABANDONMENT ---
    EvaluationScenario(
        scenario_id="CA_1_STANDARD",
        description="Standard checkout abandonment.",
        events=[
            create_event(
                "CA_1",
                250.0,
                25,
                "CA_1",
                RiskCategory.CHECKOUT_ABANDONMENT,
                {"checkout_stage": "payment"},
            )
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="PAYMENT_FRICTION",
            expected_action_type=ActionType.SEND_CHECKOUT_REMINDER,
            expected_policy_status=PolicyDecisionStatus.PERMITTED,
            expected_execution_status="COMPLETED_SIMULATED",
            expected_outcome_status=RecoveryOutcomeStatus.FULLY_RECOVERED,
            expected_simulated_verification="sim_full",
        ),
    ),
    EvaluationScenario(
        scenario_id="CA_2_COOLDOWN",
        description="Cooldown period active for CHECKOUT_ABANDONMENT (max communications exceeded), should wait.",
        events=[
            create_event(
                "CA_2_1",
                250.0,
                4,
                "CA_2",
                RiskCategory.CHECKOUT_ABANDONMENT,
                {"checkout_stage": "payment"},
            ),
            create_event(
                "CA_2_2",
                250.0,
                3,
                "CA_2",
                RiskCategory.CHECKOUT_ABANDONMENT,
                {"checkout_stage": "payment"},
            ),
            create_event(
                "CA_2_3",
                250.0,
                2,
                "CA_2",
                RiskCategory.CHECKOUT_ABANDONMENT,
                {"checkout_stage": "payment"},
            ),
            create_event(
                "CA_2_4",
                250.0,
                1,
                "CA_2",
                RiskCategory.CHECKOUT_ABANDONMENT,
                {"checkout_stage": "payment"},
            ),
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="PAYMENT_FRICTION",
            expected_action_type=ActionType.SEND_CHECKOUT_REMINDER,
            expected_policy_status=PolicyDecisionStatus.WAIT,
            expected_execution_status="REJECTED",
            expected_outcome_status=RecoveryOutcomeStatus.PENDING_VERIFICATION,
            expected_simulated_verification="sim_pending",
        ),
    ),
    # --- FAILED_SUBSCRIPTION ---
    EvaluationScenario(
        scenario_id="FS_1_STANDARD",
        description="Standard failed subscription with mandate failure.",
        events=[
            create_event(
                "FS_1",
                50.0,
                25,
                "FS_1",
                RiskCategory.FAILED_SUBSCRIPTION,
                {"failure_code": "mandate_revoked"},
            )
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="MANDATE_FAILURE",
            expected_action_type=ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
            expected_policy_status=PolicyDecisionStatus.PERMITTED,
            expected_execution_status="COMPLETED_SIMULATED",
            expected_outcome_status=RecoveryOutcomeStatus.FULLY_RECOVERED,
            expected_simulated_verification="sim_full",
        ),
    ),
    # --- OVERDUE_INVOICE ---
    EvaluationScenario(
        scenario_id="OI_1_STANDARD",
        description="Standard overdue invoice with unknown diagnosis, maps to SEND_INVOICE_REMINDER.",
        events=[
            create_event(
                "OI_1", 500.0, 25, "OI_1", RiskCategory.OVERDUE_INVOICE, {"days_overdue": 30}
            )
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="UNKNOWN",
            expected_action_type=ActionType.SEND_INVOICE_REMINDER,
            expected_policy_status=PolicyDecisionStatus.PERMITTED,
            expected_execution_status="COMPLETED_SIMULATED",
            expected_outcome_status=RecoveryOutcomeStatus.FULLY_RECOVERED,
            expected_simulated_verification="sim_full",
        ),
    ),
    # --- BROKEN_PROMISE ---
    EvaluationScenario(
        scenario_id="BP_1_STANDARD",
        description="Standard broken promise with unknown diagnosis, maps to REQUEST_NEW_COMMITMENT (due to alphabetic sorting tiebreaker).",
        events=[
            create_event(
                "BP_1",
                1000.0,
                25,
                "BP_1",
                RiskCategory.BROKEN_PROMISE,
                {"promise_date_passed": True},
            )
        ],
        gold=GoldExpectation(
            expected_diagnosis_category="UNKNOWN",
            expected_action_type=ActionType.REQUEST_NEW_COMMITMENT,
            expected_policy_status=PolicyDecisionStatus.PERMITTED,
            expected_execution_status="COMPLETED_SIMULATED",
            expected_outcome_status=RecoveryOutcomeStatus.FULLY_RECOVERED,
            expected_simulated_verification="sim_full",
        ),
    ),
    # --- MISSING EVIDENCE ---
    EvaluationScenario(
        scenario_id="ME_1_NO_PAYLOAD",
        description="Missing raw payload, defaults to unknown diagnosis, for FAILED_PAYMENT this is ESCALATE_TO_HUMAN.",
        events=[create_event("ME_1", 100.0, 25, "ME_1", RiskCategory.FAILED_PAYMENT, {})],
        gold=GoldExpectation(
            expected_diagnosis_category="UNKNOWN",
            expected_action_type=ActionType.ESCALATE_TO_HUMAN,
            expected_policy_status=PolicyDecisionStatus.ESCALATE,
            expected_execution_status="REJECTED",
            expected_outcome_status=RecoveryOutcomeStatus.PENDING_VERIFICATION,
            expected_simulated_verification="sim_pending",
        ),
    ),
]
