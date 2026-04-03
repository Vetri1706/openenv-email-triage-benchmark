from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Email(BaseModel):
    id: str = Field(..., description="Unique email identifier")
    sender: str
    subject: str
    body: str
    priority: Literal["low", "medium", "high", "critical"]
    type: Literal["support", "billing", "internal", "spam", "phishing"]


class Observation(BaseModel):
    task_id: str
    objective: str
    difficulty: Literal["easy", "medium", "hard"]
    inbox: List[Email]
    processed_email_ids: List[str] = Field(default_factory=list)
    available_actions: List[Literal["reply", "escalate", "archive", "mark_spam"]] = Field(
        default_factory=lambda: ["reply", "escalate", "archive", "mark_spam"]
    )
    step_count: int = 0
    max_steps: int


class Action(BaseModel):
    email_id: str
    action_type: Literal["reply", "escalate", "archive", "mark_spam"]
    response: Optional[str] = None

    @field_validator("response")
    @classmethod
    def normalize_response(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class Reward(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    action_correctness: float = Field(..., ge=0.0, le=1.0)
    response_quality: float = Field(..., ge=0.0, le=1.0)
    efficiency: float = Field(..., ge=0.0, le=1.0)
    penalties: Dict[str, float] = Field(default_factory=dict)
    feedback: str
