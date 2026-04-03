from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, Literal, Optional

import httpx
from dotenv import load_dotenv
from openai import OpenAI


Mode = Literal["simulated", "live"]
ActionType = Literal["reply", "escalate", "archive", "mark_spam"]


def _priority_rank(priority: str) -> int:
    mapping = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return mapping.get(priority, 0)


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1]
        if candidate.endswith("```"):
            candidate = candidate[:-3]
        candidate = candidate.strip()

    try:
        value = json.loads(candidate)
        if isinstance(value, dict):
            return value
    except Exception:
        pass

    left = candidate.find("{")
    right = candidate.rfind("}")
    if left != -1 and right != -1 and right > left:
        try:
            value = json.loads(candidate[left : right + 1])
            if isinstance(value, dict):
                return value
        except Exception:
            return None
    return None


class OpenEnvAgentAdapter:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:7860",
        mode: Mode = "simulated",
        provider: str = "imap",
        api_base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        load_dotenv()

        self.base_url = base_url.rstrip("/")
        self.mode: Mode = mode
        self.provider = provider
        self.planner_mode = os.getenv("ADAPTER_PLANNER_MODE", "on").strip().lower() != "off"

        resolved_api_base_url = api_base_url or os.getenv("API_BASE_URL", "https://openrouter.ai/api/v1")
        self.model_name = model_name or os.getenv("MODEL_NAME", "nvidia/nemotron-3-super-120b-a12b:free")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "") or os.getenv("HF_TOKEN", "")

        self.client: Optional[OpenAI] = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=resolved_api_base_url)

    def reset(self, *, task_id: str = "easy", limit: int = 10) -> Dict[str, Any]:
        endpoint = "/live/reset" if self.mode == "live" else "/reset"
        payload: Dict[str, Any]
        if self.mode == "live":
            payload = {"provider": self.provider, "limit": limit}
        else:
            payload = {"task_id": task_id}

        with httpx.Client(timeout=45.0) as http:
            response = http.post(f"{self.base_url}{endpoint}", json=payload)
            response.raise_for_status()
            return response.json()

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = "/live/step" if self.mode == "live" else "/step"
        with httpx.Client(timeout=45.0) as http:
            response = http.post(f"{self.base_url}{endpoint}", json=action)
            response.raise_for_status()
            return response.json()

    def _select_email(self, observation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        inbox = observation.get("inbox", [])
        if not inbox:
            return None

        processed = set(observation.get("processed_email_ids", []))
        remaining = [item for item in inbox if item.get("id") not in processed]
        if not remaining:
            remaining = list(inbox)

        plan = self._plan_sequence(remaining)
        return plan[0] if plan else None

    def _plan_sequence(self, remaining: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        if not remaining:
            return []

        if not self.planner_mode:
            ordered = list(remaining)
            ordered.sort(key=lambda item: (_priority_rank(str(item.get("priority", "low"))), str(item.get("type", "")) != "spam"), reverse=True)
            return ordered

        def plan_key(item: Dict[str, Any]) -> tuple[int, int, int, int]:
            priority = _priority_rank(str(item.get("priority", "low")))
            email_type = str(item.get("type", "support"))
            internal_bonus = 1 if email_type == "internal" else 0
            spam_penalty = 0 if email_type == "spam" else 1
            phishing_bonus = 1 if email_type == "phishing" else 0
            return (priority, phishing_bonus, internal_bonus, spam_penalty)

        ordered = list(remaining)
        ordered.sort(key=plan_key, reverse=True)
        return ordered

    def _heuristic_decision(self, email: Dict[str, Any]) -> Dict[str, Any]:
        email_type = str(email.get("type", "support"))
        if email_type in {"spam", "phishing"}:
            return {"action_type": "mark_spam", "response": None}
        if email_type == "internal":
            return {"action_type": "escalate", "response": None}
        if email_type == "billing":
            return {
                "action_type": "reply",
                "response": "Thanks for flagging this billing issue. We are validating the invoice and will share a correction timeline shortly.",
            }
        return {
            "action_type": "reply",
            "response": "Thanks for the update. We received your message and will provide concrete next steps shortly.",
        }

    def decide_with_llm(self, observation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        email = self._select_email(observation)
        if email is None:
            return None

        processed_ids = observation.get("processed_email_ids", [])
        step_count = observation.get("step_count", 0)
        max_steps = observation.get("max_steps", 0)
        remaining_ids = [item.get("id") for item in observation.get("inbox", []) if item.get("id") not in set(processed_ids)]

        if self.client is None:
            decision = self._heuristic_decision(email)
            return {
                "email_id": email["id"],
                "action_type": decision["action_type"],
                "response": decision.get("response"),
            }

        prompt = (
            "You are an email triage agent.\n"
            "Decide ONE action from: reply, escalate, archive, mark_spam.\n"
            "Return ONLY JSON with keys: action_type, response.\n"
            "Use response only when action_type is reply.\n\n"
            "Rules:\n"
            "- Do NOT reply to spam or phishing.\n"
            "- Escalate urgent internal emails before lower-priority work.\n"
            "- Respect dependencies between related emails and avoid duplicate handling.\n"
            "- Prefer critical/high priority items first.\n\n"
            f"Processed: {processed_ids}\n"
            f"Step: {step_count}/{max_steps}\n"
            f"Remaining IDs: {remaining_ids}\n\n"
            f"Sender: {email.get('sender', '')}\n"
            f"Subject: {email.get('subject', '')}\n"
            f"Body: {email.get('body', '')}\n"
            f"Priority: {email.get('priority', '')}\n"
            f"Type hint: {email.get('type', '')}\n"
        )

        try:
            result = self.client.chat.completions.create(
                model=self.model_name,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": "You are a precise enterprise triage decision agent."},
                    {"role": "user", "content": prompt},
                ],
                timeout=45.0,
            )
            content = (result.choices[0].message.content or "").strip()
            parsed = _extract_json_object(content) or {}
        except Exception:
            parsed = self._heuristic_decision(email)

        action_type = str(parsed.get("action_type", "archive"))
        if action_type not in {"reply", "escalate", "archive", "mark_spam"}:
            action_type = "archive"

        response = parsed.get("response")
        if action_type != "reply":
            response = None
        elif response is not None:
            response = str(response).strip() or None

        return {
            "email_id": email["id"],
            "action_type": action_type,
            "response": response,
        }

    def run_episode(
        self,
        *,
        task_id: str = "easy",
        max_steps: int = 10,
        limit: int = 10,
    ) -> float:
        reset_payload = self.reset(task_id=task_id, limit=limit)
        observation = reset_payload.get("observation", {})

        rewards: list[float] = []
        steps = 0
        task_label = f"live:{self.provider}" if self.mode == "live" else task_id
        print(f"[START] task={task_label}")

        while steps < max_steps:
            action = self.decide_with_llm(observation)
            if action is None:
                break

            result = self.step(action)
            reward = float(result.get("reward", {}).get("score", 0.0))
            done = bool(result.get("done", False))

            print(
                f"[STEP] step={steps + 1} email_id={action['email_id']} action={action['action_type']} "
                f"reward={reward:.4f} done={str(done).lower()}"
            )

            rewards.append(reward)
            steps += 1
            if done:
                break
            observation = result.get("observation", observation)

        score = sum(rewards) / max(1, len(rewards))
        print(f"[END] steps={steps} score={score:.4f}")
        return score

    def run_benchmark(self, tasks: Iterable[str] = ("easy", "medium", "hard", "killer")) -> Dict[str, float]:
        if self.mode == "live":
            raise ValueError("run_benchmark is for simulated mode only")

        scores: Dict[str, float] = {}
        for task_id in tasks:
            scores[task_id] = self.run_episode(task_id=task_id, max_steps=12)
        average = sum(scores.values()) / max(1, len(scores))
        scores["average"] = average
        return scores


if __name__ == "__main__":
    mode = os.getenv("ADAPTER_MODE", "simulated").strip().lower()
    provider = os.getenv("LIVE_PROVIDER", "imap")

    adapter = OpenEnvAgentAdapter(mode="live" if mode == "live" else "simulated", provider=provider)
    if mode == "live":
        adapter.run_episode(max_steps=int(os.getenv("LIVE_MAX_STEPS", "8")), limit=int(os.getenv("LIVE_LIMIT", "10")))
    else:
        results = adapter.run_benchmark()
        print(json.dumps(results, indent=2))
