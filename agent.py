"""eGynaecologist voice booking agent.

Run locally:
    uv run python agent.py dev

Run as worker (for production / Railway):
    uv run python agent.py start
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()  # before importing anything that reads env

from livekit import api
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)
from livekit.agents.voice.background_audio import (
    AudioConfig,
    BackgroundAudioPlayer,
    BuiltinAudioClip,
)
from livekit.plugins import anthropic, assemblyai, elevenlabs, openai, silero
# We used to use livekit.plugins.turn_detector.MultilingualModel here, but it runs
# in a separate inference subprocess that gets OOM-killed on smaller Railway plans.
# When that subprocess dies, every end-of-turn prediction throws AssertionError and
# the conversation locks up — Sophia can't detect that the caller is done speaking,
# so she never moves on, never calls save_appointment_request, and the call ends
# with no booking. VAD-only turn detection (the default when no model is passed)
# is less linguistically aware but rock-solid memory-wise.

import db
import tools
from prompts import build_system_prompt, is_within_working_hours_now
from twilio_watchdog import start_watchdog_in_background

log = logging.getLogger("agent")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
# Surface tool invocations + LLM events at INFO so we can audit "did the agent
# actually call log_callback_request?" without combing DEBUG logs.
logging.getLogger("livekit.agents.voice").setLevel(logging.INFO)
logging.getLogger("tools").setLevel(logging.INFO)


# Default voice = Alice (Clear, Engaging Educator — British, middle-aged female).
# To swap: set ELEVENLABS_VOICE_ID in .env.
#   Lily   pFZP5JQG7iQjlpkPgRhg  -- Velvety Actress, British female (warmer, theatrical)
#   Alice  Xb7hH8MSUJpSbSDYk0k2  -- Clear, Engaging Educator, British female (default)
DEFAULT_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID") or "Xb7hH8MSUJpSbSDYk0k2"

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai").lower()
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def _build_llm():
    if LLM_PROVIDER == "anthropic":
        log.info("LLM: Anthropic %s", ANTHROPIC_MODEL)
        return anthropic.LLM(model=ANTHROPIC_MODEL)
    log.info("LLM: OpenAI %s", OPENAI_MODEL)
    return openai.LLM(model=OPENAI_MODEL)


class BookingAgent(Agent):
    def __init__(
        self,
        caller_phone: str | None = None,
        hours_open: bool = True,
        mode: str = "out_of_hours",
    ) -> None:
        super().__init__(
            instructions=build_system_prompt(
                caller_phone=caller_phone,
                hours_open=hours_open,
                mode=mode,
            ),
            tools=tools.ALL_TOOLS,
        )


def _resolve_hours_open() -> bool:
    """Read app_settings to decide whether the clinic is open right now.
    `auto`  -> compute from London time, Mon-Fri 9-5
    `open`  -> force open (override for testing)
    `closed` -> force closed (override for testing)
    """
    try:
        mode = (db.get_setting("hours_mode", "auto") or "auto").lower()
    except Exception:
        log.exception("Could not read hours_mode setting; defaulting to auto")
        mode = "auto"
    if mode == "open":
        return True
    if mode == "closed":
        return False
    return is_within_working_hours_now()


def _is_agent_enabled() -> bool:
    """Master toggle from the dashboard. When False, Sophia disconnects immediately."""
    try:
        v = (db.get_setting("agent_enabled", "true") or "true").lower()
    except Exception:
        log.exception("Could not read agent_enabled; defaulting to True")
        return True
    return v in ("true", "1", "yes", "on")


def _extract_caller_phone(ctx: JobContext) -> str | None:
    """Pull the caller's phone number from SIP participant attributes if this is a phone call."""
    for p in ctx.room.remote_participants.values():
        # LiveKit SIP participants expose attributes like:
        #   sip.phoneNumber  -> the caller's number (E.164 if Twilio)
        #   sip.callID       -> SIP call id
        attrs = getattr(p, "attributes", {}) or {}
        for key in ("sip.phoneNumber", "sip.from", "sip.fromUser"):
            if key in attrs and attrs[key]:
                return attrs[key]
    return None


def _find_sip_participant_identity(ctx: JobContext) -> str | None:
    for p in ctx.room.remote_participants.values():
        attrs = getattr(p, "attributes", {}) or {}
        if any(k.startswith("sip.") for k in attrs.keys()):
            return p.identity
    return None


async def entrypoint(ctx: JobContext) -> None:
    # Start (or no-op-restart) the Twilio watchdog the moment a job runs. It's
    # idempotent — if a previous job already started it, asyncio.create_task
    # creates a new one, but we tag it with a name so duplicates are visible.
    # The watchdog kills any Twilio call alive longer than TWILIO_MAX_CALL_SECONDS.
    try:
        loop = asyncio.get_running_loop()
        existing = [t for t in asyncio.all_tasks(loop) if t.get_name() == "twilio-watchdog" and not t.done()]
        if not existing:
            start_watchdog_in_background()
            log.info("Twilio watchdog launched")
    except Exception:
        log.exception("Failed to launch Twilio watchdog")

    await ctx.connect()
    log.info("Agent connected to room %s", ctx.room.name)

    # MASTER TOGGLE — if the dashboard has Sophia turned off, disconnect immediately.
    if not _is_agent_enabled():
        log.info("agent_enabled=false; disconnecting without engaging")
        await ctx.shutdown(reason="agent_disabled_via_dashboard")
        return

    # Wait briefly for the SIP participant so we can read their phone number.
    await ctx.wait_for_participant()
    caller_phone = _extract_caller_phone(ctx)
    log.info("Caller phone: %s", caller_phone)

    hours_open = _resolve_hours_open()
    # Mode drives the entire conversational flow:
    #   - "ivr" (in-hours): Sophia acts as a switchboard. She asks why they're
    #     calling, immediately tries to transfer to the receptionist, and only
    #     falls into the full appointment-request flow if the transfer fails.
    #   - "out_of_hours": clinic is closed. Sophia handles appointment requests
    #     directly, no transfer attempt.
    mode = "ivr" if hours_open else "out_of_hours"
    log.info("Working hours open: %s, mode: %s", hours_open, mode)

    state = tools.CallState(
        caller_phone=caller_phone,
        call_sid=ctx.room.name,
        room_name=ctx.room.name,
        sip_participant_identity=_find_sip_participant_identity(ctx),
        hours_open=hours_open,
        mode=mode,
        job_ctx=ctx,
    )

    session = AgentSession[tools.CallState](
        userdata=state,
        # OpenAI streaming STT. gpt-4o-transcribe (full, not -mini) is noticeably more
        # accurate on names and unusual words — important since callers will be
        # spelling things out and we cannot afford "Asmit"->"Usmith" mistakes.
        # Cost difference per call is pennies.
        stt=openai.STT(
            model="gpt-4o-transcribe",
            language="en",
            # Bias the transcriber towards medical/clinic context. Helps with names of
            # services and reduces phonetic confusion on unusual British surnames.
            prompt=(
                "A patient is phoning eGynaecologist clinic in London to request an "
                "appointment. They will spell their first name and surname letter by "
                "letter. They will give an email address. Common services mentioned "
                "include PCOS, endometriosis, fertility, menopause, coil fitting, "
                "BRCA, HPV, smear test, well-woman check."
            ),
        ),
        llm=_build_llm(),
        tts=elevenlabs.TTS(
            voice_id=DEFAULT_VOICE_ID,
            api_key=os.environ["ELEVENLABS_API_KEY"],
            # Flash streams in smaller, more even chunks than Turbo — better for phone
            # audio because it minimises the "cutty" feel when the LLM is producing text
            # gradually. Quality difference vs Turbo is inaudible after Twilio's mu-law
            # compression squashes everything to 8kHz anyway.
            model="eleven_flash_v2_5",
            # speed=1.0 — any time-stretch adds pitch artifacts. Get pace from the prompt.
            voice_settings=elevenlabs.VoiceSettings(
                stability=0.5,
                similarity_boost=0.85,
                style=0.0,
                use_speaker_boost=True,
                speed=1.0,
            ),
        ),
        vad=silero.VAD.load(),
        # turn_detection intentionally omitted — see import-block comment above.
    )

    # Soft keyboard "thinking" sound while the LLM generates a reply.
    background = BackgroundAudioPlayer(
        thinking_sound=AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.45),
    )

    await session.start(
        agent=BookingAgent(caller_phone=caller_phone, hours_open=hours_open, mode=mode),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )
    await background.start(room=ctx.room, agent_session=session)
    # Expose the player so transfer_to_colleague can play hold music during the bridge.
    state.bg_audio = background

    # Greet the caller. The caller_phone is already baked into the system prompt
    # itself (not just this initial instruction), so it's stable across all turns.
    await session.generate_reply(
        instructions=(
            "Greet the caller warmly with something like: 'Good {timeofday}, you've reached "
            "eGynaecologist, I'm Sophia — how can I help today?' Pick morning/afternoon/evening "
            "based on the current London time."
        )
    )


if __name__ == "__main__":
    # Spawn the Twilio watchdog as a sibling subprocess BEFORE the worker starts.
    # This runs an independent always-on loop that kills any Twilio call alive
    # for >TWILIO_MAX_CALL_SECONDS (default 600). Even if the agent worker
    # crashes, this subprocess keeps running and protects the bill.
    import atexit
    import subprocess as _sp
    import sys as _sys
    _watchdog_proc = None
    try:
        _watchdog_proc = _sp.Popen(
            [_sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "twilio_watchdog.py")],
        )
        log.info("Spawned twilio_watchdog subprocess pid=%s", _watchdog_proc.pid)

        def _kill_watchdog():
            try:
                if _watchdog_proc and _watchdog_proc.poll() is None:
                    _watchdog_proc.terminate()
                    log.info("Terminated twilio_watchdog on shutdown")
            except Exception:
                pass

        atexit.register(_kill_watchdog)
    except Exception:
        log.exception("Failed to spawn twilio_watchdog subprocess")

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            # Must match the agent_name in the LiveKit SIP dispatch rule
            agent_name=os.environ.get("AGENT_NAME", "booking-agent"),
            # Railway/Fly/etc. inject $PORT for the HTTP health endpoint. Falls back
            # to 8081 for local dev.
            port=int(os.environ.get("PORT", "8081")),
            host="0.0.0.0",
            # Don't pre-warm idle worker subprocesses. By default LiveKit forks 3-4
            # idle processes — combined with the inference executor that's 5-6
            # Python interpreters loaded into memory at boot, and Railway's smaller
            # memory plans OOM-kill the inference one. With 0 idle, processes spawn
            # lazily when a call arrives (adds ~1-2s startup on the very first call
            # after redeploy, then warm).
            num_idle_processes=int(os.environ.get("NUM_IDLE_PROCESSES", "0")),
        )
    )
