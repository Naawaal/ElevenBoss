# Research Plan: Club Facilities Comprehension (Youth Academy & Training Ground)

## Research Questions
1. **Terminology Comprehension:** How do users currently interpret game-specific jargon like "Intake POT cap", "OVR range", and "Drill XP bonus"?
2. **Value Proposition Visibility:** Why do users feel they don't understand the use of the facilities despite the current embed text descriptions?
3. **Information Formatting:** What UI/UX approach (e.g., visual progress bars, before/after comparison tables, tooltips, or FAQ buttons) most effectively communicates the long-term ROI of facility upgrades on Discord?

## Methods
| Method | Questions Addressed | Participants | Timeline |
|--------|-------------------|-------------|----------|
| **Think-aloud Usability Testing** | Q1, Q2 | 5 active players (mixed experience levels) | Week 1 |
| **Concept / A-B Testing** | Q3 | 10 active players | Week 2 |
| **Brief User Interviews** | Q1, Q2, Q3 | 3 new players (unfamiliar with sports sims) | Week 1 |

## Inclusion Considerations
- **Participant Diversity:** We will recruit both veteran players (familiar with football sim mechanics) and complete beginners to ensure the terminology isn't acting as a gatekeeper.
- **Method Accessibility:** Testing will be conducted directly via Discord screenshare, matching the native environment where the bot is used. Mobile vs Desktop views must both be tested since Discord formats embeds differently on smaller screens.
- **Situational Contexts:** Testing will observe users who skim text rapidly to see if they miss the facility benefits completely, simulating real-world impatience.

## Expected Outputs
- **Findings Report:** Documenting the specific terms that confuse players.
- **Redesign Mockups:** Alternative UI representations for the `StoreFacilitiesHub` (e.g., separating stats into more legible tables or adding "What does this do?" buttons).
- **Revised Copywriting Guide:** A standardized way to explain POT, OVR, and XP bonuses.

## Decision Points
- Should we replace the plain text descriptions with a visual breakdown of benefits?
- Do we need to add an interactive "Info/Help" button (`[❓ What is the Youth Academy?]`) to the facilities view?
- Should the game obscure complex stats (like POT caps) behind simpler terms for newer players?
