from typing import Any, Dict
from engine.scales.base_scale import BaseScale
from engine.kernel.world_state_manager import PrefectWorldState

class PrefectScale(BaseScale):
    """
    Implementation of the strategic/operational Prefect scale.
    Operates on a PrefectWorldState object.
    """
    def __init__(self, state: PrefectWorldState):
        self.state = state

    def initialize_state(self, initial_data: Dict[str, Any]) -> None:
        """Initialize the strategic map and units."""
        pass

    def advance_turn(self) -> None:
        """
        Advances the operational clock.
        This represents a much larger time scale than Centurion turns.
        """
        self.state.turn += 1
        
        # Operational level morale/soft state recovery or decay
        for unit in self.state.units.values():
            if not unit.is_destroyed:
                # Operational units recover morale each turn
                unit.soft_state.recover_morale()
                
    def get_state(self) -> PrefectWorldState:
        return self.state
