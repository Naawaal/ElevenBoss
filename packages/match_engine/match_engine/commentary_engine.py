# packages/match_engine/match_engine/commentary_engine.py
"""
Commentary engine that loads templates from commentary_bank.json and hydrates
them with match-state context variables.

Thread Safety:
    Accepts an optional ``rng`` parameter (random.Random instance) to avoid
    touching global random state.  Falls back to the module-level ``random``
    module for backwards compatibility with callers that don't supply one.
"""
from __future__ import annotations

import os
import json
import random


class CommentaryEngine:
    def __init__(self) -> None:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        json_path = os.path.join(dir_path, "commentary_bank.json")
        with open(json_path, "r", encoding="utf-8") as f:
            self.bank: dict = json.load(f)

    def get_commentary(
        self,
        event_type: str,
        match_context: list[str] | set[str],
        variables: dict[str, str],
        rng: random.Random | None = None,
    ) -> dict[str, str]:
        """
        Select and hydrate a commentary template for the given event type.

        Args:
            event_type:    EventType string (e.g. "GOAL", "SAVE", "CHANCE").
            match_context: Active context tags from MatchState.context_tags.
            variables:     Template placeholder values (e.g. {"actor": ..., "team": ...}).
            rng:           Optional thread-safe Random instance.  When provided,
                           all random selection uses this instead of global state.
                           Defaults to ``None`` → module-level ``random.choice()``.

        Returns:
            {"text": str, "urgency": str}
        """
        templates = self.bank.get(event_type, [])
        if not templates:
            return {"text": "A standard phase play unfolds.", "urgency": "routine"}

        context_set = set(match_context)

        # 1. Look for templates matching specific context tags
        matching = [
            t for t in templates
            if set(t["tags"]) != {"generic"} and set(t["tags"]).issubset(context_set)
        ]

        # 2. Fall back to generic tags if no specific tags matched
        if not matching:
            matching = [t for t in templates if "generic" in t["tags"]]

        # 3. Final fallback: choose any template available
        if not matching:
            matching = templates

        # Thread-safe selection
        if rng is not None:
            selected = rng.choice(matching)
        else:
            selected = random.choice(matching)

        formatted_text = selected["text"].format(**variables)
        return {
            "text": formatted_text,
            "urgency": selected["urgency"],
        }
