# packages/match_engine/match_engine/commentary_engine.py
from __future__ import annotations
import os
import json
import random

class CommentaryEngine:
    def __init__(self) -> None:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        json_path = os.path.join(dir_path, "commentary_bank.json")
        with open(json_path, "r", encoding="utf-8") as f:
            self.bank = json.load(f)

    def get_commentary(self, event_type: str, match_context: list[str] | set[str], variables: dict[str, str]) -> dict[str, str]:
        """Filters commentary templates by active context tags, resolving format placeholders."""
        templates = self.bank.get(event_type, [])
        if not templates:
            return {"text": "A standard phase play unfolds.", "urgency": "routine"}

        context_set = set(match_context)

        # 1. Look for templates matching specific context tags
        matching = []
        for t in templates:
            t_tags = set(t["tags"])
            if t_tags != {"generic"} and t_tags.issubset(context_set):
                matching.append(t)

        # 2. Fall back to generic tags if no specific tags matched
        if not matching:
            matching = [t for t in templates if "generic" in t["tags"]]

        # 3. Final fallback: choose any template available
        if not matching:
            matching = templates

        selected = random.choice(matching)
        formatted_text = selected["text"].format(**variables)
        return {
            "text": formatted_text,
            "urgency": selected["urgency"]
        }
