"""One-shot helper to wire Twilio -> LiveKit SIP -> agent dispatch.

Creates (idempotently):
  - an inbound SIP trunk that accepts calls from your Twilio SIP domain
  - a dispatch rule that routes every call to a fresh room and triggers the 'booking-agent'

Run once after deploying the agent worker:
    uv run python setup_sip.py
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from livekit import api

load_dotenv()
log = logging.getLogger("setup_sip")
logging.basicConfig(level=logging.INFO)

AGENT_NAME = os.environ.get("AGENT_NAME", "booking-agent")
TWILIO_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]
TRUNK_NAME = "egynaecologist-twilio-inbound"


async def main() -> None:
    lkapi = api.LiveKitAPI()
    try:
        # ---- Inbound trunk -------------------------------------------------
        trunks = await lkapi.sip.list_sip_inbound_trunk(api.ListSIPInboundTrunkRequest())
        existing = next((t for t in trunks.items if t.name == TRUNK_NAME), None)
        if existing:
            log.info("Inbound trunk already exists: %s", existing.sip_trunk_id)
            trunk_id = existing.sip_trunk_id
        else:
            trunk = await lkapi.sip.create_sip_inbound_trunk(
                api.CreateSIPInboundTrunkRequest(
                    trunk=api.SIPInboundTrunkInfo(
                        name=TRUNK_NAME,
                        numbers=[TWILIO_NUMBER],
                    )
                )
            )
            trunk_id = trunk.sip_trunk_id
            log.info("Created inbound trunk: %s", trunk_id)

        # ---- Dispatch rule -------------------------------------------------
        rules = await lkapi.sip.list_sip_dispatch_rule(api.ListSIPDispatchRuleRequest())
        rule_name = "egynaecologist-route-to-agent"
        existing_rule = next((r for r in rules.items if r.name == rule_name), None)
        if existing_rule:
            log.info("Dispatch rule already exists: %s", existing_rule.sip_dispatch_rule_id)
        else:
            rule = await lkapi.sip.create_sip_dispatch_rule(
                api.CreateSIPDispatchRuleRequest(
                    dispatch_rule=api.SIPDispatchRuleInfo(
                        name=rule_name,
                        trunk_ids=[trunk_id],
                        rule=api.SIPDispatchRule(
                            dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                                room_prefix="call-",
                            )
                        ),
                        room_config=api.RoomConfiguration(
                            agents=[api.RoomAgentDispatch(agent_name=AGENT_NAME)],
                        ),
                    )
                )
            )
            log.info("Created dispatch rule: %s", rule.sip_dispatch_rule_id)

        log.info("Done. Twilio number %s -> LiveKit -> agent '%s'.", TWILIO_NUMBER, AGENT_NAME)
        log.info(
            "Final step: in Twilio console, set the number's Voice configuration to "
            "'SIP Domain' = %s and dial: sip:<the-twilio-number>@%s",
            os.environ.get("TWILIO_SIP_DOMAIN", "<your-livekit-sip-domain>"),
            os.environ.get("TWILIO_SIP_DOMAIN", "<your-livekit-sip-domain>"),
        )
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    asyncio.run(main())
