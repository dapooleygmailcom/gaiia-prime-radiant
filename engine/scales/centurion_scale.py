from typing import Any, Dict
from engine.scales.base_scale import BaseScale
from engine.kernel.world_state_manager import CenturionWorldState

class CenturionScale(BaseScale):
    """
    Implementation of the tactical Centurion combat scale.
    Operates on a CenturionWorldState object.
    """
    def __init__(self, engagement_id: str, state: CenturionWorldState):
        self.engagement_id = engagement_id
        self.state = state

    def initialize_state(self, initial_data: Dict[str, Any]) -> None:
        """Initialize any specific starting conditions for the tactical battle."""
        pass

    def advance_turn(self) -> None:
        """
        Advances the tactical clock.
        Updates unit soft-states (decaying suppression and recovering morale).
        """
        self.state.turn += 1
        for unit in self.state.units.values():
            if not unit.is_destroyed:
                unit.soft_state.decay_suppression()
                unit.soft_state.recover_morale()

    def get_state(self) -> CenturionWorldState:
        return self.state
