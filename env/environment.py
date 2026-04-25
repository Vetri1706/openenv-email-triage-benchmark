from __future__ import annotations

from typing import Dict, List, Set, Tuple

try:
    from openenv import Environment
    BASE = Environment
except ImportError:
    BASE = object

from .grader import GradeContext, grade_action
from .models import Action, Observation, Reward
from .tasks import TASKS, TaskConfig, get_task, get_task_emails


class EnterpriseEmailTriageEnvironment(BASE):
    def __init__(self, default_task_id: str = "easy") -> None:
        self.default_task_id = default_task_id
        self.current_task: TaskConfig = get_task(default_task_id)
        self._inbox_by_id: Dict[str, object] = {}
        self._processed_ids: Set[str] = set()
        self._step_count: int = 0
        self._done: bool = False
        self._history: List[Tuple[str, str]] = []
        self._cumulative_score: float = 0.0
        self._expectations_by_email: Dict[str, object] = {}

    def reset(self, task_id: str | None = None) -> Observation:
        selected = task_id or self.default_task_id
        self.current_task = get_task(selected)

        emails = get_task_emails(self.current_task.task_id)
        self._inbox_by_id = {email.id: email for email in emails}
        self._processed_ids = set()
        self._step_count = 0
        self._done = False
        self._history = []
        self._cumulative_score = 0.0
        self._expectations_by_email = {
            item.email_id: item for item in self.current_task.expectations
        }

        return self.state()

    def state(self) -> Observation:
        inbox = [self._inbox_by_id[eid] for eid in sorted(self._inbox_by_id.keys())]
        return Observation(
            task_id=self.current_task.task_id,
            objective=self.current_task.objective,
            difficulty=self.current_task.difficulty,
            inbox=inbox,
            processed_email_ids=sorted(self._processed_ids),
            step_count=self._step_count,
            max_steps=self.current_task.max_steps,
        )

    def step(self, action: Action):
        if self._done:
            reward = Reward(
                score=0.0,
                action_correctness=0.0,
                response_quality=0.0,
                efficiency=0.0,
                penalties={"episode_complete": 1.0},
                feedback="Episode already complete. Call reset() to start a new episode.",
            )
            return self.state(), reward, True, {
                "normalized_score": self._normalized_score(),
                "completed": True,
            }

        self._step_count += 1
        expected = self._expectations_by_email.get(action.email_id)
        already_processed = action.email_id in self._processed_ids

        context = GradeContext(
            step_count=self._step_count,
            max_steps=self.current_task.max_steps,
            already_processed=already_processed,
            expected=expected,
            seen_pairs=self._history,
            processed_ids=set(self._processed_ids),
            seen_actions=[item[1] for item in self._history],
        )
        reward = grade_action(self.current_task, action, context)

        if expected and not already_processed:
            valid_actions = {expected.expected_action, *set(expected.acceptable_actions)}
            if action.action_type in valid_actions:
                if not expected.response_required or action.response:
                    self._processed_ids.add(action.email_id)

        self._history.append((action.email_id, action.action_type))
        self._cumulative_score += reward.score

        completed_all = len(self._processed_ids) == len(self._expectations_by_email)
        max_steps_hit = self._step_count >= self.current_task.max_steps
        self._done = completed_all or max_steps_hit

        bonus = 0.0
        if self._done and completed_all:
            spare_steps = self.current_task.max_steps - self._step_count
            bonus = min(0.10, max(0.0, spare_steps * 0.02))
            self._cumulative_score += bonus

        info = {
            "task_id": self.current_task.task_id,
            "processed": sorted(self._processed_ids),
            "remaining": sorted(set(self._expectations_by_email.keys()) - self._processed_ids),
            "completed": completed_all,
            "max_steps_hit": max_steps_hit,
            "efficiency_bonus": round(bonus, 4),
            "normalized_score": self._normalized_score(),
        }

        return self.state(), reward, self._done, info

    def _normalized_score(self) -> float:
        if self.current_task.max_steps <= 0:
            return 0.0
        normalized = self._cumulative_score / self.current_task.max_steps
        return max(0.0, min(1.0, normalized))


def available_tasks() -> List[dict]:
    output = []
    for task in TASKS.values():
        output.append(
            {
                "task_id": task.task_id,
                "name": task.name,
                "difficulty": task.difficulty,
                "objective": task.objective,
                "max_steps": task.max_steps,
            }
        )
    return output
