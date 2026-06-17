"""Canonical misconception taxonomy for circular motion.

Stable ids are stored in the student model; the descriptions ground the tutor's
detection. Aligned with the knowledge graph's `misconceptions_by_stage`.
"""

MISCONCEPTIONS = {
    "centrifugal_confusion": "treats an outward (centrifugal) force as the real cause of circular motion",
    "speed_equals_velocity": "thinks constant speed means zero acceleration, ignoring the change in velocity direction",
    "radius_inverse": "thinks a larger radius always means larger centripetal acceleration (ignores the fixed-speed case)",
    "omega_linear": "thinks centripetal acceleration scales linearly with angular velocity instead of with its square",
    "force_direction": "thinks the net force/acceleration points outward or tangentially rather than inward",
    "rotation_is_circular_motion": "confuses any spinning-looking object with a point actually following a circular path",
}


def ids():
    return list(MISCONCEPTIONS.keys())


def is_valid(mid):
    return mid in MISCONCEPTIONS


def describe_list():
    """Prompt-ready 'id (description); ...' string for the detection instruction."""
    return "; ".join(f"'{k}' ({v})" for k, v in MISCONCEPTIONS.items())
