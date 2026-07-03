from dataclasses import dataclass

KNOWN_SCOPES = {"locker", "squad", "player", "nav", "lineup", "league", "table", "fixtures", "matchday", "match", "setup", "automation", "schedule", "settings", "admin", "dm_settings", "dm_admin", "onboarding", "season", "friendly", "facility", "training"}
KNOWN_ACTIONS = {"open", "view", "page", "back", "close", "refresh", "help", "formation", "auto", "save", "join", "start", "view_table", "week", "prev", "next", "generate", "run", "recent", "status", "toggle", "run_now", "run_check", "go_schedule", "go_league", "automation", "matchday_run", "automation_check", "enable", "disable", "guild_select", "switch", "channel_game", "channel_match", "role_admin", "league_start", "extend_deadline", "cancel_league", "open_modal", "edit", "save_modal", "club_name", "finish", "prepare_next_season", "view_summary", "accept", "decline", "practice", "simulate", "skip", "cancel", "upgrade", "set_intensity", "set_default_plan", "open_plans_page", "set_player_plan", "open_condition_page", "open_outlook_page"}





@dataclass(frozen=True)
class CustomId:
    namespace: str
    version: str
    scope: str
    action: str
    target: str
    nonce: str

    def __post_init__(self):
        if self.namespace != "fcm":
            raise ValueError(f"Invalid namespace: {self.namespace}")
        if self.version != "v1":
            raise ValueError(f"Unsupported version: {self.version}")
        if self.scope not in KNOWN_SCOPES:
            raise ValueError(f"Unknown scope: {self.scope}")
        if self.action not in KNOWN_ACTIONS:
            raise ValueError(f"Unknown action: {self.action}")
        if not self.target:
            raise ValueError("Target cannot be empty")
        if not self.nonce:
            raise ValueError("Nonce cannot be empty")
        
        # Verify length limit
        full_str = f"{self.namespace}:{self.version}:{self.scope}:{self.action}:{self.target}:{self.nonce}"
        if len(full_str) > 100:
            raise ValueError(f"Custom ID length ({len(full_str)}) exceeds Discord limit of 100 characters")

def encode_custom_id(scope: str, action: str, target: str, nonce: str) -> str:
    """
    Encode custom_id into the versioned colon-separated FCM format.
    """
    t = target if target else "_"
    n = nonce if nonce else "_"
    
    # Instantiate CustomId dataclass to run validations
    custom_id_obj = CustomId(
        namespace="fcm",
        version="v1",
        scope=scope,
        action=action,
        target=t,
        nonce=n
    )
    return f"fcm:v1:{custom_id_obj.scope}:{custom_id_obj.action}:{custom_id_obj.target}:{custom_id_obj.nonce}"

def decode_custom_id(custom_id_str: str) -> CustomId:
    """
    Parse a custom_id string and return a verified CustomId object.
    Raises ValueError on malformed or invalid inputs.
    """
    if not custom_id_str:
        raise ValueError("Empty custom_id string")
        
    parts = custom_id_str.split(":")
    if len(parts) != 6:
        raise ValueError(f"Malformed custom_id, expected 6 segments, got {len(parts)}: '{custom_id_str}'")
        
    return CustomId(
        namespace=parts[0],
        version=parts[1],
        scope=parts[2],
        action=parts[3],
        target=parts[4],
        nonce=parts[5]
    )
