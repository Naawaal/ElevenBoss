"""Ensure closing $function$ tags are followed by semicolons in 088."""
from __future__ import annotations

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "088_rarity_potential_guards.sql"
text = path.read_text(encoding="utf-8")
# Only closing tags: preceded by END; newline then $function$
text = text.replace("END;\n$function$\n", "END;\n$function$;\n")
text = text.replace("END;\n$function$\r\n", "END;\n$function$;\n")
path.write_text(text, encoding="utf-8")
print("closing tags with semicolon:", text.count("END;\n$function$;"))
