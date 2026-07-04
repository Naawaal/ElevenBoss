# app/engine/formation_rules.py

SUPPORTED_FORMATIONS = ["4-4-2", "4-3-3", "4-2-3-1", "3-5-2", "5-3-2"]

FORMATION_SLOTS = {
    "4-4-2": [
        "GK", "LB", "CB1", "CB2", "RB", "LM", "CM1", "CM2", "RM", "ST1", "ST2"
    ],
    "4-3-3": [
        "GK", "LB", "CB1", "CB2", "RB", "CM1", "CM2", "CM3", "LW", "ST", "RW"
    ],
    "4-2-3-1": [
        "GK", "LB", "CB1", "CB2", "RB", "LDM", "RDM", "LM", "CAM", "RM", "ST"
    ],
    "3-5-2": [
        "GK", "CB1", "CB2", "CB3", "LWB", "RWB", "CM1", "CM2", "CAM", "ST1", "ST2"
    ],
    "5-3-2": [
        "GK", "LWB", "CB1", "CB2", "CB3", "RWB", "CM1", "CM2", "CM3", "ST1", "ST2"
    ],
}

SLOT_RULES = {
    "GK": {"natural": ["GK"], "compatible": []},
    
    "LB": {"natural": ["LB"], "compatible": ["LWB", "CB"]},
    "CB1": {"natural": ["CB"], "compatible": ["LB", "RB"]},
    "CB2": {"natural": ["CB"], "compatible": ["LB", "RB"]},
    "CB3": {"natural": ["CB"], "compatible": ["LB", "RB"]},
    "RB": {"natural": ["RB"], "compatible": ["RWB", "CB"]},
    
    "LWB": {"natural": ["LWB", "LM"], "compatible": ["LB", "LW"]},
    "RWB": {"natural": ["RWB", "RM"], "compatible": ["RB", "RW"]},
    
    "LM": {"natural": ["LM", "LW"], "compatible": ["CM", "CAM"]},
    "CM1": {"natural": ["CM", "CDM"], "compatible": ["CAM"]},
    "CM2": {"natural": ["CM", "CDM"], "compatible": ["CAM"]},
    "CM3": {"natural": ["CM", "CDM"], "compatible": ["CAM"]},
    "RM": {"natural": ["RM", "RW"], "compatible": ["CM", "CAM"]},
    
    "LDM": {"natural": ["CDM", "CM"], "compatible": ["CB"]},
    "RDM": {"natural": ["CDM", "CM"], "compatible": ["CB"]},
    
    "CAM": {"natural": ["CAM"], "compatible": ["CM", "CF", "ST"]},
    
    "LW": {"natural": ["LW", "LM"], "compatible": ["ST", "CF"]},
    "ST": {"natural": ["ST", "CF"], "compatible": ["LW", "RW"]},
    "RW": {"natural": ["RW", "RM"], "compatible": ["ST", "CF"]},
    
    "ST1": {"natural": ["ST", "CF"], "compatible": ["LW", "RW"]},
    "ST2": {"natural": ["ST", "CF"], "compatible": ["LW", "RW"]},
}

def get_slots_for_formation(formation: str) -> list[str]:
    """
    Get the ordered list of starting slots for a given formation.
    """
    if formation not in SUPPORTED_FORMATIONS:
        raise ValueError(f"Unsupported formation: {formation}")
    return FORMATION_SLOTS[formation]

def get_slot_rules(slot: str) -> dict:
    """
    Get allowed position rules for a given slot.
    """
    if slot in SLOT_RULES:
        return SLOT_RULES[slot]
    
    # Fallback/default if slot is not explicitly declared
    return {"natural": [], "compatible": []}
