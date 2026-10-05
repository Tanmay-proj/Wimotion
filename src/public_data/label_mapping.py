# ==============================================================================
# WiMotion Public Data: Label Ontology & Semantic Mapping
# ==============================================================================
"""
Strict binary presence and multi-class activity ontology mapping.
RULES:
  1. 0 = NO_HUMAN (Only verified empty room / no presence)
  2. 1 = HUMAN_PRESENT (Verified human performing an activity)
  3. -1 = UNKNOWN (Ambiguous labels like 'no_activity' without presence verification)
  NEVER convert UNKNOWN to 0.
"""

UNKNOWN_LABEL = -1

PRESENCE_MAP = {
    # Verified Empty / No Person
    "empty": 0,
    "no_presence": 0,

    # Verified Human Activities
    "walking": 1,
    "running": 1,
    "run": 1,
    "standing": 1,
    "standup": 1,
    "sitting": 1,
    "sitdown": 1,
    "liedown": 1,
    "lying": 1,
    "fall": 1,
    "falling": 1,
    "bend": 1,
    "bending": 1,
    "jump": 1,
    "jumping": 1,
    "squat": 1,
    "turn": 1,
    "arm_wave": 1,
    "walking_arm_wave": 1,

    # CRITICAL CORRECTION: 'no_activity' does NOT equal NO_HUMAN
    # A human may be present but stationary. Map to UNKNOWN (-1) unless explicitly grounded.
    "no_activity": UNKNOWN_LABEL
}

ESP_FI_ACTIVITY_MAP = {
    1: "running",
    2: "fall",
    3: "walking",
    4: "turn",
    5: "jump",
    6: "squat",
    7: "arm_wave"
}

TU_WIEN_ACTIVITY_MAP = {
    0: "no_activity",
    1: "walking",
    2: "walking_arm_wave"
}

CSI_HAR_ACTIVITY_MAP = {
    "sitdown": "sitting",
    "standup": "standing",
    "liedown": "lying",
    "run": "running",
    "walk": "walking",
    "fall": "falling",
    "bend": "bending"
}

def map_presence(label: str) -> int:
    """
    Returns:
       0: NO_HUMAN
       1: HUMAN_PRESENT
      -1: UNKNOWN / AMBIGUOUS
    """
    cleaned = str(label).strip().lower()
    return PRESENCE_MAP.get(cleaned, UNKNOWN_LABEL)
