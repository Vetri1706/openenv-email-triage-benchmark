# Graph Report - .  (2026-04-25)

## Corpus Check
- 17 files · ~9,379 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 130 nodes · 212 edges · 14 communities detected
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 4 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `ImapProvider` - 11 edges
2. `OpenEnvAgentAdapter` - 10 edges
3. `LiveEmailSession` - 9 edges
4. `_run_simulated_mode()` - 8 edges
5. `_run_live_mode()` - 8 edges
6. `EETREEnv` - 8 edges
7. `run_loop()` - 7 edges
8. `EmailTriageClient` - 7 edges
9. `GmailProvider` - 7 edges
10. `GraphProvider` - 7 edges

## Surprising Connections (you probably didn't know these)
- `Serve the UI dashboard or fallback JSON` --uses--> `LiveEmailSession`  [INFERRED]
  app.py → live_email.py
- `HF-friendly web entrypoint` --uses--> `LiveEmailSession`  [INFERRED]
  app.py → live_email.py
- `ResetRequest` --uses--> `LiveEmailSession`  [INFERRED]
  app.py → live_email.py
- `LiveResetRequest` --uses--> `LiveEmailSession`  [INFERRED]
  app.py → live_email.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.14
Nodes (13): _build_email_record(), build_provider(), create_escalation_ticket(), _decode_header_value(), _extract_text_body(), GmailProvider, GraphProvider, _infer_priority() (+5 more)

### Community 1 - "Community 1"
Cohesion: 0.13
Nodes (16): dashboard(), live_dashboard(), live_reset(), live_state(), live_step(), LiveResetRequest, Serve the UI dashboard or fallback JSON, HF-friendly web entrypoint (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.17
Nodes (11): EETREEnv, extract_action(), EETRE — GRPO Training Script (Grand Finale Ready) Meta PyTorch OpenEnv Hackathon, Agent 2 — oversight auditor.         Validates Agent 1's decision against known, Order matters — check most specific first., Run evaluation episodes and return average reward., Stable reward lookup using (prompt, completion) tuple matching.     Avoids .inde, Safe observation formatter. (+3 more)

### Community 3 - "Community 3"
Cohesion: 0.27
Nodes (3): _extract_json_object(), OpenEnvAgentAdapter, _priority_rank()

### Community 4 - "Community 4"
Cohesion: 0.37
Nodes (12): _apply_safety_guard(), _build_client(), _log_end(), _log_start(), _log_step(), _priority_rank(), _refine_reply_with_llm(), run_baseline() (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.22
Nodes (1): EmailTriageClient

### Community 6 - "Community 6"
Cohesion: 0.54
Nodes (7): _build_action(), _load_env(), main(), _priority_rank(), run_loop(), _select_next_email(), _value_rank()

### Community 7 - "Community 7"
Cohesion: 0.46
Nodes (1): ImapProvider

### Community 8 - "Community 8"
Cohesion: 0.83
Nodes (3): checkHealth(), safeJson(), testReset()

### Community 9 - "Community 9"
Cohesion: 1.0
Nodes (2): run_demo_case(), safe_post()

### Community 10 - "Community 10"
Cohesion: 1.0
Nodes (0): 

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (0): 

### Community 12 - "Community 12"
Cohesion: 1.0
Nodes (0): 

### Community 13 - "Community 13"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **7 isolated node(s):** `EETRE — GRPO Training Script (Grand Finale Ready) Meta PyTorch OpenEnv Hackathon`, `Safe observation formatter.`, `Multi-component reward — each component logged separately.         Judges want t`, `Agent 2 — oversight auditor.         Validates Agent 1's decision against known`, `Order matters — check most specific first.` (+2 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 10`** (1 nodes): `ui_test.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (1 nodes): `environment.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (1 nodes): `js.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ImapProvider` connect `Community 7` to `Community 0`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `LiveEmailSession` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `LiveEmailSession` (e.g. with `ResetRequest` and `LiveResetRequest`) actually correct?**
  _`LiveEmailSession` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `EETRE — GRPO Training Script (Grand Finale Ready) Meta PyTorch OpenEnv Hackathon`, `Safe observation formatter.`, `Multi-component reward — each component logged separately.         Judges want t` to the rest of the system?**
  _7 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.14 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._