# EETRE — How I Built an RL Environment for Enterprise Email Triage

## The Problem

I was drowning in emails. Spam, production alerts, newsletters,
phishing — all mixed together. I kept missing the ones that
actually mattered.

I thought: what if an AI agent could not just read emails,
but decide what to DO with them — and actually do it?

That's EETRE.

## What I Built

EETRE is an OpenEnv-compliant RL environment where an LLM
agent learns to triage enterprise emails through reinforcement
learning. It doesn't just classify — it executes.

The agent can:
- `reply` — generate a contextual LLM response and send it
- `escalate` — fire a real Slack alert to your team
- `archive` — silently file low-priority mail
- `mark_spam` — block the sender

## The Multi-Agent System

I designed 3 agents working together:

**Reasoning Agent** — reads the email and detects signals.
Is this phishing? Is it urgent? Is it a newsletter?

**Decision Agent** — picks one action based on reasoning.

**Auditor Agent** — validates the decision. If the reasoning
agent missed a phishing signal and decision agent says reply,
auditor blocks it and penalizes the reward.

This separation means the system is interpretable — you can
see exactly why each decision was made.

## Why Reinforcement Learning?

Rule-based filters are static. They can't adapt.

I wanted the agent to *discover* the right action through
experience. So I built:

**SFT first** — trained on reward-filtered real emails from
my own Gmail + simulated curriculum tasks. This gives the
model a warm start so RL doesn't stall.

**Then GRPO** — Group Relative Policy Optimization via HF TRL
+ Unsloth. The live environment acts as the verifier. Agent
generates actions, environment scores them, policy updates.

The reward signal is multi-component — not just 0/1:
- Correctness score
- Anti-repetition penalty
- Auditor validation bonus
- Format compliance

This prevents reward hacking.

## Training Results

| Metric | Value |
|---|---|
| SFT loss | 37.5 → 18.1 (51% reduction) |
| GRPO reward | 0.608 → 0.833 (37% improvement) |
| Training steps | 96 |
| Avg trained reward | 0.836 |
| Data | 180 simulated + 11 live Gmail emails |
| Model | Qwen2.5-0.5B + LoRA r=16, Unsloth 2x faster |

## The Slack Integration

The moment I saw a live Slack alert fire from an email the
agent had just read and escalated — I knew this could
integrate with anything.

Spam gets blocked silently. Support requests get smart LLM
replies via SMTP. Production incidents go straight to
#incidents on Slack. Security alerts go to #security-alerts.

No generic pings. Structured, contextual alerts.

## External Validation

After publishing, Nitish Kulkarni — ex-Google ML engineer
building NextToken — independently found our repo and
benchmarked 5 frontier models against EETRE:

- claude-3-5-sonnet → highest accuracy
- gpt-4o
- gemini-1.5-pro
- gpt-4o-mini
- llama-3-70b

Average accuracy: **82%** — without any training on our data.
We didn't ask for this. He found it on his own.

## What I Learned

Building the reward function was the hardest part. A naive
single reward signal gets gamed immediately — the agent just
picks the most common action and gets decent scores without
actually learning. Multiple independent reward components
fixed this.

Training on my own real emails made a huge difference. The
model learned patterns that simulated data couldn't capture
— like how Nigerian prince spam looks different from
legitimate urgent emails even when both use urgent language.

## Try It

```bash
curl -X POST \
  https://Vetri17-openenv-email-triage-benchmark.hf.space/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "medium"}'
```

## Links
- HF Space: https://huggingface.co/spaces/Vetri17/openenv-email-triage-benchmark
- Colab: https://colab.research.google.com/drive/1s7hBuQe93gA1yzKJ0_tcNauOEFeq4yEF?usp=sharing
- GitHub: https://github.com/Vetri1706/openenv-email-triage-benchmark
- Demo Video: https://youtu.be/ndwF3Rp_f2Q
