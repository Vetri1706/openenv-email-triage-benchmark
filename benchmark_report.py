from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Dict, List, Literal

import httpx
from dotenv import load_dotenv

from env.agent_brain import SmartEmailAgentBrain
from env.environment import EnterpriseEmailTriageEnvironment
from env.models import Action, Observation


Mode = Literal["simulated", "live"]


@dataclass
class RunStats:
    total_reward: float
    avg_reward: float
    action_counts: Counter
    steps: int
    completed: bool


def _priority_rank(priority: str) -> int:
    mapping = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return mapping.get(priority, 0)


def _value_rank(email_type: str) -> int:
    if email_type == "internal":
        return 4
    if email_type == "billing":
        return 3
    if email_type == "support":
        return 2
    if email_type in {"spam", "phishing"}:
        return 0
    return 1


def _select_next_email(observation: Observation):
    processed = set(observation.processed_email_ids)
    remaining = [email for email in observation.inbox if email.id not in processed]
    if not remaining:
        return None
    remaining.sort(key=lambda item: (_value_rank(item.type), _priority_rank(item.priority)), reverse=True)
    return remaining[0]


def _run_simulated_once(task_id: str) -> RunStats:
    brain = SmartEmailAgentBrain()
    env = EnterpriseEmailTriageEnvironment()
    observation = env.reset(task_id)

    total_reward = 0.0
    done = False
    steps = 0
    action_counts: Counter = Counter()
    info: Dict[str, object] = {"completed": False}

    while not done and steps < observation.max_steps:
        steps += 1
        email = _select_next_email(observation)
        if email is None:
            break

        decision = brain.decide(email)
        action = decision.action
        if action.action_type == "reply" and not action.response:
            action = Action(email_id=action.email_id, action_type=action.action_type, response="Acknowledged. We are investigating and will update shortly.")

        action_counts[action.action_type] += 1
        observation, reward, done, info = env.step(action)
        total_reward += reward.score

    return RunStats(
        total_reward=total_reward,
        avg_reward=(total_reward / max(1, steps)),
        action_counts=action_counts,
        steps=steps,
        completed=bool(info.get("completed", False)),
    )


def _run_live_once(env_api_url: str, provider: str, limit: int, max_steps: int) -> RunStats:
    brain = SmartEmailAgentBrain()
    total_reward = 0.0
    steps = 0
    action_counts: Counter = Counter()
    completed = False

    with httpx.Client(timeout=45.0) as client:
        reset_payload = {"provider": provider, "limit": limit}
        reset_res = client.post(f"{env_api_url}/live/reset", json=reset_payload)
        reset_res.raise_for_status()
        observation = Observation.model_validate(reset_res.json().get("observation", {}))

        done = False
        while not done and steps < max_steps and observation.inbox:
            steps += 1
            email = _select_next_email(observation)
            if email is None:
                break

            decision = brain.decide(email)
            action = decision.action
            if action.action_type == "reply" and not action.response:
                action = Action(email_id=action.email_id, action_type=action.action_type, response=None)

            action_counts[action.action_type] += 1
            step_res = client.post(f"{env_api_url}/live/step", json=action.model_dump())
            step_res.raise_for_status()
            payload = step_res.json()

            if payload.get("info", {}).get("approval_required"):
                break

            observation = Observation.model_validate(payload.get("observation", {}))
            reward_score = float(payload.get("reward", {}).get("score", 0.0))
            total_reward += reward_score
            done = bool(payload.get("done", False))

        completed = done

    return RunStats(
        total_reward=total_reward,
        avg_reward=(total_reward / max(1, steps)),
        action_counts=action_counts,
        steps=steps,
        completed=completed,
    )


def _summarize(runs: List[RunStats]) -> Dict[str, object]:
    all_avg_rewards = [item.avg_reward for item in runs]
    all_totals = [item.total_reward for item in runs]
    aggregate_actions: Counter = Counter()
    steps = []
    completed = 0

    for run in runs:
        aggregate_actions.update(run.action_counts)
        steps.append(run.steps)
        completed += 1 if run.completed else 0

    total_actions = sum(aggregate_actions.values())
    action_distribution = {
        key: {
            "count": value,
            "ratio": round((value / total_actions), 4) if total_actions else 0.0,
        }
        for key, value in sorted(aggregate_actions.items())
    }

    return {
        "runs": len(runs),
        "avg_reward_mean": round(mean(all_avg_rewards), 4) if all_avg_rewards else 0.0,
        "avg_reward_std": round(pstdev(all_avg_rewards), 4) if len(all_avg_rewards) > 1 else 0.0,
        "avg_reward_min": round(min(all_avg_rewards), 4) if all_avg_rewards else 0.0,
        "avg_reward_max": round(max(all_avg_rewards), 4) if all_avg_rewards else 0.0,
        "total_reward_mean": round(mean(all_totals), 4) if all_totals else 0.0,
        "steps_mean": round(mean(steps), 2) if steps else 0.0,
        "completed_runs": completed,
        "action_distribution": action_distribution,
    }


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Generate benchmark-grade action distribution and reward variance report.")
    parser.add_argument("--mode", choices=["simulated", "live"], default="simulated")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--task", choices=["easy", "medium", "hard", "killer"], default="hard")
    parser.add_argument("--provider", choices=["imap", "gmail", "graph"], default=os.getenv("LIVE_PROVIDER", "imap"))
    parser.add_argument("--live-limit", type=int, default=int(os.getenv("LIVE_LIMIT", "8")))
    parser.add_argument("--live-max-steps", type=int, default=int(os.getenv("LIVE_MAX_STEPS", "10")))
    parser.add_argument("--env-api-url", default=os.getenv("ENV_API_URL", "http://127.0.0.1:7860").rstrip("/"))
    parser.add_argument("--json", action="store_true", help="Print raw JSON only")
    args = parser.parse_args()

    if args.runs <= 0:
        raise ValueError("--runs must be >= 1")

    runs: List[RunStats] = []
    for _ in range(args.runs):
        if args.mode == "simulated":
            runs.append(_run_simulated_once(args.task))
        else:
            runs.append(_run_live_once(args.env_api_url, args.provider, args.live_limit, args.live_max_steps))

    summary = _summarize(runs)
    summary["mode"] = args.mode
    if args.mode == "simulated":
        summary["task"] = args.task
    else:
        summary["provider"] = args.provider

    if args.json:
        print(json.dumps(summary, indent=2))
        return

    print(f"mode={summary['mode']} runs={summary['runs']}")
    if args.mode == "simulated":
        print(f"task={summary['task']}")
    else:
        print(f"provider={summary['provider']}")
    print(
        "reward(avg): "
        f"mean={summary['avg_reward_mean']:.4f} std={summary['avg_reward_std']:.4f} "
        f"min={summary['avg_reward_min']:.4f} max={summary['avg_reward_max']:.4f}"
    )
    print(f"steps(mean)={summary['steps_mean']} completed_runs={summary['completed_runs']}")
    print("action_distribution:")
    for key, value in summary["action_distribution"].items():
        print(f"  - {key}: count={value['count']} ratio={value['ratio']:.4f}")


if __name__ == "__main__":
    main()
