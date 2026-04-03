from __future__ import annotations

import argparse
import os

from dotenv import dotenv_values

from env.models import Action
from live_email import ImapProvider, LiveEmailSession, _build_email_record, _decode_header_value, _extract_text_body, build_provider
import email as email_parser


def _load_env() -> None:
    values = dotenv_values('.env')
    for key, value in values.items():
        if value is not None:
            os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(description='Send reply via OpenEnv live session only (no SMTP fallback).')
    parser.add_argument('--email-id', required=False, help='Target email ID in current unread inbox set')
    parser.add_argument('--sender-contains', required=False, help='Fallback selector: sender substring')
    parser.add_argument('--subject-contains', required=False, help='Fallback selector: subject substring')
    parser.add_argument('--limit', type=int, default=50, help='Unread emails to fetch')
    parser.add_argument('--response', default=None, help='Optional response. If omitted, AI reply is generated in session.step().')
    parser.add_argument('--disable-approval', action='store_true', help='Temporarily disable approval mode for this run')
    args = parser.parse_args()

    _load_env()

    if args.disable_approval:
        os.environ['APPROVAL_MODE'] = 'off'

    session = LiveEmailSession()
    observation = session.reset('imap', args.limit)

    email_ids = {email.id for email in observation.inbox}
    print('INBOX_IDS', ','.join(sorted(email_ids)))

    target_id = args.email_id
    if target_id and target_id in email_ids:
        pass
    elif not target_id:
        sender_filter = (args.sender_contains or '').lower().strip()
        subject_filter = (args.subject_contains or '').lower().strip()
        candidates = []
        for email in observation.inbox:
            sender_ok = not sender_filter or sender_filter in email.sender.lower()
            subject_ok = not subject_filter or subject_filter in email.subject.lower()
            if sender_ok and subject_ok:
                candidates.append(email)

        if not candidates:
            raise RuntimeError(
                f"email_id '{args.email_id}' not found and no selector match (sender='{args.sender_contains}', subject='{args.subject_contains}')"
            )

        target_id = candidates[-1].id
        print('TARGET_SELECTED_BY_FILTER', target_id)
    else:
        print('TARGET_NOT_IN_BATCH_WILL_FETCH_BY_UID', target_id)

    if not target_id:
        raise RuntimeError('No target email selected')

    if target_id not in email_ids:
        provider = build_provider('imap')
        if not isinstance(provider, ImapProvider):
            raise RuntimeError('IMAP provider unavailable for direct UID fetch')

        client = provider._connect_imap()
        try:
            client.select(provider.mailbox)
            _, msg_data = client.uid('fetch', target_id, '(RFC822)')
            raw = msg_data[0][1] if msg_data and msg_data[0] else b''
            if not raw:
                raise RuntimeError(f"Unable to fetch target email_id '{target_id}' by UID")
            message = email_parser.message_from_bytes(raw)
            sender = _decode_header_value(message.get('From'))
            subject = _decode_header_value(message.get('Subject'))
            body = _extract_text_body(message)
            record = _build_email_record(target_id, sender, subject, body)
        finally:
            try:
                client.close()
            except Exception:
                pass
            client.logout()

        session.provider_name = 'imap'
        session.provider = provider
        session.provider_id_by_email_id = {target_id: target_id}
        session.email_by_id = {target_id: record}
        session.processed_email_ids = []
        session.step_count = 0
        session.max_steps = 2
        session.done = False
        print('TARGET_LOADED_BY_UID', target_id)

    action = Action(email_id=target_id, action_type='reply', response=args.response)
    _, reward, done, info = session.step(action)

    print('SEND_MODE', 'env_step_only')
    print('APPLIED', info.get('applied'))
    print('APPROVAL_REQUIRED', info.get('approval_required', False))
    print('AUTO_GENERATED_REPLY', info.get('auto_generated_reply', False))
    print('REWARD', reward.score)
    print('DONE', done)
    print('INFO', info)


if __name__ == '__main__':
    main()
