"""Minimal Gradio UI for the EETRE OpenEnv environment.

Designed for HF Space judges:
- Click "Run Episode" -> watch the agent process emails live.
- Each cycle prints: Reset -> Email -> Reasoning -> Decision -> Reward -> Next.
- Talks to the OpenEnv-compliant FastAPI endpoints (`/reset`, `/step`, `/health`)
  so the UI itself is just another OpenEnv client.

Mounted at `/ui` by `app.py`.
"""

from __future__ import annotations

import os
import time
from typing import Generator, List

import gradio as gr
import requests


BASE_URL = os.environ.get("EETRE_BASE_URL", "http://localhost:7860")
PUBLIC_URL = "https://Vetri17-openenv-email-triage-benchmark.hf.space"

VALID_ACTIONS = ["mark_spam", "escalate", "reply", "archive"]

PHISHING_KEYWORDS = ("credentials", "click now", "click here", "prize", "gift", "winner", "lottery")
TECHNICAL_KEYWORDS = ("timeout", "failed", "error", "production", "down", "outage", "5xx")
NEWSLETTER_KEYWORDS = ("unsubscribe", "digest", "newsletter", "weekly", "subscribe")
SECURITY_KEYWORDS = ("oauth", "security", "suspicious", "unusual", "breach", "mfa")


def _decide_action(email: dict) -> str:
    body = (email.get("body") or "").lower()
    subject = (email.get("subject") or "").lower()
    text = f"{subject} {body}"

    if any(w in text for w in PHISHING_KEYWORDS):
        return "mark_spam"
    if any(w in text for w in TECHNICAL_KEYWORDS):
        return "reply"
    if any(w in text for w in NEWSLETTER_KEYWORDS):
        return "archive"
    if any(w in text for w in SECURITY_KEYWORDS):
        return "escalate"
    if email.get("priority") in ("high", "critical"):
        return "escalate"
    return "reply"


def _reasoning_signals(email: dict) -> List[str]:
    body = (email.get("body") or "").lower()
    subject = (email.get("subject") or "").lower()
    text = f"{subject} {body}"

    signals: List[str] = []
    if any(w in text for w in PHISHING_KEYWORDS):
        signals.append("phishing signal detected")
    if any(w in text for w in TECHNICAL_KEYWORDS):
        signals.append("technical issue detected")
    if any(w in text for w in NEWSLETTER_KEYWORDS):
        signals.append("newsletter / low priority")
    if any(w in text for w in SECURITY_KEYWORDS):
        signals.append("security alert detected")
    if email.get("priority") in ("high", "critical"):
        signals.append(f"priority={email.get('priority')}")
    if not signals:
        signals.append("standard email")
    return signals


def check_health() -> str:
    try:
        res = requests.get(f"{BASE_URL}/health", timeout=10).json()
        return f"OK  -  environment status: {res.get('status', 'unknown')}  ({BASE_URL})"
    except Exception as exc:
        return f"OFFLINE  -  {exc}"


def run_episode(task_id: str, pacing: float) -> Generator[str, None, None]:
    """Stream the episode line-by-line so judges see it run live."""

    pacing = max(0.0, min(float(pacing or 0.0), 2.0))
    logs: List[str] = []

    def push(line: str = "") -> str:
        logs.append(line)
        return "\n".join(logs)

    yield push("=" * 60)
    yield push(f"TASK: {task_id.upper()}")
    yield push("=" * 60)
    yield push("")

    try:
        res = requests.post(
            f"{BASE_URL}/reset",
            json={"task_id": task_id},
            timeout=20,
        ).json()
        obs = res["observation"]
    except Exception as exc:
        yield push(f"Reset failed: {exc}")
        return

    yield push(f"Objective : {obs.get('objective', '')}")
    yield push(f"Difficulty: {obs.get('difficulty', task_id)}")
    yield push(f"Inbox size: {len(obs.get('inbox', []))}")
    yield push(f"Max steps : {obs.get('max_steps', '?')}")
    yield push("-" * 60)

    total_reward = 0.0
    inbox = obs.get("inbox", [])

    for idx, email in enumerate(inbox, start=1):
        if pacing:
            time.sleep(pacing)
        yield push("")
        yield push(f"[{idx}/{len(inbox)}] EMAIL")
        yield push(f"   id      : {email.get('id')}")
        yield push(f"   from    : {email.get('sender', '')}")
        yield push(f"   subject : {email.get('subject', '')}")
        yield push(f"   priority: {email.get('priority', 'normal')}")
        body_preview = (email.get("body") or "").replace("\n", " ")[:140]
        yield push(f"   body    : {body_preview}...")

        if pacing:
            time.sleep(pacing)
        yield push("")
        yield push("   REASONING AGENT")
        for signal in _reasoning_signals(email):
            yield push(f"      -> {signal}")

        action = _decide_action(email)
        if pacing:
            time.sleep(pacing)
        yield push("")
        yield push(f"   DECISION AGENT: {action.upper()}")

        try:
            step_res = requests.post(
                f"{BASE_URL}/step",
                json={
                    "email_id": email["id"],
                    "action_type": action,
                    "response": "Automated response",
                },
                timeout=20,
            ).json()
            reward = step_res.get("reward", {}) or {}
            score = float(reward.get("score", 0.0) or 0.0)
            total_reward += score

            yield push("")
            yield push("   EVALUATOR AGENT")
            yield push(f"      score   : {score:.3f}")
            yield push(f"      correct : {reward.get('action_correctness', 0.0):.3f}")
            yield push(f"      quality : {reward.get('response_quality', 0.0):.3f}")
            feedback = reward.get("feedback")
            if feedback:
                yield push(f"      note    : {feedback}")
            yield push(f"      done    : {step_res.get('done', False)}")

            if step_res.get("done"):
                yield push("")
                yield push("   environment signalled DONE")
                yield push("-" * 60)
                break
        except Exception as exc:
            yield push(f"   step error: {exc}")

        yield push("-" * 60)

    avg = total_reward / max(len(inbox), 1)
    yield push("")
    yield push("=" * 60)
    yield push("EPISODE COMPLETE")
    yield push(f"  emails processed : {len(inbox)}")
    yield push(f"  total reward     : {total_reward:.3f}")
    yield push(f"  avg reward       : {avg:.3f}")
    yield push("=" * 60)


with gr.Blocks(title="EETRE - Email Triage RL Environment") as demo:
    gr.Markdown(
        """
        # EETRE - Enterprise Email Triage & Response Environment
        **OpenEnv-compliant RL environment** &middot; 3-Agent System &middot; Live Slack/SMTP Integration

        | | |
        |---|---|
        | HF Space | https://huggingface.co/spaces/Vetri17/openenv-email-triage-benchmark |
        | Colab    | https://colab.research.google.com/drive/1s7hBuQe93gA1yzKJ0_tcNauOEFeq4yEF |
        | GitHub   | https://github.com/Vetri1706/openenv-email-triage-benchmark |
        | Blog     | See `Blog.md` in the Space repo |

        Endpoints exercised by this UI: `POST /reset`, `POST /step`, `GET /health`.
        """
    )

    gr.Markdown("---")

    with gr.Row():
        health_btn = gr.Button("Check environment health", variant="secondary")
        health_out = gr.Textbox(label="Status", lines=1, interactive=False)
    health_btn.click(check_health, outputs=health_out)

    gr.Markdown("---")
    gr.Markdown("## Run Episode")
    gr.Markdown(
        "Pick a task, then watch the 3-agent loop process each email in real time. "
        "Every cycle prints the email, reasoning, decision, and reward — exactly what "
        "the environment returns over `/reset` and `/step`."
    )

    with gr.Row():
        task_dropdown = gr.Dropdown(
            choices=["easy", "medium", "hard"],
            value="medium",
            label="Task difficulty",
            info="easy = basic support  |  medium = mixed inbox  |  hard = phishing + escalation",
        )
        pacing_slider = gr.Slider(
            minimum=0.0,
            maximum=1.5,
            value=0.4,
            step=0.1,
            label="Pacing (seconds between agent steps)",
            info="Set to 0 for max speed; ~0.4s reads nicely for a live demo.",
        )
        run_btn = gr.Button("Run episode", variant="primary", scale=2)

    logs_output = gr.Textbox(
        label="Live agent logs",
        lines=32,
        max_lines=60,
        placeholder="Click 'Run episode' to see the agent process emails in real time...",
    )

    run_btn.click(
        fn=run_episode,
        inputs=[task_dropdown, pacing_slider],
        outputs=logs_output,
    )

    gr.Markdown("---")
    gr.Markdown(
        """
        ## Training Results
        - SFT Loss: 37.5 -> 18.1 (51% reduction)
        - GRPO Reward: 0.608 -> 0.833 (37% improvement)
        - Model: Qwen2.5-0.5B + LoRA r=16 via Unsloth
        - Data: 180 simulated + 11 live Gmail emails

        ## Architecture
        ```
        Reasoning Agent -> Decision Agent -> Auditor -> Evaluator -> Slack/SMTP
        ```
        """
    )


if __name__ == "__main__":
    demo.launch()
