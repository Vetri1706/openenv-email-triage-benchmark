# Enterprise Email Triage & Response Environment (EETRE)

Live demo: https://Vetri17-openenv-email-triage-benchmark.hf.space

EETRE is a production-style OpenEnv environment for enterprise email triage. It lets agents read inbox messages, classify intent, decide the right workflow action, and write a professional reply when needed.

## What this environment does

The environment simulates the core work performed by support, security, billing, HR, and operations teams:

- classify incoming emails
- detect spam, phishing, internal requests, billing issues, and support tickets
- choose one action per message: `reply`, `escalate`, `archive`, or `mark_spam`
- generate a useful reply when a response is required
- score the agent with a bounded reward in the range `[0.0, 1.0]`

It works in two main ways:

- **Simulated benchmark mode**: deterministic task episodes for evaluation
- **Live mailbox mode**: connects to IMAP, Gmail, or Microsoft Graph and triages a real inbox

There is also a **human-in-the-loop approval mode** for live actions that should not run automatically.

## Real-World Motivation

Enterprise support, security, billing, and internal operations teams process high volumes of email with strict SLAs. Automation quality directly affects customer trust, incident response speed, and risk containment. EETRE evaluates whether an AI agent can execute this workflow safely, consistently, and with enough nuance to handle ambiguous inboxes.

## How the full system works

1. Load a task or live mailbox.
2. Read the observation payload.
3. Pick the next email to process.
4. Decide one action.
5. Send the action to the environment.
6. Receive the updated observation, reward, and done flag.
7. Repeat until the episode finishes.

This same loop is used by:

- the baseline runner in `inference.py`
- the live loop in `live_agent_loop.py`
- the reusable adapter in `agent_adapter.py`

The environment is therefore plug-and-play for other agents that can make HTTP requests.

## Observation Space

`Observation` includes:
- `task_id`, `objective`, `difficulty`
- `inbox`: list of emails with `id`, `sender`, `subject`, `body`, `priority`, `type`
- `processed_email_ids`
- `available_actions`
- `step_count`, `max_steps`

Each email in the inbox is structured so agents can reason over:

- sender identity
- subject and body text
- priority level
- coarse message type

That makes the environment suitable for classification, planning, response generation, and safety testing.

## Action Space

`Action` schema:
- `email_id`: target message
- `action_type`: one of `reply`, `escalate`, `archive`, `mark_spam`
- `response` (optional): required for reply-focused expectations

## Reward & Grading

`step()` returns `(observation, reward, done, info)` where:
- `reward.score` is always normalized to `[0.0, 1.0]`
- Grader evaluates three dimensions:
  - Action correctness (expected operation per email)
  - Response quality (keyword coverage + minimum response quality)
  - Efficiency (fewer steps scores higher)
- Penalties apply for:
  - Wrong actions
  - Repeated actions
  - Re-processing completed emails
  - Missing required reply text
- Controlled stochastic reward noise is applied with bounded amplitude (default ±0.04) to prevent zero-variance collapse while preserving policy ranking.
- Some emails allow alternative valid actions with slightly different scores to support multiple realistic strategies.
- Episode-level efficiency bonus is added when all emails are solved early.

The score is designed to reward correct decisions, good replies, and efficient handling while still exposing enough variation to compare different agents.

## Tasks (Easy → Hard)

1. **easy**: single support email with clear expected reply.
2. **medium**: mixed inbox with spam + production support + bulk digest requiring archive (anti-shortcut).
3. **hard**: phishing + urgent internal escalation + billing reply dependency + low-value bulk traffic.
4. **killer**: threaded meeting scheduling conflict with alternative slots, priority handling, and escalation.

All tasks have primary expected outcomes in `env/tasks.py`, with selected ambiguous cases permitting alternative valid actions.

## Task coverage summary

| Task | Skill tested |
|---|---|
| easy | basic support reply |
| medium | spam filtering and support triage |
| hard | security, billing, escalation, and dependency handling |
| killer | scheduling conflict resolution, thread memory, and trade-offs |

```text
openenv-email-triage/
├── env/
│   ├── __init__.py
│   ├── environment.py
│   ├── models.py
│   ├── tasks.py
│   ├── grader.py
│   └── data.py
├── inference.py
├── openenv.yaml
├── Dockerfile
├── requirements.txt
├── README.md
└── app.py
```

## Setup (Local)

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Fill in your local mail credentials and baseline settings in `.env`.

3. Start the app:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 7860
```

You can also run the app with `python app.py` if you prefer a direct entrypoint.

## Project metadata and packaging

This repository includes a required [pyproject.toml](pyproject.toml) file for packaging, dependency management, and evaluator compatibility.

Use it to install the project in editable mode during development:

```bash
pip install -e .
```

This keeps the package metadata, dependencies, and console entrypoints aligned for local runs, Docker builds, and benchmark agents.

## Quick start

### 1) Simulated benchmark

```bash
python inference.py
```

This runs the benchmark tasks and prints `[START]`, `[STEP]`, and `[END]` logs.

### 2) Live mailbox triage

```bash
export MODE=live
export ENV_API_URL=http://127.0.0.1:7860
export LIVE_PROVIDER=imap
python inference.py
```

### 3) Use the adapter directly

```bash
python agent_adapter.py
```

or from Python:

```python
from agent_adapter import OpenEnvAgentAdapter

agent = OpenEnvAgentAdapter(mode="simulated")
agent.run_episode(task_id="hard")
```

For live IMAP/SMTP mode, the app reads these environment variables from your shell or `.env` file:

- `IMAP_HOST`
- `IMAP_PORT`
- `IMAP_USERNAME`
- `IMAP_PASSWORD`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`

## Web Dashboard UI

### Access the UI

Once the FastAPI app is running, open your browser:

```
http://localhost:8000
```

You'll see a clean, two-column dashboard for interactive environment control.

### Dashboard Features

**Left Panel:**
- **Task Selector**: Choose between `easy`, `medium`, `hard`, or `killer` tasks
- **Reset Button**: Initialize a new episode
- **Inbox List**: All available emails with priority, sender, and subject
- **Email Selection**: Click an email to select it
- **Action Form**: 
  - Select action type: `reply`, `escalate`, `archive`, `mark_spam`
  - Optional response text (for reply actions)
  - Submit button to execute the action

**Right Panel:**
- **Status Display**: Current step count, cumulative reward, and done status
- **Observation Display**: Pretty-printed JSON of the current environment state
- **Action History**: Timestamped log of all actions taken in the episode

### Workflow Example

1. Select task (e.g., "medium") and click **Reset Environment**
2. Inbox populates with emails; select one by clicking it
3. Choose an action (e.g., "reply") and optionally write a response
4. Click **Submit Action** to step the environment
5. Observation, reward, and history update automatically
6. Repeat until done status shows ✓

### Browser Compatibility

Works in all modern browsers (Chrome, Firefox, Safari, Edge). No build tools or external dependencies required — pure HTML + CSS + vanilla JavaScript.

## API Endpoints

- `GET /health`
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /dashboard`
- `GET /tasks`
- `POST /live/reset`
- `POST /live/step`
- `GET /live/state`
- `GET /live/dashboard`

### Reset example

```bash
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy"}'
```

### Live inbox reset example

```bash
curl -X POST http://localhost:7860/live/reset \
  -H "Content-Type: application/json" \
  -d '{"provider": "imap", "limit": 10}'
```

### Live inbox step example

```bash
curl -X POST http://localhost:7860/live/step \
  -H "Content-Type: application/json" \
  -d '{
    "email_id": "12345",
    "action_type": "reply",
    "response": "We are investigating and will update shortly."
  }'
```

## Live Provider Configuration

The app supports three live providers and maps incoming messages into the same `Email` schema.

- `imap` pull + push actions:
  - Required secrets: `IMAP_HOST`, `IMAP_PORT`, `IMAP_USERNAME`, `IMAP_PASSWORD`
  - Optional SMTP secrets for reply: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
  - Optional folders: `IMAP_MAILBOX`, `IMAP_SPAM_MAILBOX`, `IMAP_ARCHIVE_MAILBOX`
- `gmail` API pull + labels:
  - Required secret: `GMAIL_ACCESS_TOKEN`
  - Optional: `GMAIL_USER_ID` (default `me`)
- `graph` (Microsoft 365) pull + actions:
  - Required secret: `GRAPH_ACCESS_TOKEN`
  - Optional: `GRAPH_USER` (default `me`)

Escalation ticketing is sent to `ESCALATION_WEBHOOK_URL` when configured.

For Hugging Face Space deployment, set all credentials as Space Secrets; do not commit keys to the repository.

## Human-in-the-loop mode

There is no separate `/human` endpoint. Human review is controlled by approval mode in the live environment.

Enable it with:

```bash
APPROVAL_MODE=required
APPROVAL_ACTIONS=reply,escalate
APPROVAL_RISK_LEVELS=critical,high
```

When enabled:

- live actions that match those rules return `approval_required=true`
- the environment does not execute the action automatically
- the calling agent can pause and wait for a human decision

This is the intended human method for safe operational use.

## Baseline Inference

`inference.py` uses the OpenAI Python client and reads:
- `MODE` (`simulated` or `live`, default `simulated`)
- `API_BASE_URL` (default: `https://openrouter.ai/api/v1`)
- `MODEL_NAME` (default: `nvidia/nemotron-3-super-120b-a12b:free`)
- `OPENAI_API_KEY` (required; `HF_TOKEN` is also accepted for compatibility)
- `BACKUP_MODEL` (default: `meta-llama/llama-3-8b-instruct:free`)
- `ENV_API_URL` (live mode only; default `http://127.0.0.1:7860`)
- `LIVE_PROVIDER` (live mode only; default `imap`)
- `LIVE_LIMIT` (live mode only)
- `LIVE_MAX_STEPS` (live mode only)

Run:

```bash
export OPENAI_API_KEY="your-openrouter-key"
export API_BASE_URL="https://openrouter.ai/api/v1"
export MODEL_NAME="nvidia/nemotron-3-super-120b-a12b:free"
export MODE="simulated"
python inference.py
```

Live mode run:

```bash
export MODE="live"
export ENV_API_URL="http://127.0.0.1:7860"
export LIVE_PROVIDER="imap"
python inference.py
```

If you want the agent to pause for human approval on important mail, keep `APPROVAL_MODE=required` in your environment.

Logs are emitted in strict tagged format only:
- `[START] ...`
- `[STEP] ...`
- `[END] ...`

`[STEP]` logs include a decision trace for judges:
- `classification`
- `risk`
- `reasoning`
- `decision_path`

## Smart Agent Brain

The agent now applies a deterministic decision pipeline per email:
1. classify email type (`support`, `billing`, `internal`, `spam`, `phishing`)
2. estimate risk (`low` → `critical`)
3. choose workflow action (`reply`, `escalate`, `archive`, `mark_spam`)
4. generate a policy-aligned reply when action is `reply`

This logic is implemented in `env/agent_brain.py`.

## Reusable agent integration

`agent_adapter.py` is a drop-in HTTP adapter for other agents or model stacks.

It supports:

- simulated mode: `/reset` and `/step`
- live mode: `/live/reset` and `/live/step`
- LLM-based decisions with OpenAI-compatible APIs
- heuristic fallback when no API key is available
- optional planner mode for better task ordering

This makes the environment easy to plug into custom planners, RL agents, or benchmark harnesses.

## Safety Layer

- In inference: replies to suspicious (`spam`/`phishing`) emails are blocked and auto-routed to `mark_spam`.
- In live server mode: `LiveEmailSession.step()` rejects unsafe reply actions to suspicious emails with penalty feedback.
- No-reply or bulk promotional traffic is filtered to avoid low-value replies.

## Proper OpenEnv Agent Loop (Required Pattern)

Use this for strict environment interaction:

`reset() -> observation -> one action -> step() -> new observation -> repeat`

Run:

```bash
python live_agent_loop.py --provider imap --limit 10 --max-steps 10
```

Spam-focused loop variant:

```bash
python live_agent_loop.py --provider imap --mode spam-only --limit 20 --max-steps 20
```

Notes:
- `live_agent_loop.py` is OpenEnv-compliant step-by-step execution.
- `send_live_reply.py` is a targeted utility for one email action.

## Plug-and-Play Agent Adapter

Use `agent_adapter.py` to connect any external agent/model stack with plain HTTP calls.

### Simulated benchmark run

```bash
python agent_adapter.py
```

This runs tasks (`easy`, `medium`, `hard`, `killer`) and prints JSON scores.

### Live inbox run

```bash
export ADAPTER_MODE=live
export LIVE_PROVIDER=imap
export LIVE_LIMIT=10
export LIVE_MAX_STEPS=8
python agent_adapter.py
```

### Programmatic usage

```python
from agent_adapter import OpenEnvAgentAdapter

agent = OpenEnvAgentAdapter(mode="simulated")
agent.run_episode(task_id="hard", max_steps=10)

live_agent = OpenEnvAgentAdapter(mode="live", provider="imap")
live_agent.run_episode(max_steps=6, limit=10)
```

## Priority Handling

Inference processes highest-priority unprocessed emails first using `critical > high > medium > low`.
This ensures urgent incidents are handled before lower-priority traffic.
Live state output also prioritizes inbox ordering by severity.

## Evaluation Dashboard

Use API dashboards for grading visibility and operational analytics:

- `GET /dashboard`: combined simulation + live summary
- `GET /live/dashboard`: live metrics only

Dashboard includes:
- applied/blocked action counters
- approval request counters
- auto-generated reply counts
- average reward
- classification + intent distributions
- recent decision events with risk/action metadata

## Docker Usage

```bash
docker build -t eetre .
docker run --rm -p 7860:7860 eetre
```

## Environment Variables

Before submission, define these in your environment configuration:

- `API_BASE_URL`: API endpoint for the LLM.
- `MODEL_NAME`: model identifier used for inference.
- `OPENAI_API_KEY`: OpenRouter or OpenAI-compatible API key used by the OpenAI client.

### Reward variance controls

- `REWARD_NOISE_AMPLITUDE` (default `0.04`, clamped to `[0.0, 0.1]`)
- `REWARD_NOISE_SEED` (optional; when set, reward noise becomes reproducible)

Use `REWARD_NOISE_SEED` for strict A/B comparisons, and leave it unset for natural run-to-run variance.

## Hugging Face Spaces

The repo is Space-ready with the included `Dockerfile` and FastAPI app. Push the repository to a Docker Space and set any live email provider secrets in the Space secret manager.

### Deploy Steps (Docker Space)

1. Create a new Hugging Face Space with SDK set to `Docker`.
2. Push this repository contents to that Space repo.
3. Add secrets in Space Settings → Variables and secrets:
  - `IMAP_HOST`, `IMAP_PORT`, `IMAP_USERNAME`, `IMAP_PASSWORD`
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
  - `API_BASE_URL`, `MODEL_NAME`, `OPENAI_API_KEY`
  - optional: `APPROVAL_MODE`, `APPROVAL_ACTIONS`, `APPROVAL_RISK_LEVELS`
4. Wait for the Space build to complete and check:
  - `GET /` returns 200
  - `POST /reset` works
  - `GET /live/dashboard` works after `/live/reset`

## Baseline Results (example)

| Task | Score |
|---|---:|
| easy | 0.86 |
| medium | 0.73 |
| hard | 0.61 |
| average | 0.73 |

Scores are normalized in range `[0, 1]` and deterministic for identical action sequences.
