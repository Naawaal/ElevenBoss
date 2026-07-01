import secrets
from datetime import datetime, timedelta
from dataclasses import dataclass, field

@dataclass
class UiSession:
    session_id: str
    discord_user_id: int
    guild_id: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=15))
    metadata: dict = field(default_factory=dict)

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def refresh(self, duration_minutes: int = 15):
        self.expires_at = datetime.utcnow() + timedelta(minutes=duration_minutes)

class SessionManager:
    def __init__(self):
        self._sessions: dict[str, UiSession] = {}

    def create_session(self, discord_user_id: int, guild_id: int, metadata: dict | None = None) -> UiSession:
        """
        Creates a new interactive UI session and registers it.
        """
        self.cleanup_expired()
        
        # Generate a unique 6-character hex nonce
        nonce = secrets.token_hex(3)
        while nonce in self._sessions:
            nonce = secrets.token_hex(3)
            
        session = UiSession(
            session_id=nonce,
            discord_user_id=int(discord_user_id),
            guild_id=int(guild_id),
            metadata=metadata or {}
        )
        self._sessions[nonce] = session
        return session

    def get_session(self, nonce: str) -> UiSession | None:
        """
        Retrieves a session if it exists and is not expired.
        """
        session = self._sessions.get(nonce)
        if session and session.is_expired():
            self._sessions.pop(nonce, None)
            return None
        return session

    def validate_session(self, nonce: str, discord_user_id: int) -> tuple[bool, str]:
        """
        Validates if a session exists, is not expired, and belongs to the user.
        Returns (success, error_message).
        """
        session = self.get_session(nonce)
        if not session:
            return False, "This UI session has expired or is invalid. Please run the command again."
        
        if session.discord_user_id != int(discord_user_id):
            return False, "You do not own this interactive menu. Please run the command to open your own."
            
        # Refresh sliding expiration
        session.refresh()
        return True, ""

    def cleanup_expired(self):
        """
        Removes all expired sessions from memory.
        """
        expired_keys = [k for k, s in self._sessions.items() if s.is_expired()]
        for k in expired_keys:
            self._sessions.pop(k, None)

# Global singleton session manager
ui_session_manager = SessionManager()
