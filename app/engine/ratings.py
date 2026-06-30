def calculate_player_value(overall: int, potential: int, age: int) -> int:
    """
    Calculate player market value based on overall, potential, and age.
    """
    # Base value based on overall
    base = 50000 * (1.15 ** (overall - 48))
    
    # Potential bonus
    potential_diff = max(0, potential - overall)
    potential_bonus = 1.10 ** potential_diff
    
    # Age factor
    if age < 23:
        age_factor = 1.2
    elif age <= 28:
        age_factor = 1.0
    elif age <= 32:
        age_factor = 0.8
    else:
        age_factor = 0.5
        
    val = int(base * potential_bonus * age_factor)
    # Round to nearest 1,000
    return max(1000, (val // 1000) * 1000)

def calculate_player_wage(overall: int, age: int) -> int:
    """
    Calculate player weekly wage based on overall rating and age/experience.
    """
    base_wage = 500 * (1.12 ** (overall - 48))
    
    if age < 22:
        age_wage_factor = 0.8
    elif age <= 30:
        age_wage_factor = 1.0
    else:
        age_wage_factor = 1.2
        
    wage = int(base_wage * age_wage_factor)
    # Round to nearest 50
    return max(50, (wage // 50) * 50)
