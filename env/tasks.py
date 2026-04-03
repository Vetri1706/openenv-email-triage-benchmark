from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field

from .data import EMAIL_TASK_DATA


class EmailExpectation(BaseModel):
    email_id: str
    expected_action: Literal["reply", "escalate", "archive", "mark_spam"]
    acceptable_actions: List[Literal["reply", "escalate", "archive", "mark_spam"]] = Field(default_factory=list)
    response_required: bool = False
    response_keywords: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)


class TaskConfig(BaseModel):
    task_id: str
    name: str
    difficulty: Literal["easy", "medium", "hard"]
    objective: str
    max_steps: int
    dataset_key: str
    expectations: List[EmailExpectation]


TASKS: Dict[str, TaskConfig] = {
    "easy": TaskConfig(
        task_id="easy",
        name="Single Support Email Handling",
        difficulty="easy",
        objective="Process one support request with an appropriate customer-facing reply.",
        max_steps=3,
        dataset_key="easy_single_support",
        expectations=[
            EmailExpectation(
                email_id="E-EASY-001",
                expected_action="reply",
                response_required=True,
                response_keywords=["reset", "link", "today"],
            )
        ],
    ),
    "medium": TaskConfig(
        task_id="medium",
        name="Mixed Spam and Support Inbox",
        difficulty="medium",
        objective=(
            "Separate malicious traffic from transactional notifications, respond to production support, "
            "and handle ambiguous security notifications without overfitting to spam actions."
        ),
        max_steps=8,
        dataset_key="medium_mixed_inbox",
        expectations=[
            EmailExpectation(
                email_id="E-MED-001",
                expected_action="mark_spam",
            ),
            EmailExpectation(
                email_id="E-MED-002",
                expected_action="reply",
                response_required=True,
                response_keywords=["incident", "eta", "investigating"],
            ),
            EmailExpectation(
                email_id="E-MED-003",
                expected_action="archive",
                acceptable_actions=["mark_spam"],
            ),
            EmailExpectation(
                email_id="E-MED-004",
                expected_action="escalate",
                acceptable_actions=["mark_spam"],
            ),
        ],
    ),
    "hard": TaskConfig(
        task_id="hard",
        name="Enterprise Triage Under Time Pressure",
        difficulty="hard",
        objective=(
            "Prioritize a phishing threat, an internal urgent legal escalation, and a high-value "
            "billing dispute with correct actions and high-quality communication."
        ),
        max_steps=10,
        dataset_key="hard_enterprise_crisis",
        expectations=[
            EmailExpectation(
                email_id="E-HARD-001",
                expected_action="mark_spam",
            ),
            EmailExpectation(
                email_id="E-HARD-002",
                expected_action="escalate",
            ),
            EmailExpectation(
                email_id="E-HARD-003",
                expected_action="reply",
                response_required=True,
                response_keywords=["refund", "invoice", "timeline"],
                depends_on=["E-HARD-002"],
            ),
            EmailExpectation(
                email_id="E-HARD-004",
                expected_action="archive",
                acceptable_actions=["mark_spam"],
            ),
        ],
    ),
    "killer": TaskConfig(
        task_id="killer",
        name="Meeting Scheduling Conflict Resolution",
        difficulty="hard",
        objective=(
            "Resolve a threaded meeting conflict by prioritizing the most important attendee, proposing alternate slots, "
            "and escalating only when a meeting change affects a critical internal event."
        ),
        max_steps=8,
        dataset_key="killer_scheduling_conflict",
        expectations=[
            EmailExpectation(
                email_id="E-KILL-001",
                expected_action="reply",
                response_required=True,
                response_keywords=["alternative", "slot", "client", "priority"],
            ),
            EmailExpectation(
                email_id="E-KILL-002",
                expected_action="reply",
                response_required=True,
                response_keywords=["thursday", "10:30", "ceo", "prep"],
                depends_on=["E-KILL-001"],
            ),
            EmailExpectation(
                email_id="E-KILL-003",
                expected_action="escalate",
            ),
            EmailExpectation(
                email_id="E-KILL-004",
                expected_action="archive",
            ),
        ],
    ),
}


def get_task(task_id: str) -> TaskConfig:
    if task_id not in TASKS:
        raise ValueError(f"Unknown task_id '{task_id}'. Available: {list(TASKS.keys())}")
    return TASKS[task_id]


def get_task_emails(task_id: str):
    task = get_task(task_id)
    return EMAIL_TASK_DATA[task.dataset_key]
