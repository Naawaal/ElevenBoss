import logging
from app.services.friendly_service import FriendlyMatchReport

logger = logging.getLogger("app.ui.renderers.friendly_live_renderer")

class FriendlyLiveRenderer:

    @staticmethod
    def get_score_at_minute(report: FriendlyMatchReport, minute: int) -> tuple[int, int]:
        """
        Calculates the score at a specific minute by counting the goal events up to that minute.
        """
        home_score = 0
        away_score = 0
        for event in report.timeline:
            if event.get("minute", 0) <= minute and event.get("type") == "goal":
                event_club_id = str(event.get("club_id", ""))
                if event_club_id == str(report.home_club_id):
                    home_score += 1
                elif event_club_id == str(report.away_club_id):
                    away_score += 1
        return home_score, away_score

    @staticmethod
    def render_progressive_events(report: FriendlyMatchReport, revealed_until_minute: int) -> str:
        """
        Formats the progressive timeline up to the given minute.
        """
        lines = []
        for event in report.timeline:
            minute = event.get("minute", 0)
            if minute > revealed_until_minute:
                continue

            etype = event.get("type", "generic")
            desc = event.get("description", "")
            
            # Map type to correct emoji
            prefix = "⏱️"
            if etype == "match_start":
                prefix = "📢"
            elif etype == "half_time":
                prefix = "⏸️"
            elif etype == "full_time":
                prefix = "🏁"
            elif etype == "goal":
                prefix = "⚽"
            elif etype in ("yellow_card", "yellow"):
                prefix = "🟨"
            elif etype in ("red_card", "red"):
                prefix = "🟥"
            elif etype == "substitution":
                prefix = "🔄"
            elif etype == "injury":
                prefix = "🚑"

            lines.append(f"• **{minute}'** {prefix} {desc}")
            
        if not lines:
            return "• No significant events occurred in this match."
        return "\n".join(lines)

    @staticmethod
    def render_progressive_stats(report: FriendlyMatchReport, minute: int) -> str:
        """
        Formats progressive stats up to the given minute.
        Possession is kept steady/final, while shots/SOT are scaled proportionally.
        """
        # If match hasn't started or is starting (0'), show zero stats
        if minute <= 0:
            return (
                "📊 **Match Stats**\n"
                "• **Possession:** 50% vs 50%\n"
                "• **Shots:** 0 vs 0\n"
                "• **Shots on Target:** 0 vs 0\n"
            )
            
        ratio = min(1.0, minute / 90.0)
        
        home_shots = int(report.home_shots * ratio)
        away_shots = int(report.away_shots * ratio)
        home_sot = int(report.home_shots_on_target * ratio)
        away_sot = int(report.away_shots_on_target * ratio)
        
        # Ensure shots on target doesn't exceed total shots
        home_sot = min(home_sot, home_shots)
        away_sot = min(away_sot, away_shots)
        
        title = "📊 **Half-Time Stats**\n" if minute == 45 else "📊 **Match Stats**\n"
        
        return (
            f"{title}"
            f"• **Possession:** {report.home_possession}% vs {report.away_possession}%\n"
            f"• **Shots:** {home_shots} vs {away_shots}\n"
            f"• **Shots on Target:** {home_sot} vs {away_sot}"
        )
