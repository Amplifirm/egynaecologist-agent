"""Provision outbound calling: Twilio termination + LiveKit outbound SIP trunk.

Run once. Idempotent. Required so the agent can dial out to a colleague's phone
(via `transfer_to_colleague`) in a way that lets Sophia come back if nobody picks up.

Steps:
  1. Create or reuse a Twilio Credential List with a generated user/pass.
  2. Attach the credential list to the existing Twilio Elastic SIP Trunk so
     anyone using those credentials can dial out via this trunk.
  3. Set the trunk's DomainName so it has a SIP termination URI.
  4. Create a LiveKit Outbound SIP Trunk pointing at that termination URI,
     authenticating with the credentials above.

Outputs new env values to add to `.env`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import string
import sys

import httpx
from dotenv import load_dotenv
from livekit import api

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("setup_outbound")

SID = os.environ["TWILIO_ACCOUNT_SID"]
TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]

# The trunk we already created in setup_twilio.py
TRUNK_SID = "TKc381c3f30a03ba58859a92b0367d4524"
DOMAIN_PREFIX = f"egynaecologist-lk-{TRUNK_SID[-6:].lower()}"  # ensures uniqueness

CL_NAME = "egynaecologist-livekit-creds"
LK_TRUNK_NAME = "egynaecologist-twilio-outbound"

AUTH = (SID, TOKEN)
BASE = "https://api.twilio.com/2010-04-01"
TRUNKING = "https://trunking.twilio.com/v1"


def random_password(n: int = 28) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(n))


def list_credential_lists() -> list[dict]:
    r = httpx.get(f"{BASE}/Accounts/{SID}/SIP/CredentialLists.json", auth=AUTH, timeout=20)
    r.raise_for_status()
    return r.json().get("credential_lists", [])


def ensure_credential_list() -> tuple[str, str, str | None]:
    """Returns (credential_list_sid, username, password_or_None_if_reused)."""
    for cl in list_credential_lists():
        if cl.get("friendly_name") == CL_NAME:
            log.info("Reusing existing credential list %s", cl["sid"])
            return cl["sid"], "lkagent", None

    r = httpx.post(
        f"{BASE}/Accounts/{SID}/SIP/CredentialLists.json",
        auth=AUTH,
        data={"FriendlyName": CL_NAME},
        timeout=20,
    )
    r.raise_for_status()
    cl_sid = r.json()["sid"]
    log.info("Created credential list %s", cl_sid)

    username = "lkagent"
    password = random_password()
    r = httpx.post(
        f"{BASE}/Accounts/{SID}/SIP/CredentialLists/{cl_sid}/Credentials.json",
        auth=AUTH,
        data={"Username": username, "Password": password},
        timeout=20,
    )
    r.raise_for_status()
    log.info("Added credential username=%s", username)
    return cl_sid, username, password


def attach_credentials(cl_sid: str) -> None:
    r = httpx.get(f"{TRUNKING}/Trunks/{TRUNK_SID}/CredentialLists", auth=AUTH, timeout=20)
    r.raise_for_status()
    for c in r.json().get("credential_lists", []):
        if c["sid"] == cl_sid:
            log.info("Credential list already attached to trunk")
            return
    r = httpx.post(
        f"{TRUNKING}/Trunks/{TRUNK_SID}/CredentialLists",
        auth=AUTH,
        data={"CredentialListSid": cl_sid},
        timeout=20,
    )
    r.raise_for_status()
    log.info("Attached credentials to trunk")


def ensure_trunk_domain() -> str:
    r = httpx.get(f"{TRUNKING}/Trunks/{TRUNK_SID}", auth=AUTH, timeout=20)
    r.raise_for_status()
    current = r.json().get("domain_name")
    if current:
        log.info("Trunk already has domain: %s", current)
        return current

    domain = f"{DOMAIN_PREFIX}.pstn.twilio.com"
    r = httpx.post(
        f"{TRUNKING}/Trunks/{TRUNK_SID}",
        auth=AUTH,
        data={"DomainName": domain},
        timeout=20,
    )
    if r.status_code >= 400:
        log.error("Failed to set domain: %s — %s", r.status_code, r.text)
        sys.exit(1)
    log.info("Set trunk domain to %s", domain)
    return domain


async def ensure_livekit_outbound_trunk(domain: str, username: str, password: str) -> str:
    lkapi = api.LiveKitAPI()
    try:
        existing = await lkapi.sip.list_sip_outbound_trunk(api.ListSIPOutboundTrunkRequest())
        for t in existing.items:
            if t.name == LK_TRUNK_NAME:
                log.info("Reusing LiveKit outbound trunk %s", t.sip_trunk_id)
                return t.sip_trunk_id

        trunk = await lkapi.sip.create_sip_outbound_trunk(
            api.CreateSIPOutboundTrunkRequest(
                trunk=api.SIPOutboundTrunkInfo(
                    name=LK_TRUNK_NAME,
                    address=domain,
                    numbers=[TWILIO_NUMBER],
                    auth_username=username,
                    auth_password=password,
                )
            )
        )
        log.info("Created LiveKit outbound trunk %s", trunk.sip_trunk_id)
        return trunk.sip_trunk_id
    finally:
        await lkapi.aclose()


async def main() -> None:
    cl_sid, username, password_maybe = ensure_credential_list()

    if password_maybe is None:
        # Reusing an existing credential list — we don't have the password to give to LiveKit.
        password = os.environ.get("TWILIO_TERMINATION_PASSWORD")
        if not password:
            print(
                "\nERROR: a credential list named '%s' already exists, but its password "
                "isn't recoverable from Twilio. Either:\n"
                "  (1) Delete that credential list in Twilio Console -> Voice -> Manage -> "
                "Credential Lists, then re-run, or\n"
                "  (2) Add the existing password to .env as TWILIO_TERMINATION_PASSWORD."
                % CL_NAME
            )
            sys.exit(2)
    else:
        password = password_maybe

    attach_credentials(cl_sid)
    domain = ensure_trunk_domain()
    trunk_id = await ensure_livekit_outbound_trunk(domain, username, password)

    print("\n========= Add these to your .env =========")
    print(f"TWILIO_TERMINATION_USERNAME={username}")
    if password_maybe is not None:
        print(f"TWILIO_TERMINATION_PASSWORD={password}")
    else:
        print("TWILIO_TERMINATION_PASSWORD=<unchanged>")
    print(f"TWILIO_TERMINATION_DOMAIN={domain}")
    print(f"LIVEKIT_OUTBOUND_TRUNK_ID={trunk_id}")
    print("==========================================\n")


if __name__ == "__main__":
    asyncio.run(main())
