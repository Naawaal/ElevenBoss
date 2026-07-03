# Milestone — Season Completion & Season Reset Foundation

This milestone implements the lifecycle of season-to-season progression. When a season concludes:
1. Historical standings and statistics are archived.
2. The champions are announced.
3. Users can view the final standings and a summary.
4. Admins can manually prepare the league and trigger Season 2+ registrations.

---

## Architecture and Components

### 1. Database Model (`SeasonSnapshot`)
A new database table `season_snapshots` was introduced to permanently archive finished standings:
- **`season_id`**: Reference to the completed season.
- **`league_id`**: Reference to the league.
- **`champion_club_id`** / **`runner_up_club_id`**: References to the top two clubs.
- **`final_table_json`**: Normalized standings JSON dump.
- **`total_matches`** & **`total_goals`**: League statistics aggregate.
- **`completed_at`**: Timestamp.

### 2. Season Completion Flow
- **`SeasonCompletionService.save_final_snapshot`**: Integrates into the season completion transaction. It generates standings data, computes goals, maps champion and runner-up details, and stores the snapshot.
- **`AnnouncementService.announce_season_complete`**: Displays a custom message to the public channel with Components V2 buttons to **🏆 View Final Table**, **🏆 View Champion Club**, and **📊 View Season Summary**.

### 3. Season Summary UI Screen
- **`build_season_summary_layout`**: Implements a retro monospace standings overview card for completed seasons:
  ```yaml
  ╔══╦═══════════════╦══╦══╦══╦══╦═══╦═══╗
  ║R ║ CLUB          ║P ║W ║D ║L ║GD ║PTS║
  ╠══╬═══════════════╬══╬══╬══╬══╬═══╬═══╣
  ║1 ║ Pokhara City  ║14║10║2 ║2 ║+23║32 ║
  ║2 ║ Kathmandu FC  ║14║8 ║3 ║3 ║+13║27 ║
  ╚══╩═══════════════╩══╩══╩══╩══╩═══╩═══╝
  ```
- Handled by `handle_view_season_summary` and routed through the global button click listener.

### 4. Season Reset Service
- **`SeasonResetService.prepare_next_season`**: Allows admins to prepare for Season N+1. It transitions the completed league status back to `DRAFT`, creates the next season record in `DRAFT` status, and keeps all existing squads/clubs intact.
- **`start_league`**: Dynamically looks up any existing `DRAFT` season created by the reset handler, activating it upon start.
