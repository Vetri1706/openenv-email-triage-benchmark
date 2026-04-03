from __future__ import annotations

from typing import Dict, List

from .models import Email


EMAIL_TASK_DATA: Dict[str, List[Email]] = {
    "easy_single_support": [
        Email(
            id="E-EASY-001",
            sender="ana.rodriguez@northwind-corp.com",
            subject="Password reset link expired",
            body=(
                "Hi IT team, the password reset link in the portal expires instantly and "
                "I cannot sign in to submit my timesheet. Please help me reset access today."
            ),
            priority="medium",
            type="support",
        )
    ],
    "medium_mixed_inbox": [
        Email(
            id="E-MED-001",
            sender="no-reply@cash-prize-now.biz",
            subject="Claim your gift card in 10 minutes",
            body=(
                "You were selected for a corporate bonus. Click now and submit company credentials "
                "to receive your reward."
            ),
            priority="low",
            type="spam",
        ),
        Email(
            id="E-MED-002",
            sender="customer-success@contoso-retail.com",
            subject="API timeout causing failed order sync",
            body=(
                "Our integration requests to /v1/orders are timing out after 30 seconds in production. "
                "Please confirm incident status and ETA."
            ),
            priority="high",
            type="support",
        ),
        Email(
            id="E-MED-003",
            sender="updates@learning-weekly.io",
            subject="Your weekly AI digest + 12 engineering links",
            body=(
                "This is your weekly digest. No action required. Unsubscribe anytime. "
                "Contains curated links and newsletter updates."
            ),
            priority="low",
            type="support",
        ),
        Email(
            id="E-MED-004",
            sender="alerts@vendor-security.co",
            subject="Action recommended: review tenant OAuth policy",
            body=(
                "We observed unusual OAuth consent activity for one integration account. "
                "Review the linked policy summary and confirm whether this access pattern is expected."
            ),
            priority="high",
            type="support",
        ),
    ],
    "hard_enterprise_crisis": [
        Email(
            id="E-HARD-001",
            sender="security-alerts@paym3nts-secure.com",
            subject="Urgent: verify mailbox quota immediately",
            body=(
                "Your corporate mailbox will be suspended. Verify credentials on the attached page "
                "to avoid disruption."
            ),
            priority="high",
            type="phishing",
        ),
        Email(
            id="E-HARD-002",
            sender="cfo.office@northwind-corp.com",
            subject="Board packet blocked: need legal approval now",
            body=(
                "Legal review comments are missing from the board packet due in 45 minutes. "
                "Escalate this to legal operations immediately and confirm owner."
            ),
            priority="critical",
            type="internal",
        ),
        Email(
            id="E-HARD-003",
            sender="billing-admin@fabrikam.com",
            subject="Invoice INV-8841 overcharged by $12,900",
            body=(
                "We were double-billed for enterprise seats this month. Please investigate and "
                "reply with correction timeline and finance contact."
            ),
            priority="high",
            type="billing",
        ),
        Email(
            id="E-HARD-004",
            sender="noreply@vendor-updates.com",
            subject="Quarterly product update and release notes",
            body=(
                "Release notes and feature digest for your subscribed products. "
                "No support ticket required unless you need assistance."
            ),
            priority="low",
            type="support",
        ),
    ],
    "killer_scheduling_conflict": [
        Email(
            id="E-KILL-001",
            sender="executive-assistant@northwind-corp.com",
            subject="Client demo conflicts with quarterly planning sync",
            body=(
                "The client demo and quarterly planning sync overlap on Tuesday at 3:00 PM. "
                "Please reply with two alternative slots and keep the client as the higher priority."
            ),
            priority="high",
            type="internal",
        ),
        Email(
            id="E-KILL-002",
            sender="executive-assistant@northwind-corp.com",
            subject="Re: Client demo conflicts with quarterly planning sync",
            body=(
                "Follow-up: the client can only do Thursday morning. Please propose 10:30 or 11:00, "
                "and avoid repeating the earlier options from Tuesday."
            ),
            priority="high",
            type="internal",
        ),
        Email(
            id="E-KILL-003",
            sender="cfo.office@northwind-corp.com",
            subject="Board review needs legal approval today",
            body=(
                "The legal team needs a decision today because the board review cannot proceed without approval. "
                "Please escalate this to legal operations so we can prioritize the board session."
            ),
            priority="critical",
            type="internal",
        ),
        Email(
            id="E-KILL-004",
            sender="no-reply@northwind-corp.com",
            subject="Auto-confirmation: optional team update",
            body=(
                "This is an informational confirmation for an optional team update. No response is required."
            ),
            priority="low",
            type="support",
        ),
    ],
}
