from __future__ import annotations

import email
import imaplib
import os
import smtplib
from dataclasses import dataclass
from email.header import decode_header
from email.message import Message
from email.mime.text import MIMEText
from typing import Dict, List, Literal, Optional

import httpx

from env.models import Action, Email, Observation, Reward


ProviderType = Literal["imap", "gmail", "graph"]


def _decode_header_value(raw_value: Optional[str]) -> str:
    if not raw_value:
        return ""
    parts = decode_header(raw_value)
    values: List[str] = []
    for text, charset in parts:
        if isinstance(text, bytes):
            values.append(text.decode(charset or "utf-8", errors="ignore"))
        else:
            values.append(text)
    return "".join(values).strip()


def _extract_text_body(message: Message) -> str:
    if message.is_multipart():
        chunks: List[str] = []
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in disposition.lower():
                payload = part.get_payload(decode=True) or b""
                chunks.append(payload.decode(part.get_content_charset() or "utf-8", errors="ignore"))
        return "\n".join(c.strip() for c in chunks if c.strip())
    payload = message.get_payload(decode=True) or b""
    return payload.decode(message.get_content_charset() or "utf-8", errors="ignore").strip()


def _infer_priority(subject: str, body: str) -> Literal["low", "medium", "high", "critical"]:
    text = f"{subject} {body}".lower()
    if any(token in text for token in ["critical", "sev1", "p0", "immediately", "urgent"]):
        return "critical"
    if any(token in text for token in ["asap", "incident", "production", "outage", "breach"]):
        return "high"
    if any(token in text for token in ["billing", "invoice", "payment", "refund"]):
        return "medium"
    return "low"


def _infer_type(sender: str, subject: str, body: str) -> Literal["support", "billing", "internal", "spam", "phishing"]:
    text = f"{sender} {subject} {body}".lower()
    if any(token in text for token in ["verify account", "password suspended", "click link", "credential"]):
        return "phishing"
    if any(token in text for token in ["prize", "gift card", "win", "crypto", "bonus now"]):
        return "spam"
    if any(token in text for token in ["invoice", "billing", "charge", "refund"]):
        return "billing"
    sender_domain = sender.split("@")[-1] if "@" in sender else ""
    internal_domain = os.getenv("INTERNAL_EMAIL_DOMAIN", "")
    if internal_domain and sender_domain == internal_domain:
        return "internal"
    return "support"


def _build_email_record(email_id: str, sender: str, subject: str, body: str) -> Email:
    return Email(
        id=email_id,
        sender=sender,
        subject=subject,
        body=body.strip(),
        priority=_infer_priority(subject, body),
        type=_infer_type(sender, subject, body),
    )


@dataclass
class ProviderEmail:
    provider_message_id: str
    record: Email


class LiveEmailProvider:
    def fetch_inbox(self, limit: int) -> List[ProviderEmail]:
        raise NotImplementedError

    def apply_action(self, action: Action, provider_message_id: str, original: Email) -> Dict[str, object]:
        raise NotImplementedError


class ImapProvider(LiveEmailProvider):
    def __init__(self) -> None:
        self.imap_host = os.getenv("IMAP_HOST", "")
        self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        self.imap_username = os.getenv("IMAP_USERNAME", "")
        self.imap_password = os.getenv("IMAP_PASSWORD", "")
        self.smtp_host = os.getenv("SMTP_HOST", self.imap_host)
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", self.imap_username)
        self.smtp_password = os.getenv("SMTP_PASSWORD", self.imap_password)
        self.mailbox = os.getenv("IMAP_MAILBOX", "INBOX")

        missing = []
        if not self.imap_host:
            missing.append("IMAP_HOST")
        if not self.imap_username:
            missing.append("IMAP_USERNAME")
        if not self.imap_password:
            missing.append("IMAP_PASSWORD")
        if missing:
            missing_list = ", ".join(missing)
            raise ValueError(f"Missing required IMAP environment variables: {missing_list}")

    def _is_gmail_imap(self) -> bool:
        host = (self.imap_host or "").lower()
        return "gmail" in host

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        client = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        client.login(self.imap_username, self.imap_password)
        return client

    def fetch_inbox(self, limit: int) -> List[ProviderEmail]:
        client = self._connect_imap()
        client.select(self.mailbox)
        _, data = client.uid("search", None, "UNSEEN")
        all_uids = [uid.decode("utf-8") for uid in (data[0] or b"").split()]
        selected_uids = list(reversed(all_uids[-limit:]))

        items: List[ProviderEmail] = []
        for uid in selected_uids:
            _, msg_data = client.uid("fetch", uid, "(RFC822)")
            raw = msg_data[0][1] if msg_data and msg_data[0] else b""
            message = email.message_from_bytes(raw)
            sender = _decode_header_value(message.get("From"))
            subject = _decode_header_value(message.get("Subject"))
            body = _extract_text_body(message)
            items.append(ProviderEmail(provider_message_id=uid, record=_build_email_record(uid, sender, subject, body)))

        client.close()
        client.logout()
        return items

    def _move_to_mailbox(self, uid: str, target_mailbox: str) -> None:
        client = self._connect_imap()
        try:
            select_status, _ = client.select(self.mailbox)
            if select_status != "OK":
                raise RuntimeError(f"Failed to select mailbox '{self.mailbox}'")

            uid_value = str(uid).strip()
            mailbox_value = str(target_mailbox).strip()

            copy_status, copy_data = client.uid("COPY", uid_value, mailbox_value)
            if copy_status != "OK" and mailbox_value:
                quoted_mailbox = f'"{mailbox_value}"'
                copy_status, copy_data = client.uid("COPY", uid_value, quoted_mailbox)

            if copy_status != "OK":
                raise RuntimeError(f"IMAP COPY failed for mailbox '{mailbox_value}': {copy_data}")

            store_status, store_data = client.uid("STORE", uid_value, "+FLAGS", "(\\Deleted)")
            if store_status != "OK":
                raise RuntimeError(f"IMAP STORE failed while deleting original message: {store_data}")

            client.expunge()
        finally:
            try:
                client.close()
            except Exception:
                pass
            client.logout()

    def _send_reply(self, original: Email, response_text: str) -> None:
        msg = MIMEText(response_text, "plain", "utf-8")
        msg["Subject"] = f"Re: {original.subject}"
        msg["From"] = self.smtp_username
        msg["To"] = original.sender

        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        server.starttls()
        server.login(self.smtp_username, self.smtp_password)
        server.sendmail(self.smtp_username, [original.sender], msg.as_string())
        server.quit()

    def _gmail_apply_label_action(self, uid: str, add_labels: str = "", remove_labels: str = "") -> None:
        client = self._connect_imap()
        try:
            select_status, _ = client.select(self.mailbox)
            if select_status != "OK":
                raise RuntimeError(f"Failed to select mailbox '{self.mailbox}'")

            uid_value = str(uid).strip()

            if add_labels:
                add_status, add_data = client.uid("STORE", uid_value, "+X-GM-LABELS", add_labels)
                if add_status != "OK":
                    raise RuntimeError(f"Gmail add label failed: {add_data}")

            if remove_labels:
                remove_status, remove_data = client.uid("STORE", uid_value, "-X-GM-LABELS", remove_labels)
                if remove_status != "OK":
                    raise RuntimeError(f"Gmail remove label failed: {remove_data}")
        finally:
            try:
                client.close()
            except Exception:
                pass
            client.logout()

    def apply_action(self, action: Action, provider_message_id: str, original: Email) -> Dict[str, object]:
        if action.action_type == "reply":
            if not action.response:
                raise ValueError("Response text is required for reply action")
            self._send_reply(original, action.response)
            return {"provider": "imap", "status": "reply_sent"}
        if action.action_type == "mark_spam":
            if self._is_gmail_imap():
                self._gmail_apply_label_action(provider_message_id, add_labels="(\\Spam)", remove_labels="(\\Inbox)")
                return {"provider": "imap", "status": "marked_spam_gmail_labels"}
            spam_box = os.getenv("IMAP_SPAM_MAILBOX", "Spam")
            self._move_to_mailbox(provider_message_id, spam_box)
            return {"provider": "imap", "status": "moved_to_spam", "mailbox": spam_box}
        if action.action_type == "archive":
            if self._is_gmail_imap():
                self._gmail_apply_label_action(provider_message_id, remove_labels="(\\Inbox)")
                return {"provider": "imap", "status": "archived_gmail_labels"}
            archive_box = os.getenv("IMAP_ARCHIVE_MAILBOX", "Archive")
            self._move_to_mailbox(provider_message_id, archive_box)
            return {"provider": "imap", "status": "archived", "mailbox": archive_box}
        if action.action_type == "escalate":
            return create_escalation_ticket(original, action.response)
        raise ValueError("Unsupported action_type")


class GmailProvider(LiveEmailProvider):
    def __init__(self) -> None:
        self.token = os.getenv("GMAIL_ACCESS_TOKEN", "")
        self.user_id = os.getenv("GMAIL_USER_ID", "me")
        self.base_url = "https://gmail.googleapis.com/gmail/v1"
        self.http = httpx.Client(timeout=30.0)

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def fetch_inbox(self, limit: int) -> List[ProviderEmail]:
        params = {"q": "in:inbox is:unread", "maxResults": limit}
        response = self.http.get(f"{self.base_url}/users/{self.user_id}/messages", headers=self._headers(), params=params)
        response.raise_for_status()
        messages = response.json().get("messages", [])

        items: List[ProviderEmail] = []
        for message_meta in messages:
            message_id = message_meta["id"]
            message_resp = self.http.get(
                f"{self.base_url}/users/{self.user_id}/messages/{message_id}",
                headers=self._headers(),
                params={"format": "metadata", "metadataHeaders": ["From", "Subject"]},
            )
            message_resp.raise_for_status()
            payload = message_resp.json().get("payload", {})
            headers = payload.get("headers", [])
            header_map = {h.get("name", ""): h.get("value", "") for h in headers}
            sender = header_map.get("From", "")
            subject = header_map.get("Subject", "")
            snippet = message_resp.json().get("snippet", "")
            items.append(ProviderEmail(provider_message_id=message_id, record=_build_email_record(message_id, sender, subject, snippet)))
        return items

    def apply_action(self, action: Action, provider_message_id: str, original: Email) -> Dict[str, object]:
        if action.action_type == "reply":
            if not action.response:
                raise ValueError("Response text is required for reply action")
            return create_escalation_ticket(original, f"Manual Gmail reply required: {action.response}")
        if action.action_type == "mark_spam":
            response = self.http.post(
                f"{self.base_url}/users/{self.user_id}/messages/{provider_message_id}/modify",
                headers=self._headers(),
                json={"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX", "UNREAD"]},
            )
            response.raise_for_status()
            return {"provider": "gmail", "status": "marked_spam"}
        if action.action_type == "archive":
            response = self.http.post(
                f"{self.base_url}/users/{self.user_id}/messages/{provider_message_id}/modify",
                headers=self._headers(),
                json={"removeLabelIds": ["INBOX"]},
            )
            response.raise_for_status()
            return {"provider": "gmail", "status": "archived"}
        if action.action_type == "escalate":
            return create_escalation_ticket(original, action.response)
        raise ValueError("Unsupported action_type")


class GraphProvider(LiveEmailProvider):
    def __init__(self) -> None:
        self.token = os.getenv("GRAPH_ACCESS_TOKEN", "")
        self.user = os.getenv("GRAPH_USER", "me")
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.http = httpx.Client(timeout=30.0)

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def fetch_inbox(self, limit: int) -> List[ProviderEmail]:
        response = self.http.get(
            f"{self.base_url}/users/{self.user}/mailFolders/Inbox/messages",
            headers=self._headers(),
            params={"$top": limit, "$filter": "isRead eq false", "$select": "id,subject,from,bodyPreview"},
        )
        response.raise_for_status()
        values = response.json().get("value", [])

        items: List[ProviderEmail] = []
        for item in values:
            sender = item.get("from", {}).get("emailAddress", {}).get("address", "")
            subject = item.get("subject", "")
            preview = item.get("bodyPreview", "")
            message_id = item.get("id", "")
            items.append(ProviderEmail(provider_message_id=message_id, record=_build_email_record(message_id, sender, subject, preview)))
        return items

    def apply_action(self, action: Action, provider_message_id: str, original: Email) -> Dict[str, object]:
        if action.action_type == "reply":
            if not action.response:
                raise ValueError("Response text is required for reply action")
            response = self.http.post(
                f"{self.base_url}/users/{self.user}/messages/{provider_message_id}/reply",
                headers=self._headers(),
                json={"comment": action.response},
            )
            response.raise_for_status()
            return {"provider": "graph", "status": "reply_sent"}
        if action.action_type == "mark_spam":
            response = self.http.post(
                f"{self.base_url}/users/{self.user}/messages/{provider_message_id}/move",
                headers=self._headers(),
                json={"destinationId": "junkemail"},
            )
            response.raise_for_status()
            return {"provider": "graph", "status": "marked_spam"}
        if action.action_type == "archive":
            response = self.http.post(
                f"{self.base_url}/users/{self.user}/messages/{provider_message_id}/move",
                headers=self._headers(),
                json={"destinationId": "archive"},
            )
            response.raise_for_status()
            return {"provider": "graph", "status": "archived"}
        if action.action_type == "escalate":
            return create_escalation_ticket(original, action.response)
        raise ValueError("Unsupported action_type")


def create_escalation_ticket(email_record: Email, note: Optional[str]) -> Dict[str, object]:
    webhook = os.getenv("ESCALATION_WEBHOOK_URL", "")
    payload = {
        "source": "eetre",
        "email_id": email_record.id,
        "sender": email_record.sender,
        "subject": email_record.subject,
        "priority": email_record.priority,
        "type": email_record.type,
        "note": note or "Escalated by triage policy",
    }
    if webhook:
        response = httpx.post(webhook, json=payload, timeout=20.0)
        response.raise_for_status()
        return {"status": "escalated", "destination": webhook}
    return {"status": "escalation_queued", "details": payload}


def build_provider(provider: ProviderType) -> LiveEmailProvider:
    if provider == "imap":
        return ImapProvider()
    if provider == "gmail":
        return GmailProvider()
    if provider == "graph":
        return GraphProvider()
    raise ValueError(f"Unsupported provider '{provider}'")


class LiveEmailSession:
    def __init__(self) -> None:
        self.provider_name: Optional[ProviderType] = None
        self.provider: Optional[LiveEmailProvider] = None
        self.provider_id_by_email_id: Dict[str, str] = {}
        self.email_by_id: Dict[str, Email] = {}
        self.processed_email_ids: List[str] = []
        self.step_count = 0
        self.max_steps = 12
        self.done = False

    def reset(self, provider_name: ProviderType, limit: int = 10) -> Observation:
        self.provider_name = provider_name
        self.provider = build_provider(provider_name)
        self.step_count = 0
        self.done = False
        self.processed_email_ids = []
        self.provider_id_by_email_id = {}
        self.email_by_id = {}

        inbox_items = self.provider.fetch_inbox(limit)
        for item in inbox_items:
            self.provider_id_by_email_id[item.record.id] = item.provider_message_id
            self.email_by_id[item.record.id] = item.record

        self.max_steps = max(1, min(30, len(self.email_by_id) * 2))
        return self.state()

    def state(self) -> Observation:
        return Observation(
            task_id="live_inbox",
            objective="Triage and execute actions on live enterprise email inbox",
            difficulty="hard",
            inbox=[self.email_by_id[k] for k in sorted(self.email_by_id.keys())],
            processed_email_ids=list(self.processed_email_ids),
            step_count=self.step_count,
            max_steps=self.max_steps,
        )

    def step(self, action: Action):
        if self.provider is None:
            raise RuntimeError("Live session not initialized. Call /live/reset first.")
        if self.done:
            reward = Reward(
                score=0.0,
                action_correctness=0.0,
                response_quality=0.0,
                efficiency=0.0,
                penalties={"session_complete": 1.0},
                feedback="Live session already complete. Reset to continue.",
            )
            return self.state(), reward, True, {"applied": False}

        self.step_count += 1

        email_id = action.email_id
        if email_id not in self.email_by_id:
            reward = Reward(
                score=0.0,
                action_correctness=0.0,
                response_quality=0.0,
                efficiency=max(0.0, 1.0 - self.step_count / max(self.max_steps, 1)),
                penalties={"unknown_email": 0.5},
                feedback="Unknown email_id for live session",
            )
            return self.state(), reward, False, {"applied": False}

        if email_id in self.processed_email_ids:
            reward = Reward(
                score=0.0,
                action_correctness=0.0,
                response_quality=0.0,
                efficiency=max(0.0, 1.0 - self.step_count / max(self.max_steps, 1)),
                penalties={"already_processed": 0.2},
                feedback="Email already processed in this session",
            )
            return self.state(), reward, False, {"applied": False}

        provider_id = self.provider_id_by_email_id[email_id]
        original = self.email_by_id[email_id]
        action_result = self.provider.apply_action(action, provider_id, original)

        self.processed_email_ids.append(email_id)
        self.done = len(self.processed_email_ids) == len(self.email_by_id) or self.step_count >= self.max_steps

        response_quality = 1.0 if (action.action_type != "reply" or action.response) else 0.0
        efficiency = max(0.0, 1.0 - (self.step_count - 1) / max(1, self.max_steps - 1))
        score = max(0.0, min(1.0, 0.75 + 0.15 * response_quality + 0.10 * efficiency))

        reward = Reward(
            score=score,
            action_correctness=1.0,
            response_quality=response_quality,
            efficiency=efficiency,
            penalties={},
            feedback=f"Action applied successfully via {self.provider_name}",
        )

        return self.state(), reward, self.done, {
            "applied": True,
            "provider": self.provider_name,
            "result": action_result,
            "processed": list(self.processed_email_ids),
        }
