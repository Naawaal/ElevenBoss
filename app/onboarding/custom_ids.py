"""
Onboarding-specific custom_id helpers.
All IDs use the standard fcm:v1 scheme with scope="onboarding".

Target format for onboarding IDs:
  fcm:v1:onboarding:<action>:<session_id_hex>:<step_or_marker>

Because session IDs are UUIDs (36 chars) and the total limit is 100 chars, we store
the full 32 hex chars of the session UUID as the target segment (no dashes).
This avoids needing to query the database to resolve short prefixes to full UUIDs
during interaction routing, preventing 3-second Discord timeouts.

Full format:  fcm:v1:onboarding:<action>:<session_hex>:<step>
Max length check:  5+3+10+12+32+15 = ~78 chars — well under 100.
"""
import uuid
from app.ui.custom_ids import encode_custom_id, decode_custom_id, CustomId


def _serialize_uuid(session_id: uuid.UUID) -> str:
    """Full 32 hex chars of the session UUID."""
    return str(session_id).replace("-", "")


def make_next_id(session_id: uuid.UUID, step: str) -> str:
    """Button custom_id to advance from `step` to the next step."""
    return encode_custom_id(
        scope="onboarding",
        action="next",
        target=_serialize_uuid(session_id),
        nonce=step[:16],  # step name fits within nonce field
    )


def make_club_name_id(session_id: uuid.UUID) -> str:
    """Button custom_id that opens the ClubNameModal."""
    return encode_custom_id(
        scope="onboarding",
        action="club_name",
        target=_serialize_uuid(session_id),
        nonce="modal",
    )


def make_finish_id(session_id: uuid.UUID) -> str:
    """Button custom_id for the final 'Finish Setup' button."""
    return encode_custom_id(
        scope="onboarding",
        action="finish",
        target=_serialize_uuid(session_id),
        nonce="go",
    )


def parse_onboarding_id(raw: str) -> tuple[str, uuid.UUID | str, str]:
    """
    Parse a raw custom_id string and return (action, session_id_or_short, nonce).
    For legacy buttons, target is the 8-character short session prefix (str).
    For new buttons, target is the full 32-character hex UUID (uuid.UUID).
    """
    cid: CustomId = decode_custom_id(raw)
    if cid.scope != "onboarding":
        raise ValueError(f"Not an onboarding custom_id: {raw!r}")
    
    if len(cid.target) == 8:
        # Legacy format short prefix
        return cid.action, cid.target, cid.nonce
        
    try:
        session_id = uuid.UUID(hex=cid.target)
        return cid.action, session_id, cid.nonce
    except ValueError:
        # Fallback to returning the target as string if not a valid UUID hex
        return cid.action, cid.target, cid.nonce
