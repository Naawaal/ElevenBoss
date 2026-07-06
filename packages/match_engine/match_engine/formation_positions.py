# app/engine/formation_positions.py

SUPPORTED_FORMATIONS = ["4-4-2", "4-3-3", "4-2-3-1", "3-5-2", "5-3-2"]

# Percentage coordinates (X, Y) where (0, 0) is top-left of the pitch area,
# GK is near the bottom (high Y value), ST is near the top (low Y value).
FORMATION_COORDINATES = {
    "4-4-2": {
        "GK": (50, 90),
        "LB": (15, 72),
        "CB1": (38, 72),
        "CB2": (62, 72),
        "RB": (85, 72),
        "LM": (15, 48),
        "CM1": (38, 48),
        "CM2": (62, 48),
        "RM": (85, 48),
        "ST1": (35, 20),
        "ST2": (65, 20),
    },
    "4-3-3": {
        "GK": (50, 90),
        "LB": (15, 72),
        "CB1": (38, 72),
        "CB2": (62, 72),
        "RB": (85, 72),
        "CM1": (25, 48),
        "CM2": (50, 52),
        "CM3": (75, 48),
        "LW": (20, 22),
        "ST": (50, 18),
        "RW": (80, 22),
    },
    "4-2-3-1": {
        "GK": (50, 90),
        "LB": (15, 72),
        "CB1": (38, 72),
        "CB2": (62, 72),
        "RB": (85, 72),
        "LDM": (35, 56),
        "RDM": (65, 56),
        "LM": (15, 36),
        "CAM": (50, 36),
        "RM": (85, 36),
        "ST": (50, 18),
    },
    "3-5-2": {
        "GK": (50, 90),
        "CB1": (25, 75),
        "CB2": (50, 75),
        "CB3": (75, 75),
        "LWB": (15, 50),
        "RWB": (85, 50),
        "CM1": (35, 50),
        "CM2": (65, 50),
        "CAM": (50, 32),
        "ST1": (35, 20),
        "ST2": (65, 20),
    },
    "5-3-2": {
        "GK": (50, 90),
        "LWB": (15, 68),
        "CB1": (32, 75),
        "CB2": (50, 75),
        "CB3": (68, 75),
        "RWB": (85, 68),
        "CM1": (25, 45),
        "CM2": (50, 48),
        "CM3": (75, 45),
        "ST1": (35, 20),
        "ST2": (65, 20),
    },
}

def get_coordinates_for_formation(formation: str) -> dict[str, tuple[int, int]]:
    """
    Returns the coordinate mappings for a given formation.
    """
    if formation not in SUPPORTED_FORMATIONS:
        raise ValueError(f"Unsupported formation: {formation}")
    return FORMATION_COORDINATES[formation]


def _role_from_label(label: str) -> str:
    """Map formation slot label to broad position role."""
    if label == "GK":
        return "GK"
    if label.startswith("ST") or label in ("LW", "RW"):
        return "FWD"
    if any(label.startswith(p) for p in ("CB", "LB", "RB", "LWB", "RWB")):
        return "DEF"
    return "MID"


def get_slot_role(formation: str, slot: int) -> str:
    """Return GK/DEF/MID/FWD for 1-based slot index in the given formation."""
    coords = FORMATION_COORDINATES.get(formation, FORMATION_COORDINATES["4-4-2"])
    labels = list(coords.keys())
    if slot < 1 or slot > len(labels):
        return "DEF"
    return _role_from_label(labels[slot - 1])
