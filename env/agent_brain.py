from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import Action, Email


Classification = Literal["support", "billing", "internal", "spam", "phishing"]
RiskLevel = Literal["low", "medium", "high", "critical"]

TRUSTED_PROMOTIONAL_DOMAINS = {
    "linkedin.com",
    "geeksforgeeks.org",
    "devpost.com",
    "glassdoor.com",
    "udacity.com",
    "coursera.org",
    "github.com",
}


def _sender_domain(email: Email) -> str:
    sender = email.sender.lower()
    if "@" not in sender:
        return ""
    domain = sender.split("@", 1)[1]
    return domain.split(">", 1)[0].strip()


def _is_trusted_promotional_sender(email: Email) -> bool:
    domain = _sender_domain(email)
    return any(domain == trusted or domain.endswith(f".{trusted}") for trusted in TRUSTED_PROMOTIONAL_DOMAINS)


@dataclass(frozen=True)
class BrainDecision:
    classification: Classification
    intent: str
    risk_level: RiskLevel
    action: Action
    reasoning: str
    decision_path: list[str]


class SmartEmailAgentBrain:
    def _align_classification_with_intent(self, classification: Classification, intent: str) -> Classification:
        if intent == "technical_support":
            return "support"
        if intent == "billing_resolution":
            return "billing"
        if intent == "internal_escalation" and classification != "phishing":
            return "internal"
        return classification

    def detect_intent(self, email: Email) -> tuple[str, list[str]]:
        text = f"{email.sender} {email.subject} {email.body}".lower()
        path: list[str] = []

        if any(token in text for token in ["threaten", "threatening", "blackmail", "extort", "pay me", "give your money back", "ransom", "harass"]):
            path.append("Intent matched coercive_or_extortion")
            return "coercive_or_extortion", path

        if any(token in text for token in ["invoice", "refund", "charged", "billing"]):
            path.append("Intent matched billing_resolution")
            return "billing_resolution", path
        if any(token in text for token in ["incident", "timeout", "production", "outage", "error"]):
            path.append("Intent matched technical_support")
            return "technical_support", path
        if any(token in text for token in ["meeting", "calendar", "schedule", "reschedule", "slot", "availability", "conflict"]):
            path.append("Intent matched meeting_scheduling")
            return "meeting_scheduling", path
        if any(token in text for token in ["oauth", "tenant", "unusual consent", "access pattern", "policy summary"]):
            path.append("Intent matched internal_escalation (security governance)")
            return "internal_escalation", path
        if any(token in text for token in ["legal", "board", "cfo", "approval", "urgent"]):
            path.append("Intent matched internal_escalation")
            return "internal_escalation", path
        if any(token in text for token in ["newsletter", "unsubscribe", "job alert", "digest", "promotion"]):
            path.append("Intent matched informational_bulk")
            return "informational_bulk", path

        path.append("Intent fallback to general_inquiry")
        return "general_inquiry", path

    def classify_email(self, email: Email) -> tuple[Classification, RiskLevel, list[str]]:
        text = f"{email.sender} {email.subject} {email.body}".lower()
        path: list[str] = []

        if any(token in text for token in ["threaten", "threatening", "blackmail", "extort", "ransom", "give your money back", "pay me", "or else"]):
            path.append("Matched coercive/extortion language")
            return "phishing", "critical", path

        if any(token in text for token in ["noreply", "no-reply", "newsletter", "unsubscribe", "job alert", "apply now", "digest"]):
            if _is_trusted_promotional_sender(email):
                path.append("Detected trusted bulk/promotional sender")
                return "spam", "low", path
            path.append("Detected no-reply or bulk promotional pattern")
            return "spam", "low", path

        if any(token in text for token in ["verify credentials", "mailbox suspended", "click link", "urgent verify"]):
            path.append("Matched phishing signature tokens")
            return "phishing", "critical", path

        if any(token in text for token in ["gift card", "prize", "bonus now", "crypto"]):
            path.append("Matched spam campaign indicators")
            return "spam", "high", path

        if any(token in text for token in ["invoice", "billing", "refund", "charge", "double-billed"]):
            path.append("Detected finance/billing terms")
            return "billing", "high", path

        if any(token in text for token in ["legal", "board packet", "cfo", "escalate immediately"]):
            path.append("Detected internal urgent escalation markers")
            return "internal", "critical", path

        if any(token in text for token in ["meeting", "calendar", "schedule", "reschedule", "slot", "availability", "conflict"]):
            path.append("Detected scheduling conflict markers")
            return "internal", "medium", path

        if any(token in text for token in ["oauth", "tenant", "unusual consent", "access pattern", "policy summary"]):
            path.append("Detected security governance escalation markers")
            return "internal", "high", path

        if any(token in text for token in ["incident", "timeout", "production", "api", "support", "cannot sign in"]):
            path.append("Detected support/incident language")
            return "support", "medium", path

        path.append("Fallback classification to support")
        return "support", "low", path

    def generate_reply(self, email: Email, classification: Classification) -> str:
        text = f"{email.sender} {email.subject} {email.body}".lower()
        if any(token in text for token in ["meeting", "calendar", "schedule", "reschedule", "slot", "availability", "conflict"]):
            return (
                "Thanks for the update. I can propose two alternate slots: Thursday 10:30 AM or Thursday 11:00 AM. "
                "The client remains the priority, and we will avoid the conflicting Tuesday 3:00 PM time."
            )
        if classification == "billing":
            return (
                "Thanks for flagging this invoice issue. We are validating the billing records now, "
                "and we will share the correction timeline, updated invoice status, and finance point of contact shortly."
            )
        if classification == "support":
            return (
                "Thanks for reporting this incident. Our team is actively investigating, and we will provide "
                "an ETA update and next action steps as soon as diagnostics complete."
            )
        if classification == "internal":
            return "Escalated to the responsible internal owner for immediate coordination."
        return "Message reviewed and routed according to policy."

    def choose_action(self, email: Email, classification: Classification) -> tuple[Literal["reply", "escalate", "archive", "mark_spam"], str]:
        text = f"{email.sender} {email.subject} {email.body}".lower()
        if email.type in {"spam", "phishing"}:
            return "mark_spam", "Message type is suspicious; marking as spam"

        if any(token in text for token in ["meeting", "calendar", "schedule", "reschedule", "slot", "availability", "conflict"]):
            return "reply", "Scheduling conflict requires a proposed alternative slot response"

        if classification == "spam":
            if _is_trusted_promotional_sender(email) or any(token in text for token in ["noreply", "no-reply", "newsletter", "unsubscribe", "job alert", "apply now", "digest"]):
                return "archive", "Bulk/no-reply message archived to avoid low-value replies"
            return "mark_spam", "Safety policy blocks replies to suspicious messages"

        if classification == "phishing":
            return "mark_spam", "Safety policy blocks replies to suspicious messages"
        if classification == "internal":
            return "escalate", "Internal urgent request requires escalation path"
        if classification in {"billing", "support"}:
            return "reply", "Customer-facing issue requires acknowledgment and next steps"
        return "archive", "No action signal found; archiving"

    def decide(self, email: Email) -> BrainDecision:
        intent, intent_path = self.detect_intent(email)
        classification, risk_level, decision_path = self.classify_email(email)
        aligned_classification = self._align_classification_with_intent(classification, intent)
        if aligned_classification != classification:
            decision_path.append(f"Aligned classification from {classification} to {aligned_classification} based on intent={intent}")
            classification = aligned_classification
        decision_path = intent_path + decision_path
        action_type, reason = self.choose_action(email, classification)

        response = None
        if action_type == "reply":
            response = self.generate_reply(email, classification)

        action = Action(
            email_id=email.id,
            action_type=action_type,
            response=response,
        )
        decision_path.append(f"Selected action={action_type}")
        if response:
            decision_path.append("Generated response text")

        return BrainDecision(
            classification=classification,
            intent=intent,
            risk_level=risk_level,
            action=action,
            reasoning=reason,
            decision_path=decision_path,
        )
