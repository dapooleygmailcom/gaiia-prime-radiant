from typing import Dict, Optional, List
import uuid
from engine.kernel.world_state_manager import WorldStateManager, CenturionWorldState
from engine.scales.prefect_scale import PrefectScale
from engine.scales.centurion_scale import CenturionScale

class ScaleNavigator:
    """
    Manages the relationship between scales.
    Handles zooming in (Prefect -> Centurion) and zooming out (Centurion -> Prefect),
    as well as clock management across scales.
    """
    def __init__(self, wsm: WorldStateManager):
        self.wsm = wsm
        self.prefect_scale = PrefectScale(self.wsm.current_state.prefect_state)
        self.active_engagements: Dict[str, CenturionScale] = {}
        
        # Load any existing engagements from state
        for eng_id, state in self.wsm.current_state.centurion_engagements.items():
            self.active_engagements[eng_id] = CenturionScale(eng_id, state)

    def trigger_engagement(self, prefect_unit_ids: List[str]) -> str:
        """
        Zooms in. Creates a new Centurion engagement from a set of Prefect units.
        Returns the engagement ID.
        """
        engagement_id = f"eng_{uuid.uuid4().hex[:8]}"
        
        # Create a new Centurion state
        cent_state = CenturionWorldState(simulation_id=self.wsm.simulation_id)
        self.wsm.current_state.centurion_engagements[engagement_id] = cent_state
        
        # Link prefect units to this engagement
        for uid in prefect_unit_ids:
            if uid in self.prefect_scale.state.units:
                self.prefect_scale.state.units[uid].linked_centurion_engagement_id = engagement_id
                
        # Initialize Centurion scale wrapper
        centurion_scale = CenturionScale(engagement_id, cent_state)
        self.active_engagements[engagement_id] = centurion_scale
        
        # Note: Actual creation of CenturionUnits from PrefectUnits would happen here,
        # likely utilizing RAG-Doll rule resolution for Force composition.
        
        return engagement_id

    def resolve_engagement(self, engagement_id: str) -> None:
        """
        Zooms out. Concludes a Centurion engagement and rolls up results 
        (e.g., destroyed units, morale hits) to the Prefect scale.
        """
        if engagement_id not in self.active_engagements:
            raise ValueError(f"Engagement {engagement_id} not active.")
            
        # In a real implementation, we would analyze the Centurion state and update the 
        # corresponding Prefect units (e.g. if all Centurion units for a faction died, 
        # the Prefect unit is destroyed).
        
        # Unlink Prefect units
        for unit in self.prefect_scale.state.units.values():
            if unit.linked_centurion_engagement_id == engagement_id:
                unit.linked_centurion_engagement_id = None
                
        # Remove the engagement from active status (but keep it in state history if needed)
        del self.active_engagements[engagement_id]

    def advance_prefect_turn(self, centurion_turns_per_prefect_turn: int = 10) -> None:
        """
        Advances the global clock by one Prefect turn.
        Optionally advances any active Centurion engagements by a set amount of turns.
        """
        self.prefect_scale.advance_turn()
        
        for scale in self.active_engagements.values():
            for _ in range(centurion_turns_per_prefect_turn):
                scale.advance_turn()
