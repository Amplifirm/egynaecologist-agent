"""Wire the Twilio phone number into LiveKit via Elastic SIP Trunking.

Idempotent. Run after setup_sip.py.

Steps:
  1. Create (or reuse) a Twilio Elastic SIP Trunk.
  2. Point its Origination URL at the LiveKit SIP host so inbound PSTN calls
     are forwarded over SIP to LiveKit, which then dispatches the agent.
  3. Associate TWILIO_PHONE_NUMBER with that trunk (replaces any existing
     voice_url; e.g. previously routed to Vapi).
"""

from __future__ import annotations

import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

log = logging.getLogger("setup_twilio")
logging.basicConfig(level=logging.INFO)

SID = os.environ["TWILIO_ACCOUNT_SID"]
TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
NUMBER = os.environ["TWILIO_PHONE_NUMBER"]
LIVEKIT_SIP_HOST = os.environ["TWILIO_SIP_DOMAIN"]  # e.g. dxzbz05x88o.sip.livekit.cloud

TRUNK_NAME = "egynaecologist-livekit"

AUTH = (SID, TOKEN)
BASE = "https://api.twilio.com/2010-04-01"
TRUNKING = "https://trunking.twilio.com/v1"


def _list_trunks() -> list[dict]:
    r = httpx.get(f"{TRUNKING}/Trunks", auth=AUTH, timeout=20)
    r.raise_for_status()
    return r.json().get("trunks", [])


def _ensure_trunk() -> dict:
    for t in _list_trunks():
        if t.get("friendly_name") == TRUNK_NAME:
            log.info("Reusing existing trunk: %s (%s)", t["sid"], t["domain_name"])
            return t
    r = httpx.post(
        f"{TRUNKING}/Trunks",
        auth=AUTH,
        data={"FriendlyName": TRUNK_NAME},
        timeout=20,
    )
    r.raise_for_status()
    t = r.json()
    log.info("Created trunk: %s (%s)", t["sid"], t["domain_name"])
    return t


def _ensure_origination_url(trunk_sid: str, sip_url: str) -> None:
    r = httpx.get(f"{TRUNKING}/Trunks/{trunk_sid}/OriginationUrls", auth=AUTH, timeout=20)
    r.raise_for_status()
    for u in r.json().get("origination_urls", []):
        if u.get("sip_url") == sip_url:
            log.info("Origination URL already set: %s", sip_url)
            return
    r = httpx.post(
        f"{TRUNKING}/Trunks/{trunk_sid}/OriginationUrls",
        auth=AUTH,
        data={
            "FriendlyName": "livekit-origin",
            "SipUrl": sip_url,
            "Priority": 10,
            "Weight": 10,
            "Enabled": "true",
        },
        timeout=20,
    )
    r.raise_for_status()
    log.info("Origination URL set: %s", sip_url)


def _attach_number(trunk_sid: str, number: str) -> None:
    # Find the IncomingPhoneNumber SID
    r = httpx.get(
        f"{BASE}/Accounts/{SID}/IncomingPhoneNumbers.json",
        auth=AUTH,
        params={"PhoneNumber": number},
        timeout=20,
    )
    r.raise_for_status()
    found = r.json().get("incoming_phone_numbers", [])
    if not found:
        raise SystemExit(f"Number {number} is not on this Twilio account.")
    pn = found[0]
    pn_sid = pn["sid"]
    log.info("Found number %s -> %s (current voice_url: %s)", number, pn_sid, pn.get("voice_url"))

    # Already attached?
    r = httpx.get(f"{TRUNKING}/Trunks/{trunk_sid}/PhoneNumbers", auth=AUTH, timeout=20)
    r.raise_for_status()
    for p in r.json().get("phone_numbers", []):
        if p.get("sid") == pn_sid:
            log.info("Number already attached to trunk.")
            return

    r = httpx.post(
        f"{TRUNKING}/Trunks/{trunk_sid}/PhoneNumbers",
        auth=AUTH,
        data={"PhoneNumberSid": pn_sid},
        timeout=20,
    )
    r.raise_for_status()
    log.info("Attached %s to trunk %s. (Previous voice handler is now bypassed.)", number, trunk_sid)


def main() -> None:
    sip_url = f"sip:{LIVEKIT_SIP_HOST}"
    trunk = _ensure_trunk()
    _ensure_origination_url(trunk["sid"], sip_url)
    _attach_number(trunk["sid"], NUMBER)
    log.info(
        "Done. Inbound calls to %s will be forwarded over SIP to %s, where the "
        "LiveKit agent '%s' is dispatched.",
        NUMBER,
        sip_url,
        os.environ.get("AGENT_NAME", "booking-agent"),
    )


if __name__ == "__main__":
    main()
