
import email
import requests
import smtplib
import os
from email.mime.text import MIMEText

# 🔐 PUT YOUR NEW SLACK WEBHOOK HERE (old one may be revoked)
# Use .env-based webhook configuration for safety and portability.
SLACK_WEBHOOK = (
    os.getenv("ESCALATION_WEBHOOK_URL")
    or os.getenv("SLACK_WEBHOOK")
    or ""
)

BASE_URL = "https://Vetri17-openenv-email-triage-benchmark.hf.space"


# =========================
# 🔔 SLACK NOTIFICATION
# =========================
def notify_slack(email, action, reward_score, reasoning, response):
    """Send Slack alert with full debug"""

    if not SLACK_WEBHOOK:
        print("   ⚠️ Slack webhook not configured (ESCALATION_WEBHOOK_URL/SLACK_WEBHOOK).")
        return "⏭️ Slack skipped"

    emoji = {
        "mark_spam": "🚫",
        "escalate": "🚨",
        "reply": "✅",
        "archive": "📁"
    }.get(action, "📧")

    if action == "escalate":
        top_signal = reasoning.get("signals", ["no signal"])[0]
        intent = reasoning.get("intent", "general").replace("_", " ").title()
        message = (
            f"🚨 *EETRE ALERT*\n"
            f"From: {email['sender']}\n"
            f"Subject: {email['subject']}\n\n"
            f"Intent: {intent}\n"
            f"Decision: {action.upper()}\n"
            f"Signal: {top_signal}\n\n"
            f"System Response: {response}\n"
            f"Score: {reward_score:.3f}"
        )

    elif action == "mark_spam":
        message = (
            f"🚫 *EETRE SPAM BLOCKED*\n"
            f"*From:* {email['sender']}\n"
            f"*Subject:* {email['subject']}\n"
            f"*Sender blocked automatically*\n"
            f"*Confidence:* {reward_score:.3f}"
        )

    elif action == "reply":
        message = (
            f"✅ *EETRE AUTO-REPLY SENT*\n"
            f"*To:* {email['sender']}\n"
            f"*Subject:* Re: {email['subject']}\n"
            f"*Status:* Reply dispatched automatically\n"
            f"*Score:* {reward_score:.3f}"
        )

    else:
        message = (
            f"📁 *EETRE ARCHIVED*\n"
            f"*Subject:* {email['subject']}\n"
            f"*Reason:* Low priority\n"
            f"*Score:* {reward_score:.3f}"
        )

    try:
        res = requests.post(SLACK_WEBHOOK, json={"text": message})

        print(f"   🔎 Slack status: {res.status_code}")
        print(f"   🔎 Slack response: {res.text}")

        return f"{emoji} Slack notified"

    except Exception as e:
        print(f"   ❌ Slack error: {str(e)}")
        return f"{emoji} Slack failed"


# =========================
# 🧠 REASONING AGENT
# =========================
def reasoning_agent(email: dict) -> dict:
    signals = []
    body = email.get("body", "").lower()
    priority = str(email.get("priority", "")).lower()

    if any(w in body for w in ["credentials", "click now", "prize", "gift"]):
        signals.append("phishing signal: credential harvesting language")

    if any(w in body for w in ["timeout", "failed", "error", "production"]):
        signals.append("technical issue: production system affected")

    if any(w in body for w in ["unsubscribe", "digest", "newsletter"]):
        signals.append("low priority: newsletter/digest content")

    if email.get("priority") == "high":
        signals.append("high priority flag from sender")

    intent = "general"
    if any(w in body for w in ["credentials", "click now", "prize", "gift"]):
        intent = "phishing"
    elif any(w in body for w in ["timeout", "failed", "error", "production"]):
        intent = "production_issue"
    elif any(w in body for w in ["unsubscribe", "digest", "newsletter"]):
        intent = "newsletter"
    elif priority == "high":
        intent = "security_alert"

    if not signals:
        signals.append("no strong signals — defaulting to context")

    return {
        "signals": signals,
        "intent": intent,
        "confidence": len(signals) * 0.25
    }


# =========================
# ⚡ DECISION AGENT
# =========================
def decision_agent(email: dict, reasoning: dict) -> str:
    intent = reasoning.get("intent", "general")

    if intent == "phishing":
        return "mark_spam"

    if intent == "production_issue":
        return "escalate"

    if intent == "security_alert":
        return "escalate"

    if intent == "newsletter":
        return "archive"

    return "reply"


def generate_response(email, reasoning, action):
    intent = reasoning.get("intent", "general")

    if action == "escalate":
        if intent == "production_issue":
            return "Production failure detected. Engineering team has been notified for immediate investigation."
        if intent == "security_alert":
            return "Security alert identified. Escalated for policy review and risk assessment."
        if intent == "phishing":
            return "Suspicious email detected and escalated for security review."
        return "Critical issue detected and escalated."
    if action == "reply":
        return "Acknowledged. Our team is reviewing your request and will respond shortly."
    if action == "mark_spam":
        return "Email classified as phishing and blocked automatically."
    if action == "archive":
        return "No action required."
    return "No action required."


# =========================
# 🚀 MAIN LOOP
# =========================
def run_multi_agent_episode(task="medium"):

    obs = requests.post(
        f"{BASE_URL}/reset",
        json={"task_id": task}
    ).json()["observation"]

    print(f"\n{'='*60}")
    print(f"TASK: {obs['objective']}")
    print(f"{'='*60}")

    results = []

    for email in obs["inbox"]:
        print(f"\n📧 EMAIL: {email['subject']}")
        print(f"   From: {email['sender']}")

        # 🧠 Reasoning
        reasoning = reasoning_agent(email)
        print(f"\n🧠 REASONING AGENT:")
        for s in reasoning["signals"]:
            print(f"   → {s}")

        # ⚡ Decision
        action = decision_agent(email, reasoning)
        print(f"\n⚡ DECISION AGENT: {action.upper()}")
        response = generate_response(email, reasoning, action)

        # 🎯 Environment step
        result = requests.post(
            f"{BASE_URL}/step",
            json={
                "email_id": email["id"],
                "action_type": action,
                "response": response
            }
        ).json()

        # ✅ FIXED: reward before usage
        reward = result["reward"]

        # 🔔 Notify Slack only for escalations
        if action == "escalate":
            execution = notify_slack(
                email,
                action,
                reward.get("score", 0),
                reasoning,
                response
            )
        else:
            execution = "⏭️ No notification"

        print(f"\n📡 EXECUTION: {execution}")

        print(f"\n✅ EVALUATOR AGENT:")
        print(f"   Score:  {reward.get('score', 0):.3f}")
        print(f"   Reason: {reward.get('reason', 'N/A')}")

        results.append({
            "email": email["subject"],
            "signals": reasoning["signals"],
            "intent": reasoning["intent"],
            "action": action,
            "response": response,
            "reward": reward.get("score", 0)
        })

    avg = sum(r["reward"] for r in results) / len(results)

    print(f"\n{'='*60}")
    print(f"EPISODE SUMMARY")
    print(f"  Emails processed: {len(results)}")
    print(f"  Avg reward:       {avg:.3f}")
    print(f"{'='*60}\n")

    return results


# =========================
# ▶ RUN
# =========================
if __name__ == "__main__":
    run_multi_agent_episode("medium")
