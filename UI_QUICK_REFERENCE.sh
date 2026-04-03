#!/usr/bin/env bash
# Quick Reference - Web UI Structure & Usage
# ==============================================

cat << 'EOF'

╔══════════════════════════════════════════════════════════════════════════════╗
║                   EMAIL TRIAGE ENVIRONMENT - WEB UI                          ║
║                         Quick Reference Guide                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌─ LAYOUT OVERVIEW ────────────────────────────────────────────────────────────┐
│                                                                              │
│   ┌──────────────────────┐          ┌────────────────────────────────────┐  │
│   │   LEFT PANEL (35%)   │          │      RIGHT PANEL (65%)             │  │
│   │                      │          │                                    │  │
│   ├─ EMAIL TRIAGE       │          ├─ STATUS                           │  │
│   │   AGENT             │          │  • Step: 0                         │  │
│   │                      │          │  • Reward: 0.0000                 │  │
│   ├─ Task Select ▼     │          │  • Done: —                         │  │
│   │ [Reset Environment] │          │                                    │  │
│   │                      │          ├─ OBSERVATION (JSON)               │  │
│   ├─ ◉ E-001 (High)    │          │ {                                  │  │
│   │   Re: Meeting next  │          │   "inbox": [...],                │  │
│   │   alice@corp.com    │          │   "step": 0,                      │  │
│   │                      │          │   ...                              │  │
│   │ ◉ E-002 (Low)      │          │ }                                  │  │
│   │   Newsletter        │          │                                    │  │
│   │   news@bulk.com     │          ├─ HISTORY                         │  │
│   │                      │          │ Step 1: reply (0.8234) ✓         │  │
│   ├─ SELECTED: E-001    │          │ Step 2: escalate (0.9156)        │  │
│   │                      │          │                                    │  │
│   ├─ Action: [v]       │          │                                    │  │
│   │ Response: ────────  │          │                                    │  │
│   │         ────────    │          │                                    │  │
│   │ [Submit Action]     │          │                                    │  │
│   │                      │          │                                    │  │
│   └──────────────────────┘          └────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

WORKFLOW SEQUENCE:
══════════════════════════════════════════════════════════════════════════════

  1. SELECT TASK             2. RESET               3. SELECT EMAIL
  ┌──────────────┐        ┌──────────────┐       ┌──────────────┐
  │ [easy     ▼] │   →    │ [Reset   ]   │  →    │ ◉ E-001   ✓  │
  │ medium       │        │ task_id:easy │       │ (highlighted) │
  │ hard         │        │ POST /reset  │       │              │
  │ killer       │        │              │       │              │
  └──────────────┘        └──────────────┘       └──────────────┘
        ↓                       ↓                        ↓
  Task dropdown         Initializes env          Selected email


  4. CHOOSE ACTION          5. SUBMIT              6. VIEW RESULT
  ┌──────────────┐        ┌──────────────┐       ┌──────────────┐
  │ [archive  ▼] │   →    │ [Submit  ]   │  →    │ Step: 1      │
  │ reply        │        │ POST /step   │       │ Reward:0.823 │
  │ escalate     │        │ action:archive       │ Done: ✓      │
  │ mark_spam    │        │              │       │ History: +1  │
  └──────────────┘        └──────────────┘       └──────────────┘
        ↓                       ↓                        ↓
  Select action type     Execute on backend      Observation updates


COLOR CODING:
══════════════════════════════════════════════════════════════════════════════

  Priority Colors        Action Types           Status Indicators
  ─────────────────      ──────────────         ──────────────────
  🔴 CRITICAL            📧 reply               ✓ Done (green)
  🟠 HIGH                ⬆️  escalate           ⏳ In Progress (orange)
  🟡 MEDIUM              📦 archive             ❌ Error (red)
  🟢 LOW                 🚫 mark_spam

API ENDPOINTS USED:
══════════════════════════════════════════════════════════════════════════════

  GET  /       →  Serve index.html (UI dashboard)
  GET  /health  →  Health check on page load
  POST /reset   →  Initialize environment with task
  POST /step    →  Execute action on selected email
  GET  /state   →  Fetch current observation (optional)
  GET  /static/* →  Serve CSS and JS files

REQUEST/RESPONSE EXAMPLES:
══════════════════════════════════════════════════════════════════════════════

  RESET REQUEST:
  POST /reset
  {
    "task_id": "easy"
  }

  RESET RESPONSE:
  {
    "observation": {
      "inbox": [
        {
          "email_id": "E-001",
          "subject": "Re: Meeting Proposal",
          "sender": "alice@corp.com",
          "priority": "high"
        }
      ]
    }
  }

  STEP REQUEST:
  POST /step
  {
    "email_id": "E-001",
    "action_type": "archive",
    "response": null
  }

  STEP RESPONSE:
  {
    "observation": { ...updated state },
    "reward": 0.8234,
    "done": false,
    "info": {}
  }

UI STATE MACHINE:
══════════════════════════════════════════════════════════════════════════════

                          ┌─────────────┐
                          │  PAGE LOAD  │
                          └──────┬──────┘
                                 │ Health check
                                 ▼
                        ┌─────────────────┐
                        │  NOT INITIALIZED │
                        │ Action form: OFF │
                        └────────┬─────────┘
                                 │ Click "Reset"
                                 ▼
                        ┌─────────────────┐
                        │   INITIALIZED   │
                        │ Action form: ON │
                        └────────┬─────────┘
                      ┌─────────────────────────────┐
                      │                             │
                      ▼                             ▼
              (Select email)              (Action not selected)
                      │                             │
                      ▼                             ▼
             ┌──────────────────┐          (Error message)
             │  EMAIL SELECTED  │                 │
             │ Form enabled     │                 │
             └────────┬─────────┘                 │
                      │                           │
                  (Submit)                        │
                      │                           │
                      ▼                           │
             ┌──────────────────┐                 │
             │  STEP SUBMITTED  │                 │
             │ State updated    │                 │
             └────────┬─────────┘                 │
                      │                           │
        ┌─────────────┴─────────────┐             │
        │                           │             │
        NO                          YES           │
        (done: false)           (done: true)      │
        │                           │             │
        ▼                           ▼             │
   (Loop)              Show completion message    │
        │                           │             │
        └─────────────┬─────────────┘             │
                      │                           │
                  (Reset)                         │
                      │                           │
                      └───────────────────────────┘
                           ▼
                    (Returns to top)

KEYBOARD & MOUSE INTERACTIONS:
══════════════════════════════════════════════════════════════════════════════

  Action                          Element              Trigger
  ──────────────────────────────  ─────────────────    ─────────────
  Select task                     Dropdown (#task-select)  Change event
  Reset environment               Button (#reset-btn)      Click
  Select email                    Email item               Click
  Choose action type              Dropdown (#action-select) Change event
  Enter response text             Textarea (#response-text) Input event
  Submit action                   Button (#step-btn)       Click

COMMON ACTIONS:
══════════════════════════════════════════════════════════════════════════════

  To REPLY:
    1. Select email
    2. Choose "reply" action
    3. Type response message
    4. Click Submit

  To ESCALATE:
    1. Select email
    2. Choose "escalate" action
    3. Leave response empty
    4. Click Submit

  To ARCHIVE:
    1. Select email
    2. Choose "archive" action
    3. Leave response empty
    4. Click Submit

  To MARK SPAM:
    1. Select email
    2. Choose "mark_spam" action
    3. Leave response empty
    4. Click Submit

DEBUGGING TIPS:
══════════════════════════════════════════════════════════════════════════════

  In Browser Console (F12):
  
  • View app state:          console.log(state)
  • View current observation: console.log(state.currentObservation)
  • Check history:            console.log(state.history)
  • Test API:                 fetch('http://localhost:8000/health')
  
  Check Network Tab:
  • POST /reset requests and responses
  • POST /step requests and responses
  • Static file loading (index.html, script.js, style.css)

TROUBLESHOOTING:
══════════════════════════════════════════════════════════════════════════════

  ❌ "Cannot connect to API"
     → Start server: python -m uvicorn app:app --port 8000
     → Check http://localhost:8000 in browser directly

  ❌ "No email selected" error appears
     → Click an email in the inbox list before choosing action

  ❌ Inbox list is empty
     → Click "Reset Environment" first
     → Check browser console for errors (F12)

  ❌ "UI not available" message
     → Verify static/index.html exists (ls static/)
     → Restart FastAPI server

  ❌ Styling looks broken
     → Clear browser cache (Ctrl+Shift+Delete)
     → Check style.css loaded: Look for "static/style.css" in Network tab

  ❌ Submit button doesn't work
     → Select email first
     → Select action type
     → Check browser console for JavaScript errors

PROJECT STRUCTURE:
══════════════════════════════════════════════════════════════════════════════

  /home/ghostofsparta/cd_key_Projects/meta/openenv-email-triage/
  │
  ├── app.py                    # FastAPI server (modified for static files)
  ├── README.md                 # Main documentation
  ├── requirements.txt          # Python dependencies
  ├── Dockerfile                # Docker configuration
  │
  ├── static/                   # NEW: UI files
  │   ├── index.html           # HTML structure (116 lines)
  │   ├── script.js            # JavaScript logic (304 lines)
  │   └── style.css            # Styling (433 lines)
  │
  ├── UI_GUIDE.md              # NEW: Getting started guide
  ├── UI_COMPONENTS.md         # NEW: Technical reference
  └── UI_IMPLEMENTATION_SUMMARY.md  # NEW: Implementation details

GETTING STARTED (30 seconds):
══════════════════════════════════════════════════════════════════════════════

  1. Start server:
     python -m uvicorn app:app --reload --port 8000

  2. Open browser:
     http://localhost:8000

  3. Use dashboard:
     • Select task → Click Reset → Click email → Choose action → Submit

🎉 That's it! You now have a fully functional web dashboard.

EOF
