"""Independent Twilio call watchdog.

Polls Twilio every 30 seconds. ANY call that has been alive for more than
TWILIO_MAX_CALL_SECONDS (default 600 = 10 minutes) is force-terminated via the
REST API. Runs as a long-lived asyncio task, used both:

    1) inline inside agent.py at worker startup (so the watchdog is always
       running while the agent is running), AND
    2) as a standalone script (`python twilio_watchdog.py`) deployable as a
       separate Railway service so it stays running even if the agent worker
       is down. Belt and braces.

There is NO server-side max-call-duration setting on Twilio Elastic SIP Trunks
— I checked the API. Twilio's own ceiling is 4 hours, which is exactly what
bit us. This watchdog is the substitute.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import os

import httpx

log = logging.getLogger("twilio_watchdog")

POLL_SECONDS = int(os.environ.get("TWILIO_WATCHDOG_POLL_SECONDS", "30"))
MAX_CALL_SECONDS = int(os.environ.get("TWILIO_MAX_CALL_SECONDS", "600"))


def _twilio_creds() -> tuple[str, str] | None:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    tok = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not tok:
        return None
    return sid, tok


async def _kill_call(client: httpx.AsyncClient, sid: str, tok: str, call_sid: str) -> None:
    try:
        r = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls/{call_sid}.json",
            auth=(sid, tok),
            data={"Status": "completed"},
            timeout=15,
        )
        log.warning("WATCHDOG terminated call %s (HTTP %s)", call_sid, r.status_code)
    except Exception:
        log.exception("WATCHDOG failed to kill call %s", call_sid)


async def _tick(client: httpx.AsyncClient, sid: str, tok: str) -> None:
    """One pass: list in-progress calls, kill any older than MAX_CALL_SECONDS."""
    try:
        r = await client.get(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
            params={"Status": "in-progress"},
            auth=(sid, tok),
            timeout=15,
        )
        if r.status_code != 200:
            log.warning("watchdog list call returned %s: %s", r.status_code, r.text[:200])
            return
        calls = r.json().get("calls", [])
    except Exception:
        log.exception("watchdog list failed")
        return

    if not calls:
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    for c in calls:
        start_str = c.get("start_time")
        if not start_str:
            continue
        try:
            start = datetime.datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except Exception:
            continue
        age_s = (now - start).total_seconds()
        if age_s > MAX_CALL_SECONDS:
            log.warning(
                "WATCHDOG: call %s has been alive %.0fs (limit %ds) — terminating",
                c.get("sid"), age_s, MAX_CALL_SECONDS,
            )
            await _kill_call(client, sid, tok, c["sid"])


async def watchdog_loop() -> None:
    """Long-running loop. Designed to NEVER raise upward — every error is logged
    and we continue. The only way to stop it is cancellation."""
    log.info(
        "twilio watchdog starting (poll=%ds, kill-after=%ds)",
        POLL_SECONDS, MAX_CALL_SECONDS,
    )
    creds = _twilio_creds()
    if not creds:
        log.error("watchdog disabled — TWILIO_ACCOUNT_SID/AUTH_TOKEN missing")
        return
    sid, tok = creds

    async with httpx.AsyncClient() as client:
        while True:
            try:
                await _tick(client, sid, tok)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("watchdog tick crashed (continuing)")
            await asyncio.sleep(POLL_SECONDS)


def start_watchdog_in_background() -> asyncio.Task:
    """Start the watchdog as a background asyncio task. Returns the task handle."""
    task = asyncio.create_task(watchdog_loop(), name="twilio-watchdog")
    return task


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(watchdog_loop())
