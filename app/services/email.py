"""Transactional email via Resend (https://resend.com).

Kept intentionally tiny: one HTTP POST. If RESEND_API_KEY is unset (local dev),
nothing is sent and the message is logged instead, so flows that depend on email
still work end-to-end during development. Sending never raises into the request
path — callers get a bool.
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings

logger = logging.getLogger("bingetime.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Send one email. Returns True if handed off to Resend, False otherwise."""
    if not settings.resend_api_key:
        logger.warning(
            "RESEND_API_KEY unset — not sending email to %s. Subject: %s", to, subject
        )
        if text:
            logger.warning("Email body (dev):\n%s", text)
        return False
    payload = {
        "from": settings.email_from,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    try:
        resp = httpx.post(
            RESEND_ENDPOINT,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:  # never break the request over an email failure
        logger.error("Email send to %s failed: %s", to, exc)
        return False


def send_password_reset(to: str, reset_url: str) -> bool:
    subject = "Reset your BingeTime password"
    html = f"""\
<div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px">
  <h2 style="margin:0 0 12px">Reset your password</h2>
  <p>We got a request to reset the password for your BingeTime account.
     Click below to choose a new one — this link expires in 1 hour.</p>
  <p style="margin:24px 0">
    <a href="{reset_url}" style="background:#ff4d6d;color:#fff;text-decoration:none;
       padding:12px 20px;border-radius:10px;font-weight:700;display:inline-block">
      Reset password
    </a>
  </p>
  <p style="color:#666;font-size:14px">If you didn't request this, you can safely
     ignore this email — your password won't change.</p>
  <p style="color:#666;font-size:13px">Or paste this link:<br>{reset_url}</p>
</div>"""
    text = (
        "Reset your BingeTime password.\n\n"
        f"Open this link (expires in 1 hour):\n{reset_url}\n\n"
        "If you didn't request this, ignore this email."
    )
    return send_email(to, subject, html, text)


def send_feedback_notice(category: str, message: str, from_email: str | None) -> None:
    """Best-effort ping to admins when new feedback arrives. No-op if no
    admins or no email configured."""
    admins = settings.admin_email_set
    if not admins:
        return
    subject = f"New BingeTime feedback: {category}"
    who = from_email or "anonymous"
    html = (
        f"<p><strong>{category}</strong> from {who}</p>"
        f"<blockquote>{message}</blockquote>"
        f'<p><a href="{settings.base_url}/account/feedback">Open the feedback queue</a></p>'
    )
    text = f"{category} from {who}\n\n{message}\n\n{settings.base_url}/account/feedback"
    for admin in admins:
        send_email(admin, subject, html, text)
