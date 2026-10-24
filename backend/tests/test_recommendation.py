import pytest

from application.action_evaluator import DeterministicActionEvaluator
from domain.models import (
    ActionType,
    DiagnosisStatus,
    Money,
    RecommendationStatus,
    RecoveryCase,
    RecoveryPrediction,
    RiskAssessment,
    RiskCategory,
    RiskLevel,
    RootCauseCategory,
    RootCauseDiagnosis,
)


def create_mock_case(
    risk_category: RiskCategory,
    diag_cat: RootCauseCategory,
    prob: float = 0.5,
    amount: float = 100.0,
) -> RecoveryCase:
    return RecoveryCase(
        case_id="case_1",
        customer_id="cust_test",
        risk_category=risk_category,
        reference_id="ref_1",
        amount_at_risk=Money(amount=amount),
        risk_assessment=RiskAssessment(
            score=0.8,
            risk_level=RiskLevel.HIGH,
            detection_status="SUCCESS",
            primary_risk_signals={},
            contributing_evidence_references=[],
        ),
        diagnosis=RootCauseDiagnosis(
            diagnosis_id="diag_1",
            cause_category=diag_cat,
            confidence=0.9,
            status=DiagnosisStatus.CONFIRMED,
            supporting_signals={},
            evidence_references=[],
        ),
        prediction=RecoveryPrediction(
            prediction_id="pred_1",
            recovery_probability=prob,
            confidence=0.5,
            model_version="test",
            feature_version="test",
            contributing_features={},
            prediction_status="test",
        ),
    )


@pytest.fixture
def evaluator():
    return DeterministicActionEvaluator()


def test_A_B_C_strong_evidence(evaluator):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT, RootCauseCategory.NETWORK_FAILURE)
    rec = evaluator.evaluate(case)
    assert rec.status == RecommendationStatus.RECOMMENDED
    assert len(rec.candidates) == 1
    assert rec.candidates[0].action_type == ActionType.RETRY_PAYMENT
    assert rec.top_candidate.action_type == ActionType.RETRY_PAYMENT


def test_D_insufficient_evidence(evaluator):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT, RootCauseCategory.NETWORK_FAILURE)
    case.prediction = None  # Missing prediction
    rec = evaluator.evaluate(case)
    assert rec.status == RecommendationStatus.INSUFFICIENT_EVIDENCE
    assert len(rec.candidates) == 0


def test_E_F_G_ERV_calculation(evaluator):
    case = create_mock_case(
        RiskCategory.CHECKOUT_ABANDONMENT,
        RootCauseCategory.PAYMENT_FRICTION,
        prob=0.8,
        amount=200.0,
    )
    rec = evaluator.evaluate(case)
    assert rec.status == RecommendationStatus.RECOMMENDED
    cand = [c for c in rec.candidates if c.action_type == ActionType.SEND_CHECKOUT_REMINDER][0]
    # action prob = 0.8 * 1.1 = 0.88
    # erv = 0.88 * 200 = 176.0
    assert cand.expected_recoverable_value == 176.0


def test_H_I_Ranking(evaluator):
    # INSUFFICIENT_FUNDS generates RETRY and REMINDER
    case = create_mock_case(
        RiskCategory.FAILED_PAYMENT, RootCauseCategory.INSUFFICIENT_FUNDS, prob=0.5, amount=100.0
    )
    rec = evaluator.evaluate(case)
    # Both have same ERV currently. Tie breaking by alphabetical ActionType
    # RETRY_PAYMENT vs SEND_PAYMENT_REMINDER
    assert rec.top_candidate.action_type == ActionType.RETRY_PAYMENT


def test_J_K_L_state_preservation(evaluator):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT, RootCauseCategory.NETWORK_FAILURE)
    evaluator.evaluate(case)
    # State should not be mutated by evaluate alone
    assert case.risk_assessment.score == 0.8
    assert case.diagnosis.cause_category == RootCauseCategory.NETWORK_FAILURE
    assert case.prediction.recovery_probability == 0.5


def test_M_N_no_execution(evaluator):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT, RootCauseCategory.NETWORK_FAILURE)
    rec = evaluator.evaluate(case)
    assert not hasattr(rec, "approved")
    assert not hasattr(rec, "executed")


def test_O_human_escalation(evaluator):
    case = create_mock_case(RiskCategory.FAILED_PAYMENT, RootCauseCategory.UNKNOWN)
    rec = evaluator.evaluate(case)
    assert rec.top_candidate.action_type == ActionType.ESCALATE_TO_HUMAN


def test_edge_zero_amount(evaluator):
    case = create_mock_case(
        RiskCategory.FAILED_PAYMENT, RootCauseCategory.NETWORK_FAILURE, amount=0.0
    )
    rec = evaluator.evaluate(case)
    assert rec.top_candidate.expected_recoverable_value == 0.0


def test_edge_zero_probability(evaluator):
    case = create_mock_case(
        RiskCategory.FAILED_PAYMENT, RootCauseCategory.NETWORK_FAILURE, prob=0.0
    )
    rec = evaluator.evaluate(case)
    assert rec.top_candidate.expected_recoverable_value == 0.0
