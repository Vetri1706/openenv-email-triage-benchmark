
import requests

BASE_URL = "https://Vetri17-openenv-email-triage-benchmark.hf.space"

def reasoning_agent(email: dict) -> dict:
    """Agent 3 — explains signals before decision"""
    signals = []
    body = email.get("body", "").lower()
    subject = email.get("subject", "").lower()
    
    if any(w in body for w in ["credentials", "click now", "prize", "gift"]):
        signals.append("phishing signal: credential harvesting language")
    if any(w in body for w in ["timeout", "failed", "error", "production"]):
        signals.append("technical issue: production system affected")
    if any(w in body for w in ["unsubscribe", "digest", "newsletter"]):
        signals.append("low priority: newsletter/digest content")
    if email.get("priority") == "high":
        signals.append("high priority flag from sender")
    if not signals:
        signals.append("no strong signals — defaulting to context")
    
    return {"signals": signals, "confidence": len(signals) * 0.25}

def decision_agent(email: dict, reasoning: dict) -> str:
    signals = " ".join(reasoning["signals"])
    
    if "phishing" in signals:
        return "mark_spam"
    if "technical issue" in signals:
        return "reply"        # ← change escalate to reply
    if "newsletter" in signals:
        return "archive"
    if "high priority" in signals:
        return "escalate"
    return "reply"

def run_multi_agent_episode(task="medium"):
    """Full 3-agent loop with visible output"""
    
    # Reset environment
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
        
        # Agent 3 — Reasoning
        reasoning = reasoning_agent(email)
        print(f"\n🧠 REASONING AGENT:")
        for s in reasoning["signals"]:
            print(f"   → {s}")
        
        # Agent 1 — Decision
        action = decision_agent(email, reasoning)
        print(f"\n⚡ DECISION AGENT: {action.upper()}")
        
        # Agent 2 — Evaluator (your env's reward)
        result = requests.post(
            f"{BASE_URL}/step",
            json={
                "email_id":    email["id"],
                "action_type": action,
                "response":    f"Automated: {reasoning['signals'][0]}"
            }
        ).json()
        
        reward = result["reward"]
        print(f"\n✅ EVALUATOR AGENT:")
        print(f"   Score:  {reward.get('score', 0):.3f}")
        print(f"   Reason: {reward.get('reason', 'N/A')}")
        
        results.append({
            "email":    email["subject"],
            "signals":  reasoning["signals"],
            "action":   action,
            "reward":   reward.get("score", 0)
        })
    
    # Summary
    avg = sum(r["reward"] for r in results) / len(results)
    print(f"\n{'='*60}")
    print(f"EPISODE SUMMARY")
    print(f"  Emails processed: {len(results)}")
    print(f"  Avg reward:       {avg:.3f}")
    print(f"{'='*60}\n")
    
    return results

if __name__ == "__main__":
    run_multi_agent_episode("medium")