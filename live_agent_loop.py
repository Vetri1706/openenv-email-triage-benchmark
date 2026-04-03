from __future__ import annotations

import argparse
import os
from typing import Optional

from dotenv import dotenv_values

from env.agent_brain import SmartEmailAgentBrain
from env.models import Action, Email, Observation
from live_email import LiveEmailSession, ProviderType


def _load_env() -> None:
    values = dotenv_values('.env')
    for key, value in values.items():
        if value is not None:
            os.environ[key] = value


def _priority_rank(priority: str) -> int:
    mapping = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return mapping.get(priority, 0)

def _value_rank(email: Email) -> int:
    if email.type == "internal":
        return 4
    if email.type == "billing":
        return 3
    if email.type == "support":
        return 2
    if email.type in {"spam", "phishing"}:
        return 0
    return 1


def _select_next_email(observation: Observation) -> Optional[Email]:
    remaining = [email for email in observation.inbox if email.id not in set(observation.processed_email_ids)]
    if not remaining:
        return None
    remaining.sort(key=lambda item: (_value_rank(item), _priority_rank(item.priority)), reverse=True)
    return remaining[0]


def _build_action(email: Email, brain: SmartEmailAgentBrain, mode: str) -> tuple[Action, str, str, str]:
    decision = brain.decide(email)
    action = decision.action

    if mode == 'spam-only':
        if decision.classification in {'spam', 'phishing'} or email.type in {'spam', 'phishing'}:
            action = Action(email_id=email.id, action_type='mark_spam', response=None)
        else:
            action = Action(email_id=email.id, action_type='archive', response=None)
    elif action.action_type == 'reply':
        action = Action(email_id=action.email_id, action_type=action.action_type, response=None)

    return action, decision.classification, decision.intent, decision.risk_level


def run_loop(provider: ProviderType, limit: int, max_steps: int, mode: str, disable_approval: bool) -> None:
    _load_env()

    if disable_approval:
        os.environ['APPROVAL_MODE'] = 'off'

    brain = SmartEmailAgentBrain()
    session = LiveEmailSession()
    observation = session.reset(provider, limit)

    print(f"[START] loop=live provider={provider} mode={mode} inbox={len(observation.inbox)}")

    done = False
    step_num = 0
    spam_streak = 0

    while not done and step_num < max_steps:
        step_num += 1

        email = _select_next_email(observation)
        if email is None:
            break

        action, classification, intent, risk = _build_action(email, brain, mode)
        if action.action_type == 'mark_spam':
            spam_streak += 1
        else:
            spam_streak = 0

        if spam_streak >= 2:
            non_spam_remaining = [item for item in observation.inbox if item.id not in set(observation.processed_email_ids) and item.type not in {'spam', 'phishing'}]
            if non_spam_remaining:
                non_spam_remaining.sort(key=lambda item: (_value_rank(item), _priority_rank(item.priority)), reverse=True)
                email = non_spam_remaining[0]
                action, classification, intent, risk = _build_action(email, brain, mode)
                spam_streak = 0
        observation, reward, done, info = session.step(action)

        print(
            f"[STEP] step={step_num} email_id={email.id} priority={email.priority} "
            f"classification={classification} intent={intent} risk={risk} "
            f"action={action.action_type} applied={info.get('applied')} "
            f"approval_required={info.get('approval_required', False)} reward={reward.score:.4f} done={done}"
        )

        if info.get('approval_required'):
            break

    dashboard = session.dashboard()
    print(
        f"[END] steps={step_num} done={done} processed={dashboard.get('processed_count')} "
        f"applied={dashboard.get('applied_actions')} blocked={dashboard.get('blocked_actions')} "
        f"avg_reward={dashboard.get('average_reward'):.4f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description='OpenEnv-compliant live agent loop (reset -> step -> state progression).')
    parser.add_argument('--provider', default='imap', choices=['imap', 'gmail', 'graph'])
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--max-steps', type=int, default=10)
    parser.add_argument('--mode', choices=['full', 'spam-only'], default='full')
    parser.add_argument('--disable-approval', action='store_true')
    args = parser.parse_args()

    run_loop(
        provider=args.provider,
        limit=args.limit,
        max_steps=args.max_steps,
        mode=args.mode,
        disable_approval=args.disable_approval,
    )


if __name__ == '__main__':
    main()
