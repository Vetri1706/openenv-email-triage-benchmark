import requests
import time

BASE_URL = "https://Vetri17-openenv-email-triage-benchmark.hf.space"


def safe_post(url, payload, retries=3):
    for i in range(retries):
        try:
            res = requests.post(url, json=payload, timeout=10)
            return res.json()
        except Exception as e:
            print(f"[Retry {i+1}] Error: {e}")
            time.sleep(1)
    return {}


def run_demo_case():
    print("\n=== RUNNING RL BENCHMARK DEMO ===")

    # RESET → get email
    res = safe_post(f"{BASE_URL}/reset", {"task_id": "easy"})
    obs = res.get("observation", {})

    if not obs.get("inbox"):
        print("No email found.")
        return

    email = obs["inbox"][0]
    email_id = email["id"]

    print(f"\nEmail: {email['subject']}")

    # ───────────── BASELINE ─────────────
    time.sleep(0.5)
    res_base = safe_post(f"{BASE_URL}/step", {
        "email_id": email_id,
        "action_type": "archive",
        "response": "N/A"
    })

    base_reward = res_base.get("reward", {}).get("score", 0.0)

    print("\n[BASELINE]")
    print("Action: archive")
    print("Reward:", base_reward)

    # RESET again
    time.sleep(0.5)
    res = safe_post(f"{BASE_URL}/reset", {"task_id": "easy"})
    obs = res.get("observation", {})

    if not obs.get("inbox"):
        print("Second reset failed.")
        return

    email = obs["inbox"][0]
    email_id = email["id"]

    # ───────────── AFTER ─────────────
    time.sleep(0.5)
    res_after = safe_post(f"{BASE_URL}/step", {
        "email_id": email_id,
        "action_type": "reply",
        "response": "Hi, we've reset your access. Please try again."
    })

    after_reward = res_after.get("reward", {}).get("score", 0.0)

    print("\n[IMPROVED]")
    print("Action: reply")
    print("Reward:", after_reward)

    # ───────────── RESULT ─────────────
    improvement = after_reward - base_reward

    print("\n=== RESULT ===")
    print(f"Improvement: {round(improvement, 4)}")


if __name__ == "__main__":
    run_demo_case()