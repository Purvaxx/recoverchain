from abc import ABC, abstractmethod

from domain.models import (
    CandidateAction,
    Money,
    PolicyDecision,
    RecoveryCase,
    RecoveryOutcome,
    RevenueEvent,
)

# --- Core Domain Orchestration Interfaces ---


class IEventIngestion(ABC):
    @abstractmethod
    def ingest(self, raw_payload: dict) -> RevenueEvent:
        pass


class ICaseRepository(ABC):
    @abstractmethod
    def save(self, case: RecoveryCase) -> None:
        pass

    @abstractmethod
    def get_by_id(self, case_id: str) -> RecoveryCase | None:
        pass

    @abstractmethod
    def get_event_by_external_id(
        self, external_system: str, external_event_id: str
    ) -> RevenueEvent | None:
        """Used for idempotency / deduplication"""

    @abstractmethod
    def get_active_case_for_customer(
        self, customer_id: str, risk_category: str, reference_id: str | None
    ) -> RecoveryCase | None:
        """Finds an open/active case matching the customer, risk category, and financial obligation reference."""


class ICaseStateManager(ABC):
    @abstractmethod
    def transition_state(self, case: RecoveryCase, to_state: str) -> None:
        pass


class IPolicyEvaluator(ABC):
    @abstractmethod
    def evaluate(self, case: RecoveryCase, action: CandidateAction) -> PolicyDecision:
        pass


class IOutcomeVerification(ABC):
    @abstractmethod
    def verify(self, case: RecoveryCase) -> RecoveryOutcome:
        pass


class IAuditRecorder(ABC):
    @abstractmethod
    def log_transition(self, case_id: str, from_state: str, to_state: str, evidence: dict) -> None:
        pass


# --- External Adapter Boundaries ---


class IPaymentAdapter(ABC):
    @abstractmethod
    def trigger_retry(self, customer_id: str, amount: Money) -> str:
        """Returns an execution tracking ID"""


class ICheckoutAdapter(ABC):
    @abstractmethod
    def retrieve_session(self, session_id: str) -> dict:
        pass


class ISubscriptionAdapter(ABC):
    @abstractmethod
    def get_subscription_status(self, subscription_id: str) -> str:
        pass


class IInvoiceAdapter(ABC):
    @abstractmethod
    def get_invoice_details(self, invoice_id: str) -> dict:
        pass


class ICommunicationAdapter(ABC):
    @abstractmethod
    def send_message(self, customer_id: str, template: str, context: dict) -> str:
        """Returns an execution tracking ID"""


class ICRMAdapter(ABC):
    @abstractmethod
    def check_consent(self, customer_id: str) -> bool:
        pass
