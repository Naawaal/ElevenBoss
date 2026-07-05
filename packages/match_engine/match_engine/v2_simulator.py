# packages/match_engine/match_engine/v2_simulator.py
from __future__ import annotations
import random
from typing import AsyncGenerator
from pydantic import BaseModel, Field

class MatchState(BaseModel):
    home_rating: float
    away_rating: float
    home_score: int = 0
    away_score: int = 0
    minute: int = 0
    momentum: int = 0  # ranges from -100 (Away dominant) to 100 (Home dominant)
    home_tactics_modifier: float = 1.0
    context_tags: list[str] = Field(default_factory=list)

    def update_tags(self) -> None:
        tags = []
        # Time tags
        if self.minute <= 15:
            tags.append("early")
        elif self.minute >= 75:
            tags.append("late")

        # Score tags
        if self.home_score == self.away_score:
            tags.append("tied")
        elif self.home_score > self.away_score:
            tags.append("home_leading")
        else:
            tags.append("away_leading")

        # Momentum tags
        if self.momentum >= 50:
            tags.append("high_momentum")
        elif self.momentum <= -50:
            tags.append("low_momentum")

        self.context_tags = tags

async def stream_match(
    state: MatchState,
    home_squad: list,
    away_squad: list,
    home_name: str,
    away_name: str
) -> AsyncGenerator[dict, None]:
    """Async generator simulating the live match phase-by-phase."""
    state.update_tags()
    
    yield {
        "minute": 0,
        "type": "KICKOFF",
        "score_update": "0 - 0",
        "actor": "The referee",
        "team": home_name
    }

    while state.minute < 90:
        # Advance clock by random phase (6-12 mins)
        state.minute = min(90, state.minute + random.randint(6, 12))

        # Adjust momentum dynamically based on tactics & rating differentials
        base_diff = (state.home_rating * state.home_tactics_modifier) - state.away_rating
        state.momentum = max(-100, min(100, int(state.momentum + base_diff * 0.5 + random.uniform(-12.0, 12.0))))
        state.update_tags()

        # 60% chance of a phase event occurring (if not full time)
        if random.random() < 0.60 and state.minute < 90:
            # Determine actor team based on momentum bias
            is_home_event = (random.randint(-100, 100) + state.momentum) >= 0
            event_team = home_name if is_home_event else away_name
            event_squad = home_squad if is_home_event else away_squad
            opp_squad = away_squad if is_home_event else home_squad

            actor_card = random.choice(event_squad)
            actor_name = actor_card.name if hasattr(actor_card, "name") else actor_card.get("name", "Unknown Player")

            roll = random.random()
            assister_name = None
            if roll < 0.20:
                event_type = "GOAL"
                if is_home_event:
                    state.home_score += 1
                else:
                    state.away_score += 1
                other_players = [p for p in event_squad if (p.name if hasattr(p, "name") else p.get("name", "")) != actor_name]
                if other_players and random.random() < 0.70:
                    assister_card = random.choice(other_players)
                    assister_name = assister_card.name if hasattr(assister_card, "name") else assister_card.get("name", "Unknown Player")
            elif roll < 0.55:
                event_type = "MISS"
            elif roll < 0.80:
                event_type = "CHANCE"
            elif roll < 0.90:
                event_type = "FOUL"
                foul_actor = random.choice(opp_squad)
                actor_name = foul_actor.name if hasattr(foul_actor, "name") else foul_actor.get("name", "Opponent")
                event_team = away_name if is_home_event else home_name
            elif roll < 0.96:
                event_type = "YELLOW_CARD"
                foul_actor = random.choice(opp_squad)
                actor_name = foul_actor.name if hasattr(foul_actor, "name") else foul_actor.get("name", "Opponent")
                event_team = away_name if is_home_event else home_name
            else:
                event_type = "INJURY"
                injury_actor = random.choice(event_squad)
                actor_name = injury_actor.name if hasattr(injury_actor, "name") else injury_actor.get("name", "Unknown Player")

            event_data = {
                "minute": state.minute,
                "type": event_type,
                "score_update": f"{state.home_score} - {state.away_score}",
                "actor": actor_name,
                "team": event_team
            }
            if assister_name:
                event_data["assister"] = assister_name
            yield event_data

    # Yield FULL_TIME at 90'
    state.update_tags()
    yield {
        "minute": 90,
        "type": "FULL_TIME",
        "score_update": f"{state.home_score} - {state.away_score}",
        "actor": "The referee",
        "team": home_name
    }
