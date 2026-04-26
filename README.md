---
title: EETRE - Enterprise Email Triage & Response Environment
emoji: 📧
colorFrom: blue
colorTo: green
sdk: docker
pinned: true
---

# EETRE — Enterprise Email Triage & Response Environment

> Trains an LLM agent to triage enterprise email through RL — not just classify, but act.

## 🔗 Links

| | |
|---|---|
| 🤗 HF Space | https://huggingface.co/spaces/Vetri17/openenv-email-triage-benchmark |
| 📓 Colab | https://colab.research.google.com/drive/1s7hBuQe93gA1yzKJ0_tcNauOEFeq4yEF?usp=sharing |
| 💻 GitHub | https://github.com/Vetri1706/openenv-email-triage-benchmark |
| 🎥 Video | https://youtu.be/ndwF3Rp_f2Q |
| 📝 Blog | https://huggingface.co/spaces/Vetri17/openenv-email-triage-benchmark/blob/main/Blog.md |

---

## One Line

EETRE turns inbox chaos into actionable workflows — an RL-trained
agent that reads, decides, and executes on real enterprise email.

---

## What It Does

| Action | What happens |
|---|---|
| reply | LLM generates contextual reply and sends via SMTP |
| escalate | Real Slack alert to #incidents or #security-alerts |
| archive | Filed silently, no noise |
| mark_spam | Sender blocked, no reply |

---

## 3-Agent Architecture
 Reasoning Agent
↓
 Decision Agent
↓
 Auditor Agent
↓
 Evaluator — reward returned to training loop
↓
 Execution — Slack / SMTP / block

 ---

## Training Results

![Training Results](https://raw.githubusercontent.com/Vetri1706/openenv-email-triage-benchmark/main/plots/eetre_training_results.png)
*SFT loss 37.5 to 18.1 | GRPO reward 0.608 to 0.833 over 96 steps*

![Reward Curve](https://raw.githubusercontent.com/Vetri1706/openenv-email-triage-benchmark/main/plots/eetre_reward_curve.png)
*Curriculum training: easy to medium to hard. Reward stays 0.8+ throughout.*

| Metric | Value |
|---|---|
| SFT loss reduction | 37.5 to 18.1 (51%) |
| GRPO reward improvement | 0.608 to 0.833 (37%) |
| Training steps | 96 |
| Avg trained reward | 0.836 |
| Data | 180 simulated + 11 live Gmail emails |
| Model | Qwen2.5-0.5B + LoRA r=16 via Unsloth |

---

## End-to-End in Action

### Real inbox chaos
![Mixed inbox](https://raw.githubusercontent.com/Vetri1706/openenv-email-triage-benchmark/main/proofs/spam_where_sent_because_of_bulk.png)
*Spam, notifications, and critical emails all mixed together*

### Critical incident detected
![Production email](https://raw.githubusercontent.com/Vetri1706/openenv-email-triage-benchmark/main/proofs/Test_mail_for_slack.png)
*Production issue email flagged for immediate attention*

### Intelligent Slack escalation
![Slack output](https://raw.githubusercontent.com/Vetri1706/openenv-email-triage-benchmark/main/proofs/slack_output.png)
*Agent escalates to Slack with full context — not a generic ping*

### Context-aware reply
![Automated reply](https://raw.githubusercontent.com/Vetri1706/openenv-email-triage-benchmark/main/proofs/reply_message_automated.png)
*LLM generates a meaningful specific reply — not a template*

### External validation
![NextToken benchmark](https://raw.githubusercontent.com/Vetri1706/openenv-email-triage-benchmark/main/proofs/nexttoken_output.png)
*Ex-Google ML engineer independently benchmarked 5 frontier models on EETRE*

After publishing, Nitish Kulkarni — ex-Google ML engineer building
NextToken — independently found our repo and benchmarked 5 frontier
models against EETRE without being asked:

- claude-3-5-sonnet
- gpt-4o
- gemini-1.5-pro
- gpt-4o-mini
- llama-3-70b

**Average accuracy: 82%**

---

## Why RL?

Rule-based filters are static. They break on anything new.

EETRE uses a full RL pipeline:

**SFT first** — trained on reward-filtered real Gmail + simulated
curriculum (easy / medium / hard) to give the model a warm start.

**Then GRPO** — Group Relative Policy Optimization via HF TRL +
Unsloth. The live environment is the verifier. Agent generates
actions, environment scores them, policy updates toward higher reward.

The reward signal is multi-component — not just 0 or 1:
- Correctness score from environment grader
- Anti-repetition penalty
- Auditor validation signal
- Format compliance check

This prevents the agent from gaming a single metric.

---

## Safety Design

- Phishing and spam replies blocked at inference time
- Heavy penalty in live mode if spam is replied to
- Auditor agent validates every decision before execution
- Approval mode: ON for human-in-the-loop, OFF to trust the agent

---

## How Emails Are Sourced

- IMAP — pull and push on real inbox, archive, spam folders
- Gmail — access token + user ID
- Simulated — curriculum tasks easy / medium / hard

---

## Quick Start

```bash
# Reset environment
curl -X POST \
  https://Vetri17-openenv-email-triage-benchmark.hf.space/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "medium"}'

# Step with action
curl -X POST \
  https://Vetri17-openenv-email-triage-benchmark.hf.space/step \
  -H "Content-Type: application/json" \
  -d '{"email_id": "E-MED-001", "action_type": "escalate", "response": ""}'

# Get state
curl https://Vetri17-openenv-email-triage-benchmark.hf.space/state
```

---

📖 Full story and writeup: [Blog.md](https://huggingface.co/spaces/Vetri17/openenv-email-triage-benchmark/blob/main/Blog.md)
