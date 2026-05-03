"""Supabase data access layer for the booking agent.

Uses the service role key (server-side only) and bypasses RLS. Never embed this key
in any client-facing code or in voice transcripts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, time
from typing import Optional

from supabase import Client, create_client


def _client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@dataclass
class BookingResult:
    success: bool
    booking_ref: Optional[str]
    error: Optional[str]  # 'slot_taken' | 'db_error' | None


def list_available_slots(target: date) -> list[time]:
    """Return the free 30-minute slots for a Mon-Fri date between 09:00 and 17:00."""
    sb = _client()
    res = sb.rpc("available_slots", {"p_date": target.isoformat()}).execute()
    out: list[time] = []
    for row in res.data or []:
        ts = row["slot_time"]
        # Postgres returns time as 'HH:MM:SS'
        h, m, *_ = (int(p) for p in ts.split(":"))
        out.append(time(h, m))
    return out


def is_slot_free(target_date: date, target_time: time) -> bool:
    sb = _client()
    res = (
        sb.table("bookings")
        .select("id")
        .eq("appointment_date", target_date.isoformat())
        .eq("appointment_time", target_time.strftime("%H:%M:%S"))
        .limit(1)
        .execute()
    )
    return not res.data


def next_booking_ref() -> str:
    sb = _client()
    res = sb.rpc("next_booking_ref", {}).execute()
    return res.data  # function returns text


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    sb = _client()
    res = sb.table("app_settings").select("value").eq("key", key).limit(1).execute()
    if res.data and res.data[0].get("value") is not None:
        return res.data[0]["value"]
    return default


def save_appointment_request(
    *,
    booking_ref: str,
    service_code: str,
    service_name: str,
    service_price_pence: int,
    duration_minutes: int,
    requested_ranges: str,
    title: Optional[str],
    first_name: str,
    last_name: str,
    date_of_birth: Optional[date],
    email: str,
    phone: str,
    reason_for_visit: Optional[str],
    call_sid: Optional[str],
    during_hours: bool = False,
    transfer_attempted: bool = False,
    transfer_succeeded: bool = False,
) -> "BookingResult":
    """Inserts an appointment REQUEST (not a hard booking) — date/time intentionally
    null because we don't have Meddbase calendar access. The team manually schedules
    using `requested_ranges` as the caller's preferred availability."""
    sb = _client()
    try:
        res = (
            sb.table("bookings")
            .insert(
                {
                    "booking_ref": booking_ref,
                    "service_code": service_code,
                    "service_name": service_name,
                    "service_price_pence": service_price_pence,
                    "duration_minutes": duration_minutes,
                    "requested_ranges": requested_ranges,
                    "title": title,
                    "first_name": first_name,
                    "last_name": last_name,
                    "date_of_birth": date_of_birth.isoformat() if date_of_birth else None,
                    "email": email,
                    "phone": phone,
                    "reason_for_visit": reason_for_visit,
                    "call_sid": call_sid,
                    "status": "pending",
                    "during_hours": during_hours,
                    "transfer_attempted": transfer_attempted,
                    "transfer_succeeded": transfer_succeeded,
                }
            )
            .execute()
        )
        if res.data:
            return BookingResult(success=True, booking_ref=booking_ref, error=None)
    except Exception as e:
        return BookingResult(success=False, booking_ref=None, error=f"db_error: {e}")
    return BookingResult(success=False, booking_ref=None, error="db_error: empty response")


def log_escalation(
    *,
    caller_phone: str,
    callback_phone: str,
    reason: str,
    during_hours: bool,
    transferred: bool,
    call_sid: Optional[str] = None,
) -> Optional[str]:
    sb = _client()
    try:
        res = (
            sb.table("escalations")
            .insert(
                {
                    "caller_phone": caller_phone,
                    "callback_phone": callback_phone,
                    "reason": reason,
                    "during_hours": during_hours,
                    "transferred": transferred,
                    "call_sid": call_sid,
                }
            )
            .execute()
        )
        if res.data:
            return res.data[0].get("id")
    except Exception:
        return None
    return None


def patch_escalation(
    escalation_id: str,
    *,
    callback_phone: Optional[str] = None,
    transferred: Optional[bool] = None,
    reason: Optional[str] = None,
) -> bool:
    sb = _client()
    updates: dict = {}
    if callback_phone is not None:
        updates["callback_phone"] = callback_phone
    if transferred is not None:
        updates["transferred"] = transferred
    if reason is not None:
        updates["reason"] = reason
    if not updates:
        return True
    try:
        sb.table("escalations").update(updates).eq("id", escalation_id).execute()
        return True
    except Exception:
        return False


def try_book_slot(
    *,
    booking_ref: str,
    service_code: str,
    service_name: str,
    service_price_pence: int,
    appointment_date: date,
    appointment_time: time,
    duration_minutes: int,
    title: Optional[str],
    first_name: str,
    last_name: str,
    date_of_birth: Optional[date],
    email: str,
    phone: str,
    reason_for_visit: Optional[str],
    call_sid: Optional[str],
) -> BookingResult:
    sb = _client()
    payload = {
        "p_booking_ref": booking_ref,
        "p_service_code": service_code,
        "p_service_name": service_name,
        "p_service_price_pence": service_price_pence,
        "p_appointment_date": appointment_date.isoformat(),
        "p_appointment_time": appointment_time.strftime("%H:%M:%S"),
        "p_duration_minutes": duration_minutes,
        "p_title": title,
        "p_first_name": first_name,
        "p_last_name": last_name,
        "p_date_of_birth": date_of_birth.isoformat() if date_of_birth else None,
        "p_email": email,
        "p_phone": phone,
        "p_reason_for_visit": reason_for_visit,
        "p_call_sid": call_sid,
    }
    try:
        res = sb.rpc("try_book_slot", payload).execute()
    except Exception as e:  # network / supabase error
        return BookingResult(success=False, booking_ref=None, error=f"db_error: {e}")

    rows = res.data or []
    if not rows:
        return BookingResult(success=False, booking_ref=None, error="db_error: empty response")

    row = rows[0]
    return BookingResult(
        success=bool(row.get("success")),
        booking_ref=row.get("booking_ref"),
        error=row.get("error"),
    )
