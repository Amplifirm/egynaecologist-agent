"""Email service.

Two emails per booking:

1. Patient confirmation — friendly, includes booking summary.
2. Front-desk notification — booking reference ONLY, no patient data
   (per the egynaecologist Secure Booking Email Protocol, Option C).

Provider: Resend (free tier, 100/day). Falls back to a no-op if RESEND_API_KEY is
unset, so local dev doesn't blow up.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, time

import resend

log = logging.getLogger("email_service")

_FROM = os.environ.get("FROM_EMAIL", "bookings@egynaecologist.com")
_FRONT_DESK = os.environ.get("FRONT_DESK_EMAIL", "")
_API_KEY = os.environ.get("RESEND_API_KEY", "")

if _API_KEY:
    resend.api_key = _API_KEY


def _format_slot(d: date, t: time) -> str:
    return f"{d.strftime('%A %d %B %Y')} at {t.strftime('%-I:%M %p').lower()}"


def _send(to: str, subject: str, html: str, text: str) -> None:
    if not _API_KEY:
        log.warning("RESEND_API_KEY not set — skipping email to %s (subject: %s)", to, subject)
        return
    try:
        resend.Emails.send(
            {
                "from": _FROM,
                "to": to,
                "subject": subject,
                "html": html,
                "text": text,
            }
        )
    except Exception as e:
        log.exception("Failed to send email to %s: %s", to, e)


def send_request_received(
    *,
    to_email: str,
    first_name: str,
    booking_ref: str,
    service_name: str,
    requested_ranges: str,
) -> None:
    """Patient-facing 'we received your request' email — for the new appointment-request
    flow where Sophia captures details + availability ranges, and the team manually
    schedules a slot in Meddbase later.
    """
    subject = f"We've got your request, {first_name} — eGynaecologist"
    text = (
        f"Hello {first_name},\n\n"
        f"Thanks for getting in touch — we've received your appointment request.\n\n"
        f"  Service: {service_name}\n"
        f"  Your availability: {requested_ranges}\n"
        f"  Reference: {booking_ref}\n\n"
        f"Our team will be in touch shortly. They'll either send you a calendar invite "
        f"that fits one of your windows, or reach out to find a revised time if your "
        f"range doesn't work.\n\n"
        f"If you need to update or cancel, just reply to this email.\n\n"
        f"With care,\n"
        f"eGynaecologist\n"
        f"Harley Street, London\n"
    )
    html = _render_request_html(
        first_name=first_name,
        booking_ref=booking_ref,
        service_name=service_name,
        requested_ranges=requested_ranges,
    )
    _send(to_email, subject, html, text)


def _render_request_html(*, first_name: str, booking_ref: str, service_name: str, requested_ranges: str) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>We've got your request</title>
</head>
<body style="margin:0;padding:0;background:#f8f2e6;font-family:Georgia,'Times New Roman',serif;color:#11203b;">
  <div style="display:none;max-height:0;overflow:hidden;font-size:1px;line-height:1px;color:#f8f2e6;">
    Your appointment request is with us. Reference {booking_ref}.
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f8f2e6;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;background:#fcf8ee;border:1px solid #e7dfca;">

        <tr><td style="background:#11203b;padding:28px 36px 22px 36px;" align="left">
          <img src="https://egynaecologist.com/wp-content/uploads/2025/07/logo-final1.png"
               alt="eGynaecologist" width="220"
               style="display:block;border:0;outline:0;text-decoration:none;background:#fcf8ee;padding:10px 14px;">
          <p style="margin:14px 0 0 0;color:#c4dfa1;font-family:Helvetica,Arial,sans-serif;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;">
            Request received
          </p>
        </td></tr>

        <tr><td style="padding:42px 36px 8px 36px;">
          <h1 style="margin:0;font-family:Georgia,serif;font-style:italic;font-weight:400;color:#11203b;font-size:32px;line-height:1.15;letter-spacing:-0.01em;">
            Hello {first_name},
          </h1>
          <p style="margin:18px 0 0 0;font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:1.65;color:#324360;">
            Thanks for getting in touch — we've received your appointment request and the
            team will be in touch shortly.
          </p>
        </td></tr>

        <tr><td style="padding:28px 36px 8px 36px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top:1px solid #d7ccb3;border-bottom:1px solid #d7ccb3;">
            <tr><td style="padding:18px 0 14px 0;">
              <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#8b8675;">Service</p>
              <p style="margin:4px 0 0 0;font-family:Georgia,serif;font-size:18px;color:#11203b;">{service_name}</p>
            </td></tr>
            <tr><td style="border-top:1px solid #e7dfca;"></td></tr>
            <tr><td style="padding:18px 0 14px 0;">
              <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#8b8675;">Your availability</p>
              <p style="margin:4px 0 0 0;font-family:Georgia,serif;font-size:17px;color:#11203b;line-height:1.45;">{requested_ranges}</p>
            </td></tr>
            <tr><td style="border-top:1px solid #e7dfca;"></td></tr>
            <tr><td style="padding:18px 0;">
              <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#8b8675;">Reference</p>
              <p style="margin:4px 0 0 0;font-family:'Courier New',monospace;font-size:14px;color:#11203b;letter-spacing:0.04em;">{booking_ref}</p>
            </td></tr>
          </table>
        </td></tr>

        <tr><td style="padding:30px 36px 8px 36px;">
          <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#82bd3f;">What happens next</p>
          <ul style="margin:14px 0 0 0;padding-left:20px;font-family:Helvetica,Arial,sans-serif;font-size:14px;line-height:1.75;color:#324360;">
            <li>The team will review your request and either send you a calendar invite for a
                slot within your availability, or reach out to suggest a revised time.</li>
            <li>You'll receive that invite by email — please keep an eye out.</li>
            <li>To cancel or update, just reply to this email.</li>
          </ul>
        </td></tr>

        <tr><td style="padding:32px 36px 24px 36px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr><td style="background:#fdf3f7;border:1px solid #f1abc6;padding:22px 24px;" align="left">
              <p style="margin:0;font-family:Georgia,serif;font-style:italic;font-size:16px;color:#11203b;line-height:1.5;">
                We look forward to welcoming you.
              </p>
              <p style="margin:8px 0 0 0;font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#324360;line-height:1.6;">
                eGynaecologist · Harley Street, London ·
                <a href="https://egynaecologist.com" style="color:#d94a87;text-decoration:none;">egynaecologist.com</a>
              </p>
            </td></tr>
          </table>
        </td></tr>

        <tr><td style="padding:0 36px 28px 36px;">
          <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:10px;letter-spacing:0.16em;text-transform:uppercase;color:#aea69a;text-align:center;">
            eco-conscious women's healthcare
          </p>
          <p style="margin:14px 0 0 0;font-family:Helvetica,Arial,sans-serif;font-size:10px;line-height:1.6;color:#aea69a;text-align:center;">
            This email was sent because an appointment request was made for {first_name}.
            If this wasn't you, please reply and let us know.
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def send_patient_confirmation(
    *,
    to_email: str,
    first_name: str,
    booking_ref: str,
    service_name: str,
    appointment_date: date,
    appointment_time: time,
) -> None:
    when = _format_slot(appointment_date, appointment_time)
    subject = f"Your appointment is booked, {first_name} — eGynaecologist"
    text = (
        f"Hello {first_name},\n\n"
        f"Your appointment is booked.\n\n"
        f"  Service: {service_name}\n"
        f"  When: {when} (London time)\n"
        f"  Reference: {booking_ref}\n\n"
        f"Someone from our team will be in touch closer to your appointment with anything else you need.\n\n"
        f"If you need to change or cancel, reply to this email and we'll help.\n\n"
        f"With care,\n"
        f"eGynaecologist\n"
        f"Harley Street, London\n"
    )
    html = _render_patient_html(
        first_name=first_name,
        booking_ref=booking_ref,
        service_name=service_name,
        when=when,
    )
    _send(to_email, subject, html, text)


def _render_patient_html(*, first_name: str, booking_ref: str, service_name: str, when: str) -> str:
    """Branded HTML email — pink/green accents, hosted logo, generous whitespace.

    Designed for both desktop and mobile clients (single-column, max 600px). No remote
    fonts so it renders consistently in Outlook/Apple Mail without fallback weirdness.
    """
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your appointment is booked</title>
</head>
<body style="margin:0;padding:0;background:#f8f2e6;font-family:Georgia,'Times New Roman',serif;color:#11203b;">
  <div style="display:none;max-height:0;overflow:hidden;font-size:1px;line-height:1px;color:#f8f2e6;">
    Your appointment is booked. Reference {booking_ref}.
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f8f2e6;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px;width:100%;background:#fcf8ee;border:1px solid #e7dfca;">

          <!-- Brand bar -->
          <tr>
            <td style="background:#11203b;padding:28px 36px 22px 36px;" align="left">
              <img src="https://egynaecologist.com/wp-content/uploads/2025/07/logo-final1.png"
                   alt="eGynaecologist"
                   width="220"
                   style="display:block;border:0;outline:0;text-decoration:none;background:#fcf8ee;padding:10px 14px;">
              <p style="margin:14px 0 0 0;color:#c4dfa1;font-family:Helvetica,Arial,sans-serif;
                        font-size:11px;letter-spacing:0.18em;text-transform:uppercase;">
                Booking confirmed
              </p>
            </td>
          </tr>

          <!-- Headline -->
          <tr>
            <td style="padding:42px 36px 8px 36px;">
              <h1 style="margin:0;font-family:Georgia,serif;font-style:italic;font-weight:400;
                         color:#11203b;font-size:32px;line-height:1.15;letter-spacing:-0.01em;">
                Hello {first_name},
              </h1>
              <p style="margin:18px 0 0 0;font-family:Helvetica,Arial,sans-serif;font-size:15px;
                        line-height:1.65;color:#324360;">
                Your appointment is booked. Here are the details — please keep this email for
                your reference.
              </p>
            </td>
          </tr>

          <!-- Details card -->
          <tr>
            <td style="padding:28px 36px 8px 36px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="border-top:1px solid #d7ccb3;border-bottom:1px solid #d7ccb3;">
                <tr>
                  <td style="padding:18px 0 14px 0;">
                    <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:10px;
                              letter-spacing:0.2em;text-transform:uppercase;color:#8b8675;">
                      Service
                    </p>
                    <p style="margin:4px 0 0 0;font-family:Georgia,serif;font-size:18px;color:#11203b;">
                      {service_name}
                    </p>
                  </td>
                </tr>
                <tr><td style="border-top:1px solid #e7dfca;"></td></tr>
                <tr>
                  <td style="padding:18px 0 14px 0;">
                    <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:10px;
                              letter-spacing:0.2em;text-transform:uppercase;color:#8b8675;">
                      Appointment
                    </p>
                    <p style="margin:4px 0 0 0;font-family:Georgia,serif;font-size:18px;color:#11203b;">
                      {when}
                    </p>
                    <p style="margin:2px 0 0 0;font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#8b8675;">
                      London time
                    </p>
                  </td>
                </tr>
                <tr><td style="border-top:1px solid #e7dfca;"></td></tr>
                <tr>
                  <td style="padding:18px 0;">
                    <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:10px;
                              letter-spacing:0.2em;text-transform:uppercase;color:#8b8675;">
                      Reference
                    </p>
                    <p style="margin:4px 0 0 0;font-family:'Courier New',monospace;font-size:14px;
                              color:#11203b;letter-spacing:0.04em;">
                      {booking_ref}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- What happens next -->
          <tr>
            <td style="padding:30px 36px 8px 36px;">
              <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:10px;
                        letter-spacing:0.2em;text-transform:uppercase;color:#82bd3f;">
                What happens next
              </p>
              <ul style="margin:14px 0 0 0;padding-left:20px;font-family:Helvetica,Arial,sans-serif;
                         font-size:14px;line-height:1.75;color:#324360;">
                <li>Someone from our team will be in touch closer to the date with anything else you
                    need to know — directions to Harley Street, paperwork, or any pre-appointment
                    instructions.</li>
                <li>Need to change or cancel? Simply reply to this email and we'll take care of it.</li>
                <li>Free cancellation up to 48 hours before your appointment.</li>
              </ul>
            </td>
          </tr>

          <!-- Soft CTA / contact -->
          <tr>
            <td style="padding:32px 36px 24px 36px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="background:#fdf3f7;border:1px solid #f1abc6;padding:22px 24px;" align="left">
                    <p style="margin:0;font-family:Georgia,serif;font-style:italic;font-size:16px;
                              color:#11203b;line-height:1.5;">
                      We look forward to welcoming you.
                    </p>
                    <p style="margin:8px 0 0 0;font-family:Helvetica,Arial,sans-serif;font-size:12px;
                              color:#324360;line-height:1.6;">
                      eGynaecologist · Harley Street, London ·
                      <a href="https://egynaecologist.com" style="color:#d94a87;text-decoration:none;">
                        egynaecologist.com
                      </a>
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:0 36px 28px 36px;">
              <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:10px;
                        letter-spacing:0.16em;text-transform:uppercase;color:#aea69a;text-align:center;">
                eco-conscious women's healthcare
              </p>
              <p style="margin:14px 0 0 0;font-family:Helvetica,Arial,sans-serif;font-size:10px;
                        line-height:1.6;color:#aea69a;text-align:center;">
                This email was sent because an appointment was booked for {first_name} at
                eGynaecologist. If this wasn't you, please reply and let us know.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_escalation_notification(
    *,
    caller_phone: str,
    callback_phone: str,
    reason: str,
    during_hours: bool,
) -> None:
    """Tell the front desk a caller asked to be rung back. No PHI in this email."""
    if not _FRONT_DESK:
        log.warning("FRONT_DESK_EMAIL not set — skipping escalation email")
        return
    subject = f"⚠ Callback request — {callback_phone}"
    when_label = "during working hours" if during_hours else "outside working hours"
    text = (
        f"CALLBACK REQUEST\n"
        f"----------------\n"
        f"Caller phone: {caller_phone}\n"
        f"Best callback: {callback_phone}\n"
        f"Reason: {reason}\n"
        f"Logged: {when_label}\n\n"
        f"Action: please call them back as soon as possible. Mark resolved in the dashboard.\n"
    )
    html = f"""
    <div style="font-family: Helvetica, Arial, sans-serif; max-width: 520px;">
      <h2 style="color: #8c2a2e; margin: 0 0 16px 0; font-family: Georgia, serif; font-style: italic;">
        Callback request
      </h2>
      <table style="border-collapse: collapse; font-size: 14px; line-height: 1.7;">
        <tr><td style="padding-right:20px; color:#8b8675; text-transform:uppercase; font-size:11px; letter-spacing:0.1em;">Caller phone</td>
            <td style="font-family: monospace;">{caller_phone}</td></tr>
        <tr><td style="padding-right:20px; color:#8b8675; text-transform:uppercase; font-size:11px; letter-spacing:0.1em;">Best callback</td>
            <td style="font-family: monospace; font-size:16px; color:#11203b;"><strong>{callback_phone}</strong></td></tr>
        <tr><td style="padding-right:20px; color:#8b8675; text-transform:uppercase; font-size:11px; letter-spacing:0.1em;">Reason</td>
            <td>{reason}</td></tr>
        <tr><td style="padding-right:20px; color:#8b8675; text-transform:uppercase; font-size:11px; letter-spacing:0.1em;">Logged</td>
            <td>{when_label}</td></tr>
      </table>
      <p style="margin-top: 18px; color:#324360;">
        Please call them back as soon as possible and mark this resolved in the dashboard.
      </p>
    </div>
    """
    _send(_FRONT_DESK, subject, html, text)


def send_front_desk_notification(
    *,
    booking_ref: str,
    appointment_date: date | None = None,  # kept for backwards compat; no longer used
) -> None:
    """Booking-reference-only email to the front desk per the Secure Booking Email
    Protocol (Option C). Never includes patient name, phone, email, or service code in
    the subject or body.

    Includes the time the agent captured the request, in London time, so the team
    has a sense of how recent it is. The actual data lives in the dashboard.
    """
    _ = appointment_date  # unused
    if not _FRONT_DESK:
        log.warning("FRONT_DESK_EMAIL not set — skipping front-desk notification")
        return
    import pytz
    london = datetime.now(pytz.timezone("Europe/London"))
    captured_at = london.strftime("%A %-d %B %Y, %-I:%M %p").replace("AM", "am").replace("PM", "pm")
    subject = f"New lead — Ref #{booking_ref}"
    text = (
        f"NEW LEAD\n"
        f"--------\n"
        f"Booking Ref: {booking_ref}\n"
        f"Captured:    {captured_at} (London)\n\n"
        f"Action: review the full details in the dashboard.\n"
        f"  https://egynaecologist-dashboard.vercel.app\n\n"
        f"Do not reply with patient details — patient data lives in the dashboard, not in this email.\n"
    )
    html = f"""
    <div style="font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; max-width: 520px;">
      <p style="font-family: Georgia, serif; font-style: italic; font-size: 22px; color: #11203b; margin: 0 0 12px 0;">
        New lead captured
      </p>
      <table style="border-collapse: collapse; font-size: 14px; line-height: 1.7; margin-bottom: 16px;">
        <tr>
          <td style="padding-right: 24px; color:#8b8675; text-transform:uppercase; font-size:10px; letter-spacing:0.16em;">Booking ref</td>
          <td style="font-family: monospace; color:#11203b;">{booking_ref}</td>
        </tr>
        <tr>
          <td style="padding-right: 24px; color:#8b8675; text-transform:uppercase; font-size:10px; letter-spacing:0.16em;">Captured</td>
          <td style="color:#11203b;">{captured_at} <span style="color:#8b8675;">(London)</span></td>
        </tr>
      </table>
      <p style="margin: 16px 0; color:#324360;">
        <a href="https://egynaecologist-dashboard.vercel.app"
           style="color:#d94a87; text-decoration:none; font-weight:600;">
          Review the full lead in the dashboard →
        </a>
      </p>
      <p style="margin-top: 24px; font-size:11px; color:#aea69a; line-height:1.5;">
        Patient details are NOT in this email — they're behind the dashboard login. Please don't reply with patient information.
      </p>
    </div>
    """
    _send(_FRONT_DESK, subject, html, text)
