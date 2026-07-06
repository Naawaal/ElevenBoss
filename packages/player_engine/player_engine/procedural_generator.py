# packages/player_engine/player_engine/procedural_generator.py
"""Procedural squad and player generation."""
from __future__ import annotations

import random
import uuid
from random import Random

from ratings import calculate_player_value, calculate_player_wage

from .generated_player import GeneratedPlayer
from .potential import generate_potential

REGIONAL_NAME_POOLS = {
    "British": {
        "first_names": [
            "James", "John", "Robert", "Michael", "William", "David", "Richard",
            "Joseph", "Thomas", "Charles", "Christopher", "Daniel", "Matthew",
            "Anthony", "Mark", "Steven", "Paul", "Andrew", "Joshua", "Kenneth",
            "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward", "Jason",
            "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric", "Jonathan",
            "Stephen", "Larry", "Justin", "Scott", "Brandon", "Benjamin",
            "Samuel", "Gregory", "Alexander", "Frank", "Patrick", "Raymond",
            "Jack", "Dennis", "Jerry", "Harry",
        ],
        "last_names": [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis",
            "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson",
            "Martin", "Lee", "Thompson", "White", "Harris", "Clark", "Lewis",
            "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Scott",
            "Hill", "Green", "Adams", "Nelson", "Baker", "Hall", "Campbell",
            "Mitchell", "Carter", "Roberts", "Evans", "Turner", "Phillips",
            "Parker", "Collins", "Edwards", "Morris", "Rogers", "Reed", "Cook",
            "Morgan", "Bell", "Murphy",
        ],
    },
    "Spanish/Latin American": {
        "first_names": [
            "Mateo", "Santiago", "Matias", "Sebastian", "Alejandro", "Diego",
            "Samuel", "Benjamin", "Joaquin", "Gabriel", "Lucas", "Tomas",
            "Nicolas", "Daniel", "David", "Miguel", "Angel", "Francisco",
            "Jose", "Juan", "Carlos", "Luis", "Javier", "Andres", "Felipe",
            "Hugo", "Leo", "Enzo", "Thiago", "Manuel", "Marcos", "Adrian",
            "Alvaro", "Pablo", "Ruben", "Ivan", "Jorge", "Raul", "Fernando",
            "Pedro", "Hector", "Rafael", "Sergio", "Cristian", "Eduardo",
            "Victor", "Ignacio", "Julian", "Martin", "Agustin",
        ],
        "last_names": [
            "Garcia", "Fernandez", "Lopez", "Gonzalez", "Rodriguez", "Martinez",
            "Hernandez", "Perez", "Gomez", "Sanchez", "Diaz", "Alvarez",
            "Romero", "Ruiz", "Torres", "Flores", "Rivera", "Ramirez", "Cruz",
            "Guzman", "Ortiz", "Gutierrez", "Castro", "Salazar", "Vargas",
            "Herrera", "Medina", "Aguilar", "Munoz", "Silva", "Rojas", "Moreno",
            "Jimenez", "Alvarado", "Delgado", "Pena", "Valenzuela", "Ortega",
            "Guerrero", "Estrada", "Mendoza", "Rios", "Morales", "Suarez",
            "Cabrera", "Acosta", "Pinto", "Luna", "Miranda", "Fuentes",
        ],
    },
    "French": {
        "first_names": [
            "Hugo", "Lucas", "Leo", "Gabriel", "Timeo", "Enzo", "Louis",
            "Arthur", "Nathan", "Mathis", "Nolan", "Elio", "Mael", "Jules",
            "Alexis", "Antoine", "Romain", "Alexandre", "Maxime", "Paul",
            "Clement", "Julien", "Thomas", "Pierre", "Nicolas", "Quentin",
            "Maxence", "Theo", "Raphael", "Mathieu", "Bastien", "Guillaume",
            "Florian", "Valentin", "Benjamin", "Adrien", "Vincent", "Loic",
            "Alex", "Gautier", "Dorian", "Emile", "Robin", "Simon", "Olivier",
            "Marc", "Jean", "Damien", "Sebastien", "Francois",
        ],
        "last_names": [
            "Martin", "Bernard", "Thomas", "Petit", "Robert", "Richard",
            "Durand", "Dubois", "Moreau", "Laurent", "Simon", "Michel",
            "Lefevre", "Leroy", "Roux", "David", "Bertrand", "Morel",
            "Fournier", "Girard", "Bonnet", "Dupont", "Lambert", "Fontaine",
            "Rousseau", "Vincent", "Muller", "Lefevre", "Andre", "Guerin",
            "Boyer", "Chevalier", "Mercier", "Francois", "Denis", "Legrand",
            "Dufour", "Garnier", "Blanc", "Gauthier", "Morin", "Menard",
            "Mathieu", "Faure", "Aubert", "Robin", "Clement", "Dumont",
            "Brun", "Barbier",
        ],
    },
    "Nordic": {
        "first_names": [
            "Oliver", "Elias", "Emil", "Lucas", "Jakob", "Magnus", "Viktor",
            "Filip", "Oskar", "Aksel", "Noah", "Alexander", "William", "Ludvig",
            "Hugo", "Sebastian", "Isak", "Valdemar", "Alfred", "Karl", "Erik",
            "Johan", "Nils", "Anders", "Lars", "Sven", "Olaf", "Bjorn", "Thor",
            "Frederik", "Christian", "Mads", "Mikkel", "Jonas", "Rasmus",
            "Henrik", "Gustav", "Axel", "Sigurd", "Arvid", "Hakon", "Kristian",
            "Marcus", "Daniel", "Andreas", "Simon", "Stefan", "Peter", "Mikael",
            "Antti",
        ],
        "last_names": [
            "Andersson", "Johansson", "Karlsson", "Nilsson", "Eriksson",
            "Larsson", "Olsson", "Persson", "Svensson", "Gustafsson", "Hansen",
            "Pedersen", "Nielsen", "Jensen", "Olsen", "Larsen", "Christensen",
            "Rasmussen", "Andersen", "Petersen", "Sorensen", "Madsen", "Nygard",
            "Bakken", "Solberg", "Lie", "Ronneberg", "Ruud", "Engen", "Haugen",
            "Virtanen", "Korhonen", "Nieminen", "Laine", "Heikkinen", "Koskinen",
            "Jarvinen", "Lehtonen", "Lehtinen", "Saarinen", "Lindqvist",
            "Bergqvist", "Sandstrom", "Dahlstrom", "Sjoberg", "Nyqvist",
            "Lundgren", "Lindgren", "Lindstrom", "Holm",
        ],
    },
    "Balkan": {
        "first_names": [
            "Luka", "Ivan", "Marko", "David", "Petar", "Filip", "Nikola",
            "Aleksandar", "Stefan", "Milan", "Igor", "Goran", "Dragan", "Zoran",
            "Dejan", "Bojan", "Dusan", "Nemanja", "Uros", "Milos", "Matej",
            "Karlo", "Josip", "Antonio", "Marin", "Ante", "Dino", "Alen",
            "Adnan", "Haris", "Edin", "Tarik", "Amar", "Kenan", "Damir",
            "Mirza", "Emir", "Jasmin", "Denis", "Anes", "Andrej", "Bora",
            "Darko", "Miodrag", "Slobodan", "Vasil", "Hristo", "Dimitar",
            "Georgi", "Ivan",
        ],
        "last_names": [
            "Horvat", "Kovacevic", "Babic", "Maric", "Novak", "Petrovic",
            "Jovanovic", "Popovic", "Markovic", "Dordevic", "Stankovic",
            "Nikolic", "Ilic", "Kostic", "Milosevic", "Pavlovic", "Lukic",
            "Simic", "Mitrovic", "Lazarevic", "Hodzic", "Hadzic", "Kovac",
            "Delic", "Begic", "Halilovic", "Knezevic", "Vukovic", "Radic",
            "Tomasevic", "Kataric", "Blazevic", "Sutalo", "Gvardiol", "Modric",
            "Kovacic", "Brozovic", "Perisic", "Kramaric", "Livakovic", "Dzeko",
            "Pjanic", "Ibisevic", "Misimovic", "Begovic", "Spahic", "Lulic",
            "Visca", "Kolasinac", "Savic",
        ],
    },
    "West African": {
        "first_names": [
            "Samuel", "Emmanuel", "John", "David", "Daniel", "Victor",
            "Joseph", "Gift", "Kelechi", "Chidi", "Babajide", "Ibrahim",
            "Moussa", "Amadou", "Sadio", "Cheikh", "Boubacar", "Ousmane",
            "Kalidou", "Idrissa", "Aboubakar", "Karl", "Eric", "Chinedu",
            "Emeka", "Nnamdi", "Tobi", "Femi", "Segun", "Kunle", "Abiola",
            "Oluwaseun", "Kofi", "Kwame", "Yaw", "Kojo", "Mensah", "Abdoulaye",
            "Mamadou", "Sekou", "Lamine", "Bakary", "Demba", "Salif",
            "Mustapha", "Youssef", "Kassim", "Wilfried", "Serge", "Franck",
        ],
        "last_names": [
            "Obi", "Okeke", "Okafor", "Balogun", "Adebayo", "Mensah", "Owusu",
            "Diallo", "Sow", "Diop", "N'Diaye", "Traore", "Cisse", "Keita",
            "Koulibaly", "Mane", "Sarr", "Gueye", "Mendy", "Toure", "Drogba",
            "Zaha", "Kessie", "Aurier", "Bailly", "Choupo-Moting", "Anguissa",
            "Onana", "Aboubakar", "Eto'o", "Song", "Osimhen", "Ndidi",
            "Chukwueze", "Iwobi", "Lookman", "Iheanacho", "Musa", "Etebo",
            "Troost-Ekong", "Ayew", "Partey", "Kudus", "Salisu", "Amartey",
            "Gyan", "Boateng", "Appiah", "Essien", "Muntari",
        ],
    },
}

POSITIONS_DISTRIBUTION = [
    "GK", "GK", "GK",
    "CB", "CB", "CB", "CB",
    "LB", "RB", "LWB", "RWB",
    "CDM", "CDM",
    "CM", "CM", "CM",
    "CAM", "LM", "RM",
    "LW", "RW",
    "ST", "ST", "ST",
    "CF",
]


def _position_group(position: str) -> str:
    if position == "GK":
        return "GK"
    if position in {"CB", "LB", "RB", "LWB", "RWB", "DEF"}:
        return "DEF"
    if position in {"LW", "RW", "ST", "CF", "FWD"}:
        return "FWD"
    return "MID"


def _rarity_from_ovr(overall: int) -> str:
    if overall >= 85:
        return "Legendary"
    if overall >= 75:
        return "Epic"
    if overall >= 65:
        return "Rare"
    return "Common"


def generate_player(
    guild_id: str,
    club_id: uuid.UUID | None,
    position: str,
    overall: int,
    *,
    rng: Random | None = None,
) -> GeneratedPlayer:
    """Procedurally generate a single player with given position and overall rating."""
    r = rng if rng is not None else random.Random()

    nationality = r.choice(list(REGIONAL_NAME_POOLS.keys()))
    pool = REGIONAL_NAME_POOLS[nationality]

    first_name = r.choice(pool["first_names"])
    last_name = r.choice(pool["last_names"])
    display_name = f"{first_name} {last_name}"

    age_roll = r.random()
    if age_roll < 0.40:
        age = r.randint(18, 21)
    elif age_roll < 0.80:
        age = r.randint(22, 27)
    elif age_roll < 0.95:
        age = r.randint(28, 32)
    else:
        age = r.randint(33, 36)

    rarity = _rarity_from_ovr(overall)
    potential = generate_potential(
        overall, age, rarity, _position_group(position), rng=r
    )

    value = calculate_player_value(overall, potential, age)
    wage = calculate_player_wage(overall, age)

    preferred_foot = "Left" if r.random() < 0.25 else "Right"

    weak_foot = r.randint(1, 5)
    skill_moves = 1 if position == "GK" else r.randint(1, 5)

    universal_traits = ["leader", "consistent", "injury_prone", "one_club_player"]
    attacker_traits = ["clinical_finisher", "pacey", "big_game_player"]
    midfielder_traits = ["playmaker"]
    defender_gk_traits = ["ball_winner", "aerial_threat"]

    if position in ["GK", "CB", "LB", "RB", "LWB", "RWB"]:
        trait_pool = defender_gk_traits + universal_traits
    elif position in ["CDM", "CM", "CAM", "LM", "RM"]:
        trait_pool = midfielder_traits + universal_traits
    else:
        trait_pool = attacker_traits + universal_traits

    trait_pool = sorted(set(trait_pool))

    num_traits = r.choices([0, 1, 2], weights=[0.6, 0.3, 0.1])[0]
    assigned_traits = r.sample(trait_pool, num_traits) if num_traits > 0 else []
    traits = {"list": assigned_traits}

    return GeneratedPlayer(
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
        is_retired=False,
        nationality=nationality,
    )


def generate_squad(
    guild_id: str,
    club_id: uuid.UUID | None,
    *,
    seed: int | None = None,
) -> list[GeneratedPlayer]:
    """Generate a full squad of 25 balanced players."""
    rng = random.Random(seed)

    group_slots = {
        "GK": [p for p in POSITIONS_DISTRIBUTION if p == "GK"],
        "DEF": [p for p in POSITIONS_DISTRIBUTION if p in ["CB", "LB", "RB", "LWB", "RWB"]],
        "MID": [p for p in POSITIONS_DISTRIBUTION if p in ["CDM", "CM", "CAM", "LM", "RM"]],
        "ATT": [p for p in POSITIONS_DISTRIBUTION if p in ["LW", "RW", "ST", "CF"]],
    }

    group_targets = {g: len(slots) for g, slots in group_slots.items()}
    tier_sizes = {"Star": 1, "Key": 4, "Rotation": 12, "Prospect": 8}

    total_slots = sum(group_targets.values())
    group_shares = {g: target / total_slots for g, target in group_targets.items()}

    matrix: dict[str, dict[str, int]] = {}
    for g in group_targets:
        matrix[g] = {}
        for t in tier_sizes:
            matrix[g][t] = int(tier_sizes[t] * group_shares[g])

    row_caps = {g: group_targets[g] - sum(matrix[g].values()) for g in group_targets}
    col_caps = {
        t: tier_sizes[t] - sum(matrix[g][t] for g in group_targets)
        for t in tier_sizes
    }

    remainders: dict[str, dict[str, float]] = {}
    for g in group_targets:
        remainders[g] = {}
        for t in tier_sizes:
            remainders[g][t] = (tier_sizes[t] * group_shares[g]) - matrix[g][t]

    while any(c > 0 for c in row_caps.values()) and any(c > 0 for c in col_caps.values()):
        candidates = []
        for g in group_targets:
            if row_caps[g] <= 0:
                continue
            for t in tier_sizes:
                if col_caps[t] <= 0:
                    continue
                candidates.append((remainders[g][t], rng.random(), g, t))

        if not candidates:
            break

        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        _, _, best_g, best_t = candidates[0]

        matrix[best_g][best_t] += 1
        row_caps[best_g] -= 1
        col_caps[best_t] -= 1

    rotation_or_better = ["Star", "Key", "Rotation"]
    for g in group_targets:
        better_count = sum(matrix[g][t] for t in rotation_or_better)
        if better_count == 0 and matrix[g].get("Prospect", 0) > 0:
            surplus_groups = []
            for sg in group_targets:
                if sg == g:
                    continue
                if matrix[sg].get("Rotation", 0) > 0:
                    surplus_groups.append(
                        (sum(matrix[sg][t] for t in rotation_or_better), sg)
                    )
            if surplus_groups:
                surplus_groups_with_rng = [
                    (count, rng.random(), sg) for count, sg in surplus_groups
                ]
                surplus_groups_with_rng.sort(key=lambda x: (x[0], x[1]), reverse=True)
                _, _, sg = surplus_groups_with_rng[0]

                matrix[g]["Rotation"] = matrix[g].get("Rotation", 0) + 1
                matrix[g]["Prospect"] -= 1
                matrix[sg]["Rotation"] -= 1
                matrix[sg]["Prospect"] = matrix[sg].get("Prospect", 0) + 1

    allocated_tiers: dict[str, list[str]] = {}
    for g in group_targets:
        tiers_list = []
        for t in tier_sizes:
            tiers_list.extend([t] * matrix[g][t])
        rng.shuffle(tiers_list)
        allocated_tiers[g] = tiers_list

    players: list[GeneratedPlayer] = []
    slots_by_group = {g: list(slots) for g, slots in group_slots.items()}
    for g in slots_by_group:
        rng.shuffle(slots_by_group[g])

    for g in group_targets:
        for pos, tier in zip(slots_by_group[g], allocated_tiers[g]):
            if tier == "Star":
                ovr = rng.randint(72, 78)
            elif tier == "Key":
                ovr = rng.randint(66, 71)
            elif tier == "Rotation":
                ovr = rng.randint(60, 65)
            else:
                ovr = rng.randint(48, 59)

            players.append(generate_player(guild_id, club_id, pos, ovr, rng=rng))

    return players
