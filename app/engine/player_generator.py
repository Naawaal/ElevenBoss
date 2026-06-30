import random
import uuid
from app.models.player import Player
from app.engine.ratings import calculate_player_value, calculate_player_wage

FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles",
    "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
    "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey", "Ryan",
    "Jacob", "Gary", "Nicholas", "Eric", "Jonathan", "Stephen", "Larry", "Justin", "Scott", "Brandon",
    "Benjamin", "Samuel", "Gregory", "Alexander", "Frank", "Patrick", "Raymond", "Jack", "Dennis", "Jerry"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts"
]

TRAITS_LIST = [
    "leader", "pacey", "clinical_finisher", "playmaker", "ball_winner",
    "aerial_threat", "injury_prone", "consistent", "big_game_player", "one_club_player"
]

POSITIONS_DISTRIBUTION = [
    # GK: 3
    "GK", "GK", "GK",
    # DEF: 8
    "CB", "CB", "CB", "CB",
    "LB", "RB", "LWB", "RWB",
    # MID: 8
    "CDM", "CDM",
    "CM", "CM", "CM",
    "CAM", "LM", "RM",
    # ATT: 6
    "LW", "RW",
    "ST", "ST", "ST",
    "CF"
]

def generate_player(guild_id: str, club_id: uuid.UUID | None, position: str, overall: int) -> Player:
    """
    Procedurally generate a single player with given position and overall rating.
    """
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    display_name = f"{first_name} {last_name}"
    
    # Generate age with weighted ranges
    # 40% young prospect, 40% prime/developing, 15% experienced, 5% veteran
    age_roll = random.random()
    if age_roll < 0.40:
        age = random.randint(18, 21)
        # Young players get higher potential gap
        potential_gap = random.randint(8, 20)
    elif age_roll < 0.80:
        age = random.randint(22, 27)
        potential_gap = random.randint(3, 12)
    elif age_roll < 0.95:
        age = random.randint(28, 32)
        potential_gap = random.randint(1, 5)
    else:
        age = random.randint(33, 36)
        potential_gap = random.randint(0, 2)
        
    potential = min(88, overall + potential_gap)
    # Ensure potential is at least equal to overall
    if potential < overall:
        potential = overall
        
    value = calculate_player_value(overall, potential, age)
    wage = calculate_player_wage(overall, age)
    
    # Preferred foot
    preferred_foot = "Left" if random.random() < 0.25 else "Right"
    
    # Weak foot and skill moves (GK usually has low skill moves)
    weak_foot = random.randint(1, 5)
    if position == "GK":
        skill_moves = 1
    else:
        skill_moves = random.randint(1, 5)
        
    # Traits (0-2 traits)
    num_traits = random.choices([0, 1, 2], weights=[0.6, 0.3, 0.1])[0]
    assigned_traits = random.sample(TRAITS_LIST, num_traits) if num_traits > 0 else []
    traits = {"list": assigned_traits}
    
    return Player(
        guild_id=guild_id,
        club_id=club_id,
        first_name=first_name,
        last_name=last_name,
        display_name=display_name,
        position=position,
        age=age,
        overall=overall,
        potential=potential,
        value=value,
        wage=wage,
        fitness=100,
        sharpness=50,
        morale=75,
        preferred_foot=preferred_foot,
        weak_foot=weak_foot,
        skill_moves=skill_moves,
        traits=traits,
        is_retired=False
    )

def generate_squad(guild_id: str, club_id: uuid.UUID | None) -> list[Player]:
    """
    Generate a full squad of 25 balanced players.
    """
    # 1 Star: 72-78
    # 4 Key: 66-71
    # 12 Rotation: 60-65
    # 8 Prospects: 48-59
    overalls = (
        [random.randint(72, 78)] +
        [random.randint(66, 71) for _ in range(4)] +
        [random.randint(60, 65) for _ in range(12)] +
        [random.randint(48, 59) for _ in range(8)]
    )
    
    # Shuffle overalls and assign to positions
    random.shuffle(overalls)
    
    players = []
    for pos, ovr in zip(POSITIONS_DISTRIBUTION, overalls):
        players.append(generate_player(guild_id, club_id, pos, ovr))
        
    return players
