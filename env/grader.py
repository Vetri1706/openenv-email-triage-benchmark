from __future__ import annotations

from dataclasses import dataclass
import os
import random
from typing import Dict, Iterable

from .models import Action, Reward
from .tasks import EmailExpectation, TaskConfig


@dataclass(frozen=True)
class GradeContext:
    step_count: int
    max_steps: int
    already_processed: bool
    expected: EmailExpectation | None
    seen_pairs: Iterable[tuple[str, str]]
    processed_ids: set[str]
    seen_actions: Iterable[str]


def _keyword_coverage(response: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    text = response.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return hits / len(keywords)


def _reward_noise(step_count: int, email_id: str, action_type: str, max_steps: int) -> float:
    raw_amplitude = os.getenv("REWARD_NOISE_AMPLITUDE", "0.04").strip() or "0.04"
    try:
        amplitude = float(raw_amplitude)
    except ValueError:
        amplitude = 0.04
    amplitude = max(0.0, min(0.1, amplitude))
    if amplitude <= 0.0:
        return 0.0

    seed = os.getenv("REWARD_NOISE_SEED", "").strip()
    if seed:
        key = f"{seed}:{step_count}:{email_id}:{action_type}:{max_steps}"
        return random.Random(key).uniform(-amplitude, amplitude)
    return random.uniform(-amplitude, amplitude)


def grade_action(task: TaskConfig, action: Action, context: GradeContext) -> Reward:
    action_correctness = 0.0
    response_quality = 0.0
    bonus = 0.0

    penalties: Dict[str, float] = {}

    if context.expected is None:
        penalties["unknown_email"] = 0.35
    else:
        dependencies_satisfied = all(dep in context.processed_ids for dep in context.expected.depends_on)
        if not dependencies_satisfied:
            penalties["dependency_not_satisfied"] = penalties.get("dependency_not_satisfied", 0.0) + 0.30

        if action.action_type == context.expected.expected_action:
            action_correctness = 1.0
        elif action.action_type in set(context.expected.acceptable_actions):
            action_correctness = 0.75
            penalties["alternative_valid_action"] = penalties.get("alternative_valid_action", 0.0) + 0.05
        else:
            action_correctness = 0.0
            penalties["incorrect_action"] = 0.30
            if context.expected.expected_action == "mark_spam" and action.action_type == "reply":
                penalties["wrong_reply_to_spam"] = penalties.get("wrong_reply_to_spam", 0.0) + 0.50

        if context.expected.response_required:
            if action.action_type != "reply":
                penalties["missed_reply_opportunity"] = 0.40
                if action.action_type == "mark_spam":
                    penalties["support_or_billing_marked_spam"] = penalties.get("support_or_billing_marked_spam", 0.0) + 0.50
            elif action.response is None:
                penalties["missing_response_text"] = 0.25
            else:
                coverage = _keyword_coverage(action.response, context.expected.response_keywords)
                length_bonus = 1.0 if len(action.response.split()) >= 10 else 0.5
                response_quality = min(1.0, 0.7 * coverage + 0.3 * length_bonus)
                if action.action_type == context.expected.expected_action:
                    bonus += 0.30
        else:
            if action.response:
                response_quality = 0.3

    recent_actions = list(context.seen_actions)[-3:]
    if len(recent_actions) == 3 and len(set(recent_actions)) == 1 and action.action_type == recent_actions[-1]:
        penalties["action_mode_collapse"] = penalties.get("action_mode_collapse", 0.0) + 0.18

    repeated_pair = (action.email_id, action.action_type) in set(context.seen_pairs)
    if repeated_pair:
        penalties["repeated_action"] = penalties.get("repeated_action", 0.0) + 0.15

    if context.already_processed:
        penalties["already_processed"] = penalties.get("already_processed", 0.0) + 0.20

    efficiency = max(0.0, 1.0 - (context.step_count - 1) / max(1, context.max_steps - 1))

    weighted = (0.50 * action_correctness) + (0.30 * response_quality) + (0.20 * efficiency)
    total_penalty = sum(penalties.values())
    noise = _reward_noise(context.step_count, action.email_id, action.action_type, context.max_steps)
    raw = max(0.0, min(1.0, weighted + bonus - total_penalty + noise))
    raw = max(0.0, min(1.0, 0.2 + 0.8 * raw))

    feedback_parts = [
        f"action_correctness={action_correctness:.2f}",
        f"response_quality={response_quality:.2f}",
        f"efficiency={efficiency:.2f}",
    ]
    if penalties:
        feedback_parts.append(f"penalties={penalties}")
    if bonus:
        feedback_parts.append(f"bonus={bonus:.2f}")
    if noise:
        feedback_parts.append(f"noise={noise:.3f}")

    return Reward(
        score=raw,
        action_correctness=action_correctness,
        response_quality=response_quality,
        efficiency=efficiency,
        penalties=penalties,
        feedback="; ".join(feedback_parts),
    )
