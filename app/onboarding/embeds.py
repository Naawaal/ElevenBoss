"""
Components V2 payload builders for each onboarding step.
All functions return a list[dict] suitable for wrapping in V2View.
"""
import uuid
from app.ui.components import container, text_display, separator, action_row, primary_button, success_button
from app.onboarding.steps import OnboardingStep, step_number, total_visible_steps
from app.onboarding.custom_ids import make_next_id, make_club_name_id, make_finish_id


def _footer(current_step: str) -> str:
    num = step_number(current_step)
    total = total_visible_steps()
    if num == 0:
        return ""
    return f"-# Step {num} of {total}"


def build_welcome(session_id: uuid.UUID) -> list[dict]:
    """Step 1 – Welcome screen."""
    return [
        container([
            text_display(
                "## ⚽ Welcome to ElevenBoss!\n\n"
                "ElevenBoss is a football management game right here in Discord. "
                "You'll **build and manage your own football club**, sign players, set lineups, "
                "and compete in automated leagues against other managers.\n\n"
                "This short setup will get your club registered in under a minute."
            ),
            separator(divider=False, spacing=1),
            text_display(_footer(OnboardingStep.WELCOME)),
            action_row([
                primary_button(
                    "Let's Go →",
                    custom_id=make_next_id(session_id, OnboardingStep.WELCOME),
                )
            ]),
        ])
    ]


def build_explain_clubs(session_id: uuid.UUID) -> list[dict]:
    """Step 2 – Explain what a club is."""
    return [
        container([
            text_display(
                "## 🏟️ Your Club\n\n"
                "Your **club** is your team in ElevenBoss. Here's what you get when you register:\n\n"
                "- 🧑‍🤝‍🧑 **25 players** — automatically generated, each with unique stats and positions\n"
                "- 💰 **Starting budget** of £10,000,000 to sign and sell players\n"
                "- 📋 **Lineup control** — set your formation and pick your starting XI\n"
                "- 🏆 **League play** — join a league draft and compete for the title\n\n"
                "Once registered, use `/squad` to view your players and `/lineup` to set your formation."
            ),
            separator(divider=False, spacing=1),
            text_display(_footer(OnboardingStep.EXPLAIN_CLUBS)),
            action_row([
                primary_button(
                    "Name My Club →",
                    custom_id=make_next_id(session_id, OnboardingStep.EXPLAIN_CLUBS),
                )
            ]),
        ])
    ]


def build_collect_club_name(session_id: uuid.UUID, error: str | None = None) -> list[dict]:
    """Step 3 – Prompt the user to enter their club name via modal."""
    error_block = ""
    if error:
        error_block = f"\n\n> ⚠️ **{error}** — please try a different name."
    return [
        container([
            text_display(
                "## 📝 Name Your Club\n\n"
                "Choose a unique name for your club. It must be **3–40 characters** and can contain "
                "letters, numbers, spaces, hyphens, apostrophes, and periods.\n\n"
                "*Examples: Arsenal FC, Red Lions, City United, FC Nairobi*"
                + error_block
            ),
            separator(divider=False, spacing=1),
            text_display(_footer(OnboardingStep.COLLECT_CLUB_NAME)),
            action_row([
                primary_button(
                    "Enter Club Name",
                    custom_id=make_club_name_id(session_id),
                )
            ]),
        ])
    ]


def build_recruit_players(session_id: uuid.UUID, club_name: str) -> list[dict]:
    """Step 4 – Recruit your starting squad of 25 players."""
    return [
        container([
            text_display(
                f"## ⚽ Recruit Your Squad for **{club_name}**!\n\n"
                "You are ready to recruit your starting squad of **25 players**! "
                "The board has prepared a selection of talented players across all key positions:\n\n"
                "- 🧤 **Goalkeepers (GK)**\n"
                "- 🛡️ **Defenders (DF)**\n"
                "- ⚙️ **Midfielders (MF)**\n"
                "- 🎯 **Forwards (FW)**\n\n"
                "Click the button below to sign your players and reveal your initial roster!"
            ),
            separator(divider=False, spacing=1),
            text_display(_footer(OnboardingStep.RECRUIT_PLAYERS)),
            action_row([
                success_button(
                    "Recruit Players ⚽",
                    custom_id=make_finish_id(session_id),
                )
            ]),
        ])
    ]


def build_loading_screen(club_name: str) -> list[dict]:
    """Loading screen shown while players are being generated."""
    return [
        container([
            text_display(
                f"## 🤝 Recruiting starting squad for **{club_name}**...\n\n"
                "🔄 *Scouting talented players...*\n"
                "🔄 *Negotiating initial contracts...*\n"
                "🔄 *Assembling your 25-man roster...*\n\n"
                "-# Please wait a moment while the board finalizes the recruitment..."
            )
        ])
    ]


def build_success(club_name: str, players: list = None) -> list[dict]:
    """Completion screen shown after registration is finalised."""
    player_section = ""
    if players:
        gk_list = []
        df_list = []
        mf_list = []
        fw_list = []
        
        for p in players:
            pos = p.position if hasattr(p, "position") else p.get("position", "")
            ovr = p.overall if hasattr(p, "overall") else p.get("overall", 0)
            name = p.display_name if hasattr(p, "display_name") else p.get("display_name", "")
            
            p_str = f"**{name}** ({pos} {ovr})"
            
            if pos == "GK":
                gk_list.append(p_str)
            elif pos in ("CB", "LB", "RB"):
                df_list.append(p_str)
            elif pos in ("CM", "LM", "RM"):
                mf_list.append(p_str)
            elif pos in ("ST", "LW", "RW"):
                fw_list.append(p_str)
            else:
                mf_list.append(p_str)
        
        player_section = (
            "### 📋 Your Recruited Roster\n\n"
            f"🧤 **Goalkeepers**:\n"
            f"{', '.join(gk_list)}\n\n"
            f"🛡️ **Defenders**:\n"
            f"{', '.join(df_list)}\n\n"
            f"⚙️ **Midfielders**:\n"
            f"{', '.join(mf_list)}\n\n"
            f"🎯 **Forwards**:\n"
            f"{', '.join(fw_list)}\n"
        )
    else:
        player_section = "Your starting squad of 25 players has been generated."

    return [
        container([
            text_display(
                f"## 🎉 Welcome to ElevenBoss, Boss!\n\n"
                f"**{club_name}** has been registered successfully! Here are the players signed by your board:\n\n"
                f"{player_section}\n"
                "Use `/locker` to open your club dashboard, `/squad` to view complete stats, "
                "or `/lineup` to set your starting XI.\n\n"
                "*This setup thread will close automatically in a few seconds.*"
            ),
        ])
    ]


def build_name_taken_retry(session_id: uuid.UUID, taken_name: str) -> list[dict]:
    """Error screen when the club name is taken at the point of completion."""
    return [
        container([
            text_display(
                f"## ❌ Club Name Taken\n\n"
                f"**{taken_name}** is already registered in this server.\n\n"
                "Please go back and choose a different name."
            ),
            action_row([
                primary_button(
                    "← Choose a Different Name",
                    custom_id=make_club_name_id(session_id),
                )
            ]),
        ])
    ]


def build_nudge(session_id: uuid.UUID, current_step: str) -> list[dict]:
    """Inactivity nudge message sent to an idle session thread."""
    return [
        container([
            text_display(
                "⏰ **Still there?** Your registration session is still open.\n\n"
                "If you'd like to continue setting up your club, pick up where you left off — "
                "otherwise this thread will close automatically after a short while."
            ),
            action_row([
                primary_button(
                    "Continue Setup →",
                    custom_id=make_next_id(session_id, current_step),
                )
            ]),
        ])
    ]
