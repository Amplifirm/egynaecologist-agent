"""LiveKit function tools the agent calls during the appointment-request conversation.

We do NOT have access to Meddbase's calendar, so this no longer books real slots —
it captures an appointment REQUEST with the caller's preferred availability ranges,
which the team manually schedules later.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from livekit import api
from livekit.agents import RunContext, function_tool

import db
import email_service
import services as svc

log = logging.getLogger("tools")


# ---------------------------------------------------------------------------
# Per-call state — attached to the userdata of the AgentSession
# ---------------------------------------------------------------------------
@dataclass
class CallState:
    caller_phone: Optional[str] = None
    call_sid: Optional[str] = None
    requests_made: list[str] = field(default_factory=list)  # booking refs
    room_name: Optional[str] = None
    sip_participant_identity: Optional[str] = None
    escalations: list[str] = field(default_factory=list)
    hours_open: bool = True
    mode: str = "out_of_hours"
    bg_audio: Any = None
    pending_escalation_id: Optional[str] = None
    # Last email the agent confirmed via `confirm_email`.
    last_confirmed_email: Optional[str] = None
    # JobContext from agent.py — used after a successful transfer to disconnect
    # the agent so the caller + colleague are alone on the line.
    job_ctx: Any = None
    # Set when transfer_to_colleague is invoked. transfer_succeeded only set true
    # if the dial bridged. These get attached to the booking row written by
    # save_appointment_request, so the dashboard can tag it correctly.
    transfer_attempted: bool = False
    transfer_succeeded: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_date(s: str) -> Optional[date]:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# Tiny NATO phonetic table for spell-back
_NATO = {
    "a": "Alpha", "b": "Bravo", "c": "Charlie", "d": "Delta",
    "e": "Echo", "f": "Foxtrot", "g": "Golf", "h": "Hotel",
    "i": "India", "j": "Juliet", "k": "Kilo", "l": "Lima",
    "m": "Mike", "n": "November", "o": "Oscar", "p": "Papa",
    "q": "Quebec", "r": "Romeo", "s": "Sierra", "t": "Tango",
    "u": "Uniform", "v": "Victor", "w": "Whiskey", "x": "X-ray",
    "y": "Yankee", "z": "Zulu",
}


def _normalise_email(raw: str) -> str:
    """Apply common-sense parsing of a transcribed email."""
    if not raw:
        return ""
    s = raw.strip().lower()

    # Spoken-form replacements (be careful with order)
    replacements = [
        (r"\s+at\s+", "@"),
        (r"\s+@\s*", "@"),
        (r"\s+dot\s+", "."),
        (r"\s+\.\s*", "."),
        (r"\s+underscore\s+", "_"),
        (r"\s+hyphen\s+", "-"),
        (r"\s+dash\s+", "-"),
        (r"\s+minus\s+", "-"),
        (r"\s+plus\s+", "+"),
        (r"\s+", ""),
    ]
    for pat, repl in replacements:
        s = re.sub(pat, repl, s)

    # Auto-append ".com" for known providers if missing
    if "@" in s:
        local, _, domain = s.partition("@")
        if "." not in domain:
            common = {"gmail", "yahoo", "outlook", "hotmail", "icloud", "proton", "protonmail", "aol", "live", "me"}
            if domain in common:
                domain = f"{domain}.com"
            elif domain == "btinternet":
                domain = "btinternet.com"
        s = f"{local}@{domain}"

    return s


def _spell_chars(s: str) -> str:
    """Letter-by-letter NATO phonetic for the local part of an email or a name.
    Digits, dots, hyphens, underscores spoken naturally."""
    parts: list[str] = []
    for ch in s:
        low = ch.lower()
        if low in _NATO:
            parts.append(f"{ch.upper()} as in {_NATO[low]}")
        elif ch.isdigit():
            parts.append(ch)
        elif ch == ".":
            parts.append("dot")
        elif ch == "-":
            parts.append("hyphen")
        elif ch == "_":
            parts.append("underscore")
        elif ch == "+":
            parts.append("plus")
        else:
            parts.append(ch)
    return ", ".join(parts)


# Consumer email domains the agent should speak naturally rather than spell out.
# Company / niche domains get the unique part spelled letter-by-letter, only the TLD
# is spoken naturally.
_COMMON_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.uk",
    "outlook.com", "outlook.co.uk",
    "hotmail.com", "hotmail.co.uk",
    "icloud.com", "me.com",
    "protonmail.com", "proton.me",
    "aol.com", "live.com", "live.co.uk",
    "btinternet.com", "sky.com", "virginmedia.com",
    "ntlworld.com", "talk21.com", "tiscali.co.uk",
}

_COMPOUND_TLDS = {"co.uk", "ac.uk", "gov.uk", "org.uk", "me.uk", "ltd.uk", "plc.uk"}


def _phonetic_readback(email: str) -> str:
    """Readback with letter-by-letter local part. Domain treated thoughtfully:

      - asmit@gmail.com  -> "...at gmail dot com" (whole domain natural)
      - asmit@amplifirm.com -> "...at A as in Alpha, M as in Mike, ..., dot com"
        (unique part spelled out for accuracy, TLD natural)
      - info@neptyune.co.uk -> "...at N as in November, ..., dot co, dot uk"
    """
    if not email:
        return ""
    if "@" not in email:
        return _spell_chars(email)

    local, _, domain = email.partition("@")
    local_phonetic = _spell_chars(local)
    domain_lower = domain.lower()

    # Known consumer domain — speak it as-is, naturally.
    if domain_lower in _COMMON_DOMAINS:
        domain_spoken = " dot ".join(p for p in domain.split(".") if p)
        return f"{local_phonetic}, at {domain_spoken}"

    parts = domain.split(".")
    if len(parts) < 2:
        # Single-token domain — spell whole thing
        return f"{local_phonetic}, at {_spell_chars(domain)}"

    # Detect compound TLDs like "co.uk"
    compound_tld_size = 2 if ".".join(parts[-2:]).lower() in _COMPOUND_TLDS else 1
    unique = ".".join(parts[:-compound_tld_size])
    tld_parts = parts[-compound_tld_size:]

    unique_phonetic = _spell_chars(unique) if unique else ""
    tld_spoken = ", ".join(f"dot {p}" for p in tld_parts)
    if unique_phonetic:
        return f"{local_phonetic}, at {unique_phonetic}, {tld_spoken}"
    return f"{local_phonetic}, at {tld_spoken}"


def _looks_like_email(s: str) -> bool:
    if not s or "@" not in s:
        return False
    local, _, domain = s.partition("@")
    if not local or not domain:
        return False
    if "." not in domain:
        return False
    return True


def _next_booking_ref() -> str:
    today = datetime.now().strftime("%Y%m%d")
    # Use Postgres function for atomic increment
    try:
        return db.next_booking_ref()
    except Exception:
        # Fallback (very unlikely path): timestamp-based
        return f"EG-{today}-{int(datetime.now().timestamp()) % 100000:05d}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@function_tool
async def list_services(ctx: RunContext) -> str:
    """List the services the team can book for the caller."""
    lines = ["Services we offer:"]
    for s in svc.SERVICES:
        lines.append(f"- {s.name} ({svc.format_price(s.price_pence)})")
    return "\n".join(lines)


@function_tool
async def confirm_email(ctx: RunContext, email_attempt: str) -> str:
    """Normalise and prepare a NATO-phonetic readback for the email you THINK you heard.

    Call this every time you have a candidate email, BEFORE saving it. The tool returns
    the cleaned-up email plus a phonetic readback string. Speak the readback verbatim
    to the caller and ask "is that correct?". Only after they say YES, store this
    confirmation; the email cannot be saved by `save_appointment_request` unless it
    was confirmed here first.

    Args:
        email_attempt: Whatever you heard, in any form. Examples that are fine:
            "asmit at amplifirm dot com"
            "asmit@amplifirm.com"
            "j-o-h-n at gmail"
            "smith.j @ outlook"
    """
    state: CallState = ctx.userdata if isinstance(ctx.userdata, CallState) else CallState()
    cleaned = _normalise_email(email_attempt)

    if not _looks_like_email(cleaned):
        return (
            f"NOT_AN_EMAIL: I parsed '{email_attempt}' as '{cleaned}' which doesn't look "
            f"valid. Apologise, ask them to repeat the email slowly, then call this tool "
            f"again with their corrected attempt."
        )

    state.last_confirmed_email = cleaned
    readback = _phonetic_readback(cleaned)
    return (
        f"PARSED: {cleaned}\n"
        f"READBACK (speak this VERBATIM, including the punctuation words): \"{readback}. "
        f"Is that correct?\"\n"
        f"After they say YES, you may proceed to the next field. If they say NO, ask "
        f"which part is wrong and call this tool again with the corrected attempt."
    )


@function_tool
async def save_appointment_request(
    ctx: RunContext,
    service_code: str,
    requested_ranges: str,
    title: str,
    first_name: str,
    last_name: str,
    date_of_birth: str,
    email: str,
    phone: str,
    reason_for_visit: Optional[str] = None,
) -> str:
    """Save the appointment REQUEST. This does NOT book an actual slot — the team
    will manually schedule into Meddbase using the requested ranges and email an invite.

    Call this only after you've confirmed the email via `confirm_email` and the caller
    has provided availability ranges + all personal details.

    Args:
        service_code: One of the codes from the catalog (e.g. 'BDL-PCOS', 'INP-STD').
        requested_ranges: A short string describing the caller's availability windows.
            Example: "Tuesday 10:00-12:00, Wednesday 14:00-16:00".
            Try to capture at least two windows.
        title: Ms / Mrs / Miss / Mr / Dr / Other.
        first_name: Caller's first name.
        last_name: Caller's last name.
        date_of_birth: 'YYYY-MM-DD' if you can; 'DD/MM/YYYY' also accepted.
        email: Patient email — must match the email confirmed via `confirm_email`.
        phone: Patient phone in E.164 format if possible. If they confirmed the calling
            number is best, use the caller ID from the system prompt EXACTLY.
        reason_for_visit: Optional, the caller's free-text reason. Keep brief.
    """
    state: CallState = ctx.userdata if isinstance(ctx.userdata, CallState) else CallState()

    service = svc.BY_CODE.get(service_code)
    if not service:
        return f"ERROR: unknown service code '{service_code}'. Use list_services to see options."

    if not requested_ranges or len(requested_ranges.strip()) < 5:
        return (
            "ERROR: requested_ranges is empty or too short. Ask the caller again for "
            "AT LEAST two availability windows like 'Tuesday morning 10-12'."
        )

    dob = _parse_date(date_of_birth)
    if not dob:
        return f"ERROR: couldn't parse date_of_birth '{date_of_birth}'."

    cleaned_email = _normalise_email(email)
    if not _looks_like_email(cleaned_email):
        return f"ERROR: '{email}' doesn't look like a valid email — call confirm_email first."

    # Sanity: did we actually confirm this email with the caller?
    if state.last_confirmed_email != cleaned_email:
        return (
            f"ERROR: this email ({cleaned_email}) was not confirmed via `confirm_email`. "
            f"Call confirm_email first, read the phonetic spelling back to the caller, "
            f"and only after they say YES, call save_appointment_request again."
        )

    # Phone sanity — refuse known placeholders if we have caller ID
    if state.caller_phone and phone.strip() in {"+447700900000", "07700900000", "+1234567890"}:
        log.warning("Rejecting placeholder phone '%s'; substituting caller ID", phone)
        phone = state.caller_phone

    booking_ref = _next_booking_ref()
    result = db.save_appointment_request(
        booking_ref=booking_ref,
        service_code=service.code,
        service_name=service.name,
        service_price_pence=service.price_pence,
        duration_minutes=service.duration_minutes,
        requested_ranges=requested_ranges.strip(),
        title=title,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        date_of_birth=dob,
        email=cleaned_email,
        phone=phone.strip(),
        reason_for_visit=reason_for_visit,
        call_sid=state.call_sid,
        during_hours=state.hours_open,
        transfer_attempted=state.transfer_attempted,
        transfer_succeeded=state.transfer_succeeded,
    )

    if not result.success:
        log.error("DB error saving request: %s", result.error)
        return (
            "ERROR: I couldn't save the request due to a system issue. Apologise to the "
            "caller, take their callback details using `start_callback`, and tell them "
            "the team will ring back."
        )

    state.requests_made.append(result.booking_ref or booking_ref)

    # Fire-and-forget emails
    try:
        email_service.send_request_received(
            to_email=cleaned_email,
            first_name=first_name.strip(),
            booking_ref=result.booking_ref or booking_ref,
            service_name=service.name,
            requested_ranges=requested_ranges.strip(),
        )
        email_service.send_front_desk_notification(
            booking_ref=result.booking_ref or booking_ref,
            appointment_date=date.today(),
        )
    except Exception:
        log.exception("Email send failed but request is saved")

    return (
        f"SAVED: appointment request stored (ref hidden from caller — they'll see it in "
        f"the email). Now say something warm like: 'Lovely, that's all noted. The team "
        f"will be in touch by email — they'll either send you a calendar invite that "
        f"fits your availability, or reach out about a revised time. Anything else I can "
        f"help with?' Do NOT read out the booking reference."
    )


@function_tool
async def transfer_to_colleague(
    ctx: RunContext,
    reason: str,
) -> str:
    """Escalate to a human colleague. Behaviour depends on `WORKING_HOURS_OPEN` from the prompt.

    - In hours: bridges the call live to the colleague's phone.
    - Out of hours: returns guidance to use `start_callback` instead.

    Args:
        reason: One short sentence describing why you're escalating.
    """
    state: CallState = ctx.userdata if isinstance(ctx.userdata, CallState) else CallState()
    state.escalations.append(reason)

    if not state.hours_open:
        return (
            "OUT_OF_HOURS: do not transfer. Call `start_callback(reason=...)` instead "
            "to log a callback request — that tool also creates the row immediately."
        )

    log.info("ESCALATION (live transfer attempt): %s (caller=%s)", reason, state.caller_phone)

    # Read the live transfer target from the dashboard's settings table first; fall
    # back to the env var if the setting is missing or the DB call fails. This is
    # what lets the team change the transfer number from /admin/settings without a
    # redeploy.
    target = os.environ.get("ESCALATION_PHONE", "+447554477038")
    try:
        from_db = db.get_setting("escalation_phone")
        if from_db:
            target = from_db.strip()
    except Exception:
        log.exception("Could not read escalation_phone from DB; using env fallback")
    log.info("Transfer target: %s", target)

    # ───────────────────── LOOP-PROTECTION GUARD ─────────────────────
    # Refuse to dial a number that would create a self-call loop.
    def _digits(s: str) -> str:
        return "".join(ch for ch in (s or "") if ch.isdigit())

    target_digits = _digits(target)
    inbound_digits = _digits(os.environ.get("TWILIO_PHONE_NUMBER", ""))
    caller_digits = _digits(state.caller_phone or "")

    if not target_digits or len(target_digits) < 7:
        log.error("LOOP GUARD: target %r is not a valid number — refusing to dial", target)
        state.transfer_succeeded = False
        return (
            "ERROR: the configured escalation phone is not a valid number. Apologise to "
            "the caller and switch to taking a callback (capture details via the request "
            "flow and call save_appointment_request)."
        )
    if target_digits == inbound_digits or (caller_digits and target_digits == caller_digits):
        log.error(
            "LOOP GUARD: target=%s would loop back to inbound/caller — refusing to dial",
            target,
        )
        state.transfer_succeeded = False
        return (
            "ERROR: the escalation phone matches the inbound number or the caller — a "
            "transfer would loop. Apologise and switch to taking a callback (capture "
            "details via the request flow and call save_appointment_request)."
        )
    # ─────────────────────────────────────────────────────────────────

    outbound_trunk_id = os.environ.get("LIVEKIT_OUTBOUND_TRUNK_ID")
    if not state.room_name:
        return (
            "ERROR: missing room context. Apologise and call `start_callback` instead."
        )

    # NOTE: we used to pre-register an escalation row here so we'd have a record even
    # if everything blew up. That polluted the dashboard mid-call with partial entries
    # ("caller wants an appointment" with no patient details), confusing the team.
    # We now defer logging until the call's actual outcome is known:
    #   - SUCCESS: write a transferred=true escalation row after the bridge completes
    #   - FAILURE: don't write any escalation row; the fall-through appointment-request
    #     flow writes a booking row with transfer_attempted=true, which the dashboard
    #     then tags as "in hours · no answer · request" with all collected data.

    if not outbound_trunk_id:
        return (
            "ERROR: outbound calling isn't configured. Apologise, then proceed with "
            "the request flow (capture service + availability + details + email + "
            "phone) and call save_appointment_request — the dashboard will tag this "
            "as a transfer attempt regardless."
        )

    # Speak immediately so the caller isn't sitting in dead air during the
    # blocking dial below. Without this, callers think the call is dead.
    try:
        sess = getattr(ctx, "session", None)
        if sess is not None:
            sess.say(
                "Ringing them now — just one moment while it connects.",
                allow_interruptions=False,
            )
    except Exception:
        log.exception("session.say during transfer failed (non-fatal)")

    bg_handle = None
    try:
        if state.bg_audio is not None:
            from livekit.agents.voice.background_audio import AudioConfig
            from pathlib import Path
            mp3 = str(Path(__file__).parent / "sounds" / "hold_music.mp3")
            bg_handle = state.bg_audio.play(AudioConfig(mp3, volume=0.75))
    except Exception:
        log.exception("Failed to start hold music")

    import time as _time
    colleague_identity = f"colleague-{int(_time.time())}"
    bridged = False
    try:
        lkapi = api.LiveKitAPI()
        try:
            from google.protobuf.duration_pb2 import Duration as _Duration
            await lkapi.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=outbound_trunk_id,
                    sip_call_to=target,
                    room_name=state.room_name,
                    participant_identity=colleague_identity,
                    participant_name="Colleague",
                    wait_until_answered=True,
                    play_dialtone=False,
                    # 14s = ~3 rings — enough for a human, before voicemail.
                    ringing_timeout=_Duration(seconds=14),
                    # Hard 10-minute cap. If LiveKit/Twilio fail to tear down for
                    # any reason, the bridge dies at 600s. Combined with the
                    # twilio_watchdog (which also kills calls > 600s server-side)
                    # this is the belt-and-braces protection against another
                    # 4-hour billing leak.
                    max_call_duration=_Duration(seconds=600),
                )
            )
            bridged = True
        finally:
            await lkapi.aclose()
    except Exception as e:
        log.warning("Outbound dial failed: %s", e)

    if bg_handle is not None:
        try: bg_handle.stop()
        except Exception: pass

    if not bridged:
        state.transfer_succeeded = False
        # CLEANUP: remove any ghost colleague participant.
        try:
            lkapi = api.LiveKitAPI()
            try:
                await lkapi.room.remove_participant(
                    api.RoomParticipantIdentity(
                        room=state.room_name,
                        identity=colleague_identity,
                    )
                )
                log.info("Removed ghost colleague participant after failed dial")
            except Exception:
                pass
            finally:
                await lkapi.aclose()
        except Exception:
            log.exception("Failed to clean up ghost participant")

        return (
            "NO_ANSWER: my colleague isn't picking up. Now switch into the FULL "
            "APPOINTMENT-REQUEST FLOW.\n\n"
            "Say warmly, with natural pacing:\n"
            "  'Sorry, looks like they must be busy at the moment. Let me take down "
            "your details and timing preferences — we'll get back to you with the "
            "perfect slot via email.'\n\n"
            "Then proceed through the standard 5 stages from the system prompt:\n"
            "  1. Triage them to a service (use what they already told you about "
            "their reason for calling — confirm: 'I'll put your request in for [X], "
            "is that right?').\n"
            "  2. Ask for availability RANGES (push for at least two windows).\n"
            "  3. Personal details one at a time: title, first name (ASK THEM TO "
            "SPELL IT), last name (SPELL IT), DOB, email (use confirm_email + "
            "phonetic readback), phone (just say 'sure' if calling number is best, "
            "do NOT read it back).\n"
            "  4. Call `save_appointment_request(...)` once you have everything.\n"
            "  5. Confirm warmly and end the call.\n\n"
            "The pre-existing escalation row is fine — leave it. The "
            "save_appointment_request call will create a separate appointment "
            "request, which is the correct outcome."
        )

    # Successful bridge — record an escalation row NOW (with transferred=true) so
    # the dashboard shows "transferred & confirmed" without leaking partial data.
    state.transfer_succeeded = True
    try:
        db.log_escalation(
            caller_phone=state.caller_phone or "unknown",
            callback_phone=state.caller_phone or "unknown",
            reason=reason,
            during_hours=True,
            transferred=True,
            call_sid=state.call_sid,
        )
    except Exception:
        log.exception("Failed to log successful transfer")

    # Schedule the agent to fully disconnect from the room ~2.8s from now. This is
    # the fix for "voicemail audio overlapped with Sophia": even if Twilio bridges
    # voicemail (because no AMD), Sophia is gone, so there's no overlap and the
    # caller will simply hang up after hearing voicemail. With a real human, 2.8s
    # is plenty of time for Sophia to say "Putting you through now" and stop.
    import asyncio as _asyncio
    async def _shutdown_after_handover():
        try:
            await _asyncio.sleep(2.8)
            if state.job_ctx is not None:
                log.info("Disconnecting agent after successful transfer")
                await state.job_ctx.shutdown(reason="transferred_to_colleague")
        except Exception:
            log.exception("Failed to shut down agent after transfer")

    _asyncio.create_task(_shutdown_after_handover())

    return (
        "TRANSFERRED_LIVE: my colleague is on the line. Say ONE short, warm line — "
        "exactly something like 'Lovely, putting you through now.' or 'Right, "
        "connecting you now — take care.' Then STOP speaking. The agent will "
        "automatically disconnect a moment later, leaving the caller with the "
        "colleague."
    )


@function_tool
async def start_callback(ctx: RunContext, reason: str) -> str:
    """Start the callback flow. Call this AS SOON AS you decide to escalate, BEFORE speaking.

    Creates a callback row in the database with the caller's calling number as the
    default callback number. You can update it later with `update_callback_phone` if
    the caller asks to be reached on a different one.

    Args:
        reason: One short sentence summarising why this caller needs a colleague.
    """
    state: CallState = ctx.userdata if isinstance(ctx.userdata, CallState) else CallState()

    if state.pending_escalation_id is not None:
        return (
            "ALREADY_STARTED: callback row already exists. If they want a different "
            "number, call update_callback_phone(phone='...'). Otherwise just confirm "
            "warmly and end the call."
        )

    state.escalations.append(reason)
    eid = db.log_escalation(
        caller_phone=state.caller_phone or "unknown",
        callback_phone=state.caller_phone or "unknown",
        reason=reason,
        during_hours=state.hours_open,
        transferred=False,
        call_sid=state.call_sid,
    )
    state.pending_escalation_id = eid
    log.info("CALLBACK ROW CREATED: %s (caller=%s, hours_open=%s)", eid, state.caller_phone, state.hours_open)

    try:
        email_service.send_escalation_notification(
            caller_phone=state.caller_phone or "unknown",
            callback_phone=state.caller_phone or "unknown",
            reason=reason,
            during_hours=state.hours_open,
        )
    except Exception:
        log.exception("Failed to send escalation email (row already saved)")

    if state.mode == "receptionist_away":
        msg = (
            "STARTED (receptionist away): row saved with caller's calling number. Say:\n"
            "  'Our receptionist has stepped away briefly — we'll give you a ring back on "
            "the number you're calling from as soon as they're back. Is that the best "
            "number, or would you prefer a different one?'\n"
            "If YES → say 'Lovely, we'll be in touch shortly.' DO NOT call more tools.\n"
            "If DIFFERENT → read it back letter-by-letter, then update_callback_phone, "
            "then say 'Lovely, we'll be in touch shortly.'"
        )
    else:
        msg = (
            "STARTED (out-of-hours): row saved with caller's calling number. Say:\n"
            "  'Right — actually we're outside our working hours at the moment. We'll "
            "give you a ring back on the number you're calling from as soon as we're back "
            "in the office. Is that the best number, or would you prefer a different one?'\n"
            "If YES → say 'Lovely, I'll let them know.' DO NOT call more tools.\n"
            "If DIFFERENT → read it back letter-by-letter, then update_callback_phone, "
            "then say 'Lovely, I'll let them know.'"
        )
    return msg


@function_tool
async def update_callback_phone(ctx: RunContext, phone: str) -> str:
    """Update the callback row's phone number — only when the caller has given a number
    DIFFERENT from their calling number AND you've read it back to confirm.
    """
    state: CallState = ctx.userdata if isinstance(ctx.userdata, CallState) else CallState()
    if state.pending_escalation_id is None:
        return "ERROR: no callback row exists yet. Call start_callback first."
    cleaned = phone.strip()
    ok = db.patch_escalation(state.pending_escalation_id, callback_phone=cleaned)
    if not ok:
        return "ERROR: I couldn't update the callback number."
    log.info("CALLBACK NUMBER UPDATED: %s -> %s", state.pending_escalation_id, cleaned)
    return (
        "UPDATED. Now say 'Lovely, I've made a note of that. We'll be in touch shortly.' "
        "Then end the call."
    )


@function_tool
async def end_call(ctx: RunContext) -> str:
    """Politely end the call. Use only after the caller has said goodbye or the request
    is complete."""
    return "OK. Say a brief goodbye and stop speaking."


ALL_TOOLS = [
    list_services,
    confirm_email,
    save_appointment_request,
    transfer_to_colleague,
    start_callback,
    update_callback_phone,
    end_call,
]
