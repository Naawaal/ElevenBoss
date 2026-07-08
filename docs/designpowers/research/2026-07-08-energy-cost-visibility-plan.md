# Research Plan: Energy Cost Visibility

## Research Questions
1. How do players currently discover and understand the action energy costs associated with matches and development drills before committing to an action?
2. Where in the Discord UI (embed descriptions, footers, or button labels) do players look for cost information?
3. How do screen readers interpret the "⚡" emoji, and is it accessible to visually impaired players?

## Methods
| Method | Questions Addressed | Participants | Timeline |
|--------|-------------------|-------------|----------|
| Contextual Inquiry & Think-Aloud | Q1, Q2 | 5-7 current Discord players | Week 1 |
| Accessibility Audit | Q3 | 1-2 players using screen readers (or tool simulation) | Week 1 |
| A/B Testing | Q1, Q2 | Discord server (split test groups) | Week 2 |

## Inclusion Considerations
- **Platform Diversity:** Testing must include both Discord Mobile and Discord Desktop users, as UI constraints and scannability differ greatly between them.
- **Accessibility:** Ensure the "⚡" emoji is evaluated for screen reader compatibility (e.g., does it read as "Energy", "Lightning bolt", or "High voltage sign"?). We may need to use explicit text like "Energy cost applies" alongside or instead of the emoji.
- **Player Experience:** Include both new users (who might not understand the energy system yet) and veterans (who are accustomed to the current UI).

## Expected Outputs
- A findings report detailing where users currently miss energy costs.
- Concrete UI recommendations on where to place the "⚡ Energy cost applies" label (e.g., standardized embed footer, inline text, or button text).

## Decision Points
- Whether to add a universal "⚡ Energy cost applies" warning to all actionable embeds or keep costs inline on buttons.
- Whether to adjust the current text (e.g., changing `15⚡` to `Costs 15 Energy ⚡`).
