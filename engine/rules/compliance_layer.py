from engine.kernel.soft_state_layer import SoftState

def compute_compliance_probability(
    base_quality: float,
    soft_state: SoftState,
    comms_jamming_modifier: float = 1.0
) -> float:
    """
    Computes actor compliance probability based on base quality modulated by soft-states.
    A unit with morale < 0.2 is routing and has compliance probability of 0.0.
    """
    if soft_state.morale < 0.2:
        return 0.0

    prob = (
        base_quality
        * soft_state.morale
        * soft_state.command_cohesion
        * soft_state.supply_state
        * comms_jamming_modifier
    )
    return max(0.0, min(1.0, prob))
