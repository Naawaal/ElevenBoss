# packages/match_engine/match_engine/commentary.py
from __future__ import annotations
import random
from .models import MatchEvent, EventType, MatchResult

def generate_match_script(result: MatchResult, home_team: str = "Home Team", away_team: str = "Away Team") -> list[MatchEvent]:
    """Stateless generator that creates a timeline of 5 to 7 chronological match events

    ending with the simulated match score. Returns pure text strings.
    """
    goals_home = result.goals_for
    goals_away = result.goals_against
    total_goals = goals_home + goals_away
    
    # 3 to 4 filler events
    num_fillers = random.randint(3, 4)
    total_middle_events = total_goals + num_fillers
    
    # Choose unique minutes for middle events
    minutes = sorted(random.sample(range(5, 88), total_middle_events))
    
    # Distribute event types across the minutes
    types_pool = (
        ["goal_home"] * goals_home +
        ["goal_away"] * goals_away +
        ["filler"] * num_fillers
    )
    random.shuffle(types_pool)
    
    events: list[MatchEvent] = []
    
    # Add Kickoff
    events.append(MatchEvent(
        minute=0,
        type=EventType.KICKOFF,
        text=f"Kickoff! The match between {home_team} and {away_team} is underway.",
        score_update="0 - 0"
    ))
    
    current_home_score = 0
    current_away_score = 0
    
    goal_texts = [
        "GOAL! {team} scores! A sensational team move finished off with clinical precision.",
        "GOAL! {team} takes their chance! A thunderous shot from the edge of the box flies into the top corner.",
        "GOAL! {team} hits the back of the net! A pinpoint cross is met with a bullet header.",
        "GOAL! {team} makes it count! A mistake in defence is ruthlessly punished."
    ]

    miss_texts = [
        "A speculative shot from {team} flies high and wide of the goal.",
        "Great chance for {team}, but the striker rushes the shot and pulls it wide.",
        "{team} attempts an ambitious volley from distance, but it sails harmlessly out for a goal kick.",
        "A free-kick in a promising position for {team} hits the defensive wall."
    ]

    save_texts = [
        "What a save! The goalkeeper for {opponent} pulls off a spectacular diving save to deny {team}!",
        "Great reflex save! {opponent}'s keeper blocks a close-range header from the {team} attack.",
        "{team} is denied! {opponent}'s goalkeeper comes out off their line to smother the ball.",
        "The shot is on target for {team}, but {opponent}'s goalkeeper claims it cleanly."
    ]

    card_texts = [
        "Yellow card! The referee cautions a {team} player for a late challenge.",
        "A tactical foul by {team} results in a booking.",
        "Tempers flare after a rough tackle, and a {team} player receives a yellow card.",
        "The referee warns a {team} defender with a yellow card after persistent fouling."
    ]

    for i, minute in enumerate(minutes):
        ev_type = types_pool[i]
        
        if ev_type == "goal_home":
            current_home_score += 1
            text = random.choice(goal_texts).format(team=home_team)
            events.append(MatchEvent(
                minute=minute,
                type=EventType.GOAL,
                text=text,
                score_update=f"{current_home_score} - {current_away_score}"
            ))
        elif ev_type == "goal_away":
            current_away_score += 1
            text = random.choice(goal_texts).format(team=away_team)
            events.append(MatchEvent(
                minute=minute,
                type=EventType.GOAL,
                text=text,
                score_update=f"{current_home_score} - {current_away_score}"
            ))
        else:
            # Filler event (MISS, SAVE, YELLOW_CARD)
            filler_choice = random.choice([EventType.MISS, EventType.SAVE, EventType.YELLOW_CARD])
            if filler_choice == EventType.MISS:
                text = random.choice(miss_texts).format(team=random.choice([home_team, away_team]))
            elif filler_choice == EventType.SAVE:
                attacker = random.choice([home_team, away_team])
                defender = away_team if attacker == home_team else home_team
                text = random.choice(save_texts).format(team=attacker, opponent=defender)
            else:
                text = random.choice(card_texts).format(team=random.choice([home_team, away_team]))
                
            events.append(MatchEvent(
                minute=minute,
                type=filler_choice,
                text=text,
                score_update=f"{current_home_score} - {current_away_score}"
            ))
            
    # Add Full Time
    events.append(MatchEvent(
        minute=90,
        type=EventType.FULL_TIME,
        text=f"The referee blows the final whistle! Full time: {home_team} {current_home_score} - {current_away_score} {away_team}.",
        score_update=f"{current_home_score} - {current_away_score}"
    ))
    
    return events
