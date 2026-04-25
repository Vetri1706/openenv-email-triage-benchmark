from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional

from dotenv import dotenv_values
from openai import OpenAI

from env.agent_brain import SmartEmailAgentBrain
from env.models import Action, Email, Observation
from live_email import LiveEmailSession, ProviderType


def _load_env() -> None:
    values = dotenv_values('.env')
    for key, value in values.items():
        if value is not None:
            os.environ[key] = value


def _priority_rank(priority: str) -> int:
    mapping = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return mapping.get(priority, 0)

def _value_rank(email: Email) -> int:
    if email.type == "internal":
        return 4
    if email.type == "billing":
        return 3
    if email.type == "support":
        return 2
    if email.type in {"spam", "phishing"}:
        return 0
    return 1


def _safe_text(value: str, max_len: int = 88) -> str:
    text = (value or "").replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 3]}..."


def _extract_json_object(text: str) -> Dict[str, Any]:
    candidate = (text or "").strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1]
        if candidate.endswith("```"):
            candidate = candidate[:-3]
        candidate = candidate.strip()

    try:
        value = json.loads(candidate)
        if isinstance(value, dict):
            return value
    except Exception:
        pass

    left = candidate.find("{")
    right = candidate.rfind("}")
    if left != -1 and right != -1 and right > left:
        try:
            value = json.loads(candidate[left : right + 1])
            if isinstance(value, dict):
                return value
        except Exception:
            return {}
    return {}


class ThreeAgentTriageEngine:
    def __init__(self, brain: SmartEmailAgentBrain) -> None:
        self.brain = brain
        self.client = self._build_client()
        self.model_name = (
            os.getenv("MODEL_NAME")
            or os.getenv("OPENAI_MODEL")
            or os.getenv("LITELLM_MODEL")
            or "gpt-4o-mini"
        )

    def _build_client(self) -> Optional[OpenAI]:
        api_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
        api_base_url = os.getenv("API_BASE_URL")
        if not api_key:
            return None
        try:
            return OpenAI(api_key=api_key, base_url=api_base_url)
        except Exception:
            return None

    def _llm_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> Dict[str, Any]:
        if self.client is None:
            return {}
        try:
            result = self.client.chat.completions.create(
                model=self.model_name,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=12.0,
            )
            return _extract_json_object(result.choices[0].message.content or "")
        except Exception:
            return {}

    def _is_bulk_or_automated(self, email: Email) -> bool:
        text = f"{email.sender} {email.subject} {email.body}".lower()
        return any(
            token in text
            for token in [
                "no-reply",
                "noreply",
                "newsletter",
                "digest",
                "unsubscribe",
                "notifications@",
                "mailer-daemon",
            ]
        )

    def _is_incident_like(self, email: Email) -> bool:
        text = f"{email.subject} {email.body}".lower()
        return any(
            token in text
            for token in [
                "incident",
                "error",
                "failed",
                "failure",
                "timeout",
                "production",
                "outage",
                "delivery status notification",
                "run failed",
                "build failed",
            ]
        )

    def _contains_any(self, text: str, tokens: list[str]) -> bool:
        return any(token in text for token in tokens)

    def _normalize_action(self, raw_action: str, email: Email, reasoning: Dict[str, Any]) -> tuple[str, str]:
        action = (raw_action or "").strip().lower()
        classification = str(reasoning.get("classification", "")).lower()
        if action == "report":
            return "escalate", "normalized report->escalate"
        if action == "delete":
            if classification in {"spam", "phishing"} or email.type in {"spam", "phishing"}:
                return "mark_spam", "normalized delete->mark_spam for suspicious mail"
            return "archive", "normalized delete->archive for non-suspicious mail"
        if action not in {"reply", "escalate", "archive", "mark_spam"}:
            return "archive", f"invalid action '{action}' normalized to archive"
        return action, "action accepted"

    def _god_mode_override(self, email: Email, reasoning: Dict[str, Any], action_type: str) -> tuple[str, str]:
        text = f"{email.sender} {email.subject} {email.body}".lower()
        promo_tokens = [
            "newsletter",
            "unsubscribe",
            "promotion",
            "offer",
            "discount",
            "job alert",
            "digest",
            "giveaway",
        ]
        phishing_tokens = [
            "verify credentials",
            "mailbox suspended",
            "click link",
            "gift card",
            "prize",
            "password suspended",
        ]
        security_tokens = [
            "security alert",
            "new login",
            "password reset",
            "oauth",
            "suspicious",
            "breach",
        ]

        if self._contains_any(text, phishing_tokens):
            return "mark_spam", "god-mode override: phishing signature detected"

        if self._contains_any(text, security_tokens) or self._is_incident_like(email):
            return "escalate", "god-mode override: incident/security signal detected"

        if self._is_bulk_or_automated(email) and self._contains_any(text, promo_tokens):
            if action_type == "reply":
                return "archive", "god-mode override: blocked low-value bulk reply"
            if action_type == "escalate":
                return "archive", "god-mode override: avoided unnecessary escalation on promotional bulk"

        return action_type, "god-mode pass"

    def _reasoning_agent(self, email: Email) -> Dict[str, Any]:
        prompt = (
            "Classify this email for enterprise triage.\n"
            "Return JSON keys: classification, intent, risk, confidence, signals.\n"
            "classification must be one of: support,billing,internal,spam,phishing.\n"
            "risk must be one of: low,medium,high,critical.\n"
            "signals must be a short list of evidence strings.\n\n"
            f"Sender: {email.sender}\n"
            f"Subject: {email.subject}\n"
            f"Body: {email.body}\n"
            f"Priority hint: {email.priority}\n"
            f"Type hint: {email.type}\n"
        )
        parsed = self._llm_json(
            "You are Reasoning Agent 1 for enterprise email triage. Be accurate and conservative.",
            prompt,
            temperature=0.0,
        )
        if parsed:
            return {
                "classification": str(parsed.get("classification", "support")).lower(),
                "intent": str(parsed.get("intent", "general_inquiry")).lower(),
                "risk": str(parsed.get("risk", "low")).lower(),
                "confidence": float(parsed.get("confidence", 0.5) or 0.5),
                "signals": parsed.get("signals") if isinstance(parsed.get("signals"), list) else ["llm reasoning"],
                "source": "llm",
            }

        fallback = self.brain.decide(email)
        return {
            "classification": fallback.classification,
            "intent": fallback.intent,
            "risk": fallback.risk_level,
            "confidence": 0.5,
            "signals": fallback.decision_path[:3],
            "source": "heuristic",
        }

    def _decision_agent(self, email: Email, reasoning: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "Choose one action for this email.\n"
            "Return JSON keys: action_type, rationale.\n"
            "action_type may be one of: reply,escalate,archive,mark_spam,report,delete.\n"
            "Rules:\n"
            "- Never reply to spam/phishing.\n"
            "- Escalate incident/security/internal urgent issues.\n"
            "- Archive newsletters/promotions and low-value no-reply updates.\n"
            "- Reply only when user-facing resolution is needed.\n\n"
            f"Reasoning: {json.dumps(reasoning)}\n"
            f"Sender: {email.sender}\n"
            f"Subject: {email.subject}\n"
            f"Body: {email.body}\n"
        )
        parsed = self._llm_json(
            "You are Decision Agent 2 for enterprise email triage. Optimize correctness and safety.",
            prompt,
            temperature=0.0,
        )
        if not parsed:
            fallback = self.brain.decide(email)
            return {
                "action_type": fallback.action.action_type,
                "rationale": f"heuristic fallback: {fallback.reasoning}",
                "source": "heuristic",
            }
        action_type = str(parsed.get("action_type", "archive")).lower()
        rationale = str(parsed.get("rationale", "decision from policy"))
        return {"action_type": action_type, "rationale": rationale, "source": "llm" if parsed else "heuristic"}

    def _auditor_agent(self, email: Email, reasoning: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
        action_type = decision["action_type"]
        classification = str(reasoning.get("classification", "support")).lower()

        # Hard safety policy: suspicious messages cannot be replied to.
        if classification in {"spam", "phishing"} or email.type in {"spam", "phishing"}:
            if action_type == "reply":
                action_type = "mark_spam"
                return {
                    "action_type": action_type,
                    "audit_note": "auditor override: blocked reply to suspicious mail",
                    "source": "auditor_policy",
                }

        # Bulk automation should not get routine replies.
        if action_type == "reply" and self._is_bulk_or_automated(email) and not self._is_incident_like(email):
            return {
                "action_type": "archive",
                "audit_note": "auditor override: archived bulk/automated non-incident mail",
                "source": "auditor_policy",
            }

        return {
            "action_type": action_type,
            "audit_note": "auditor pass",
            "source": "auditor_policy",
        }

    def _generate_response(self, email: Email, reasoning: Dict[str, Any], action_type: str) -> Optional[str]:
        intent = str(reasoning.get("intent", "general_inquiry")).lower()
        if action_type == "reply":
            if intent in {"technical_support", "production_issue"}:
                return "Acknowledged. We have received your issue and our team is investigating the root cause."
            if intent in {"billing_resolution", "billing"}:
                return "Acknowledged. Our billing team is reviewing your request and will update you shortly."
            return "Acknowledged. Our team is reviewing your request and will respond shortly."
        if action_type == "escalate":
            if intent in {"technical_support", "production_issue"}:
                return "Production-related issue detected and escalated to engineering for immediate investigation."
            if intent in {"internal_escalation", "security_alert"}:
                return "Security/internal alert detected and escalated for priority review."
            return "Critical issue detected and escalated."
        return None

    def build_action(self, email: Email, mode: str) -> tuple[Action, str, str, str, str]:
        if mode == "spam-only":
            return Action(email_id=email.id, action_type="mark_spam", response=None), "spam", "spam_only_mode", "low", "forced spam-only mode"

        reasoning = self._reasoning_agent(email)
        decision = self._decision_agent(email, reasoning)
        normalized_action, normalization_note = self._normalize_action(decision.get("action_type", "archive"), email, reasoning)
        decision["action_type"] = normalized_action
        audit = self._auditor_agent(email, reasoning, decision)
        action_type, god_note = self._god_mode_override(email, reasoning, audit["action_type"])
        response = self._generate_response(email, reasoning, action_type)
        if action_type != "reply":
            response = None

        rationale = (
            f"{decision.get('rationale', 'n/a')} | "
            f"{normalization_note} | "
            f"{audit.get('audit_note', 'auditor pass')} | "
            f"{god_note}"
        )
        return (
            Action(email_id=email.id, action_type=action_type, response=response),
            str(reasoning.get("classification", "support")),
            str(reasoning.get("intent", "general_inquiry")),
            str(reasoning.get("risk", "low")),
            rationale,
        )


def _print_inbox_snapshot(observation: Observation, watch_sender: str = "") -> int:
    print("\n📥 Inbox Snapshot")
    print("-" * 108)
    print("Idx  ID      Priority  Type      Sender                           Subject")
    print("-" * 108)
    watch = watch_sender.lower().strip()
    watch_hits = 0
    for idx, item in enumerate(observation.inbox, start=1):
        sender = _safe_text(item.sender, 32)
        subject = _safe_text(item.subject, 50)
        marker = ""
        if watch and watch in item.sender.lower():
            marker = "  <-- MATCH"
            watch_hits += 1
        print(
            f"{idx:<4} {item.id:<7} {item.priority:<8}  {item.type:<8}  "
            f"{sender:<32} {subject}{marker}"
        )
    print("-" * 108)
    return watch_hits


def _select_next_email(observation: Observation) -> Optional[Email]:
    remaining = [email for email in observation.inbox if email.id not in set(observation.processed_email_ids)]
    if not remaining:
        return None
    # Prefer business value + priority; keep provider order as a final tie-breaker.
    remaining.sort(key=lambda item: (_value_rank(item), _priority_rank(item.priority)), reverse=True)
    return remaining[0]


def run_loop(
    provider: ProviderType,
    limit: int,
    max_steps: int,
    mode: str,
    disable_approval: bool,
    watch_sender: str,
    watch_only: bool,
) -> None:
    _load_env()

    if disable_approval:
        os.environ['APPROVAL_MODE'] = 'off'

    engine = ThreeAgentTriageEngine(SmartEmailAgentBrain())
    session = LiveEmailSession()
    observation = session.reset(provider, limit)

    print("\n" + "=" * 108)
    print("🚀 LIVE TRIAGE RUN")
    print("=" * 108)
    print(f"Provider      : {provider}")
    print(f"Mode          : {mode}")
    print(f"Emails fetched: {len(observation.inbox)}")
    if watch_sender:
        print(f"Watch sender  : {watch_sender}")

    watch_hits = _print_inbox_snapshot(observation, watch_sender)
    if watch_sender:
        if watch_hits:
            print(f"✅ Watch sender found in inbox: {watch_hits} match(es)")
        else:
            print("⚠️ Watch sender NOT found in fetched set (increase --limit or verify unread state).")
    print(f"Action Engine : {'LLM 3-agent pipeline' if engine.client else 'Heuristic fallback (no LLM credentials)'}")

    done = False
    step_num = 0
    spam_streak = 0
    applied_count = 0
    blocked_count = 0
    rewards: list[float] = []
    action_counts = {"reply": 0, "escalate": 0, "archive": 0, "mark_spam": 0}
    watch_processed = 0

    while not done and step_num < max_steps:
        step_num += 1

        email = None
        watch = watch_sender.lower().strip()
        if watch:
            for item in observation.inbox:
                if item.id in set(observation.processed_email_ids):
                    continue
                if watch in item.sender.lower():
                    email = item
                    break
        if email is None:
            email = _select_next_email(observation)
        if email is None:
            break

        action, classification, intent, risk, rationale = engine.build_action(email, mode)
        if action.action_type == 'mark_spam':
            spam_streak += 1
        else:
            spam_streak = 0

        if spam_streak >= 2:
            non_spam_remaining = [item for item in observation.inbox if item.id not in set(observation.processed_email_ids) and item.type not in {'spam', 'phishing'}]
            if non_spam_remaining:
                non_spam_remaining.sort(key=lambda item: (_value_rank(item), _priority_rank(item.priority)), reverse=True)
                email = non_spam_remaining[0]
                action, classification, intent, risk, rationale = engine.build_action(email, mode)
                spam_streak = 0
        observation, reward, done, info = session.step(action)
        rewards.append(reward.score)
        if info.get('applied'):
            applied_count += 1
        else:
            blocked_count += 1
        action_counts[action.action_type] = action_counts.get(action.action_type, 0) + 1
        if watch and watch in email.sender.lower():
            watch_processed += 1

        print("\n" + "-" * 108)
        print(f"STEP {step_num}/{max_steps}")
        print(f"Email   : {email.id} | {email.priority.upper()} | {email.type}")
        print(f"From    : {_safe_text(email.sender, 80)}")
        print(f"Subject : {_safe_text(email.subject, 95)}")
        print(f"Decision: class={classification} | intent={intent} | risk={risk} -> action={action.action_type.upper()}")
        print(f"Why     : {_safe_text(rationale, 100)}")
        print(
            f"Result  : applied={info.get('applied')} | approval_required={info.get('approval_required', False)} "
            f"| reward={reward.score:.4f} | done={done}"
        )

        if info.get('approval_required'):
            break
        if watch_only and watch_processed > 0:
            print("🛑 Watch-only mode: matched sender processed, stopping run.")
            break

    print("\n" + "=" * 108)
    print("✅ RUN SUMMARY")
    print("=" * 108)
    print(f"Steps run      : {step_num}")
    print(f"Session done   : {done}")
    print(f"Processed      : {len(observation.processed_email_ids)}")
    print(f"Applied/Blocked: {applied_count}/{blocked_count}")
    print(
        "Actions        : "
        f"reply={action_counts.get('reply', 0)} | "
        f"escalate={action_counts.get('escalate', 0)} | "
        f"archive={action_counts.get('archive', 0)} | "
        f"mark_spam={action_counts.get('mark_spam', 0)}"
    )
    if watch:
        print(f"Watch processed: {watch_processed}")
    print(f"Average reward : {(sum(rewards) / len(rewards)) if rewards else 0.0:.4f}")
    print("=" * 108 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description='OpenEnv-compliant live agent loop (reset -> step -> state progression).')
    parser.add_argument('--provider', default='imap', choices=['imap', 'gmail', 'graph'])
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--max-steps', type=int, default=10)
    parser.add_argument('--mode', choices=['full', 'spam-only'], default='full')
    parser.add_argument('--disable-approval', action='store_true')
    parser.add_argument('--watch-sender', default='', help='Highlight inbox entries whose sender contains this text')
    parser.add_argument('--watch-only', action='store_true', help='Process only first matching --watch-sender email and stop')
    args = parser.parse_args()

    run_loop(
        provider=args.provider,
        limit=args.limit,
        max_steps=args.max_steps,
        mode=args.mode,
        disable_approval=args.disable_approval,
        watch_sender=args.watch_sender,
        watch_only=args.watch_only,
    )


if __name__ == '__main__':
    main()
