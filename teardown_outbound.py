"""Reverses everything setup_outbound.py provisioned.

Removes:
  1. The LiveKit outbound SIP trunk
  2. The credential list <-> Twilio trunk association
  3. The Twilio Credential List (and its credentials)
  4. The Twilio trunk's DomainName (sets it back to None)

Inbound calling stays untouched — the inbound trunk and dispatch rule are not
modified, so calls to +447427905690 continue to land on the agent.

Usage:
    uv run python teardown_outbound.py
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv
from livekit import api

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("teardown_outbound")

SID = os.environ["TWILIO_ACCOUNT_SID"]
TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TRUNK_SID = "TKc381c3f30a03ba58859a92b0367d4524"
CL_NAME = "egynaecologist-livekit-creds"
LK_TRUNK_NAME = "egynaecologist-twilio-outbound"

AUTH = (SID, TOKEN)
BASE = "https://api.twilio.com/2010-04-01"
TRUNKING = "https://trunking.twilio.com/v1"


def find_credential_list_sid() -> str | None:
    r = httpx.get(f"{BASE}/Accounts/{SID}/SIP/CredentialLists.json", auth=AUTH, timeout=20)
    r.raise_for_status()
    for cl in r.json().get("credential_lists", []):
        if cl.get("friendly_name") == CL_NAME:
            return cl["sid"]
    return None


def detach_credentials(cl_sid: str) -> None:
    r = httpx.delete(
        f"{TRUNKING}/Trunks/{TRUNK_SID}/CredentialLists/{cl_sid}",
        auth=AUTH, timeout=20,
    )
    if r.status_code in (200, 204, 404):
        log.info("Detached credential list from trunk")
    else:
        log.warning("Detach returned %s: %s", r.status_code, r.text)


def delete_credential_list(cl_sid: str) -> None:
    r = httpx.delete(
        f"{BASE}/Accounts/{SID}/SIP/CredentialLists/{cl_sid}.json",
        auth=AUTH, timeout=20,
    )
    if r.status_code in (200, 204, 404):
        log.info("Deleted credential list %s", cl_sid)
    else:
        log.warning("Delete CL returned %s: %s", r.status_code, r.text)


def clear_trunk_domain() -> None:
    # Twilio expects an empty string to clear the field
    r = httpx.post(
        f"{TRUNKING}/Trunks/{TRUNK_SID}",
        auth=AUTH,
        data={"DomainName": ""},
        timeout=20,
    )
    if r.status_code == 200:
        log.info("Cleared trunk DomainName")
    else:
        log.warning("Clear domain returned %s: %s", r.status_code, r.text)


async def delete_livekit_outbound() -> None:
    lkapi = api.LiveKitAPI()
    try:
        existing = await lkapi.sip.list_sip_outbound_trunk(api.ListSIPOutboundTrunkRequest())
        for t in existing.items:
            if t.name == LK_TRUNK_NAME:
                await lkapi.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id=t.sip_trunk_id))
                log.info("Deleted LiveKit outbound trunk %s", t.sip_trunk_id)
                return
        log.info("No LiveKit outbound trunk named %s", LK_TRUNK_NAME)
    finally:
        await lkapi.aclose()


async def main() -> None:
    await delete_livekit_outbound()

    cl_sid = find_credential_list_sid()
    if cl_sid:
        detach_credentials(cl_sid)
        delete_credential_list(cl_sid)
    else:
        log.info("No credential list named %s — nothing to remove", CL_NAME)

    clear_trunk_domain()

    print("\nDone. Now remove these lines from .env (they're no longer valid):")
    print("  LIVEKIT_OUTBOUND_TRUNK_ID=...")
    print("  TWILIO_TERMINATION_USERNAME=...")
    print("  TWILIO_TERMINATION_PASSWORD=...")
    print("  TWILIO_TERMINATION_DOMAIN=...")


if __name__ == "__main__":
    asyncio.run(main())
