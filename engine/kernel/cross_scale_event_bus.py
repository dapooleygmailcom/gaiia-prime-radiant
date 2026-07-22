from typing import Any, Callable, Dict, List
from pydantic import BaseModel
from engine.kernel.world_state_manager import WorldStateManager

class Event(BaseModel):
    event_type: str
    payload: Dict[str, Any]
    source_scale: str
    
class CrossScaleEventBus:
    """
    Publish/Subscribe event bus for cascading effects across scales.
    Handles 'SOFT_STATE_CASCADE' events and others.
    """
    def __init__(self, wsm: WorldStateManager):
        self.wsm = wsm
        self.subscribers: Dict[str, List[Callable[[Event], None]]] = {}
        
        # Register core handlers
        self.subscribe("SOFT_STATE_CASCADE", self._handle_soft_state_cascade)
        self.subscribe("INFLUENCE_VECTOR", self._handle_influence_vector)
        self.subscribe("UNIT_DESTROYED", self._handle_unit_loss_morale_contagion)
        self.subscribe("UNIT_ROUTED", self._handle_unit_loss_morale_contagion)

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        
    def publish(self, event: Event) -> None:
        if event.event_type in self.subscribers:
            for handler in self.subscribers[event.event_type]:
                handler(event)

    def _handle_unit_loss_morale_contagion(self, event: Event) -> None:
        """
        When a unit is destroyed or routed, apply a morale penalty to all friendly units 
        in the same engagement to model morale contagion.
        """
        payload = event.payload
        engagement_id = payload.get("engagement_id")
        faction = payload.get("faction")
        
        if event.source_scale == "centurion" and engagement_id:
            cent_state = self.wsm.current_state.centurion_engagements.get(engagement_id)
            if cent_state:
                # Apply a standard -0.1 morale drop to friendly units
                for unit in cent_state.units.values():
                    if unit.faction == faction:
                        unit.soft_state.morale = max(0.0, unit.soft_state.morale - 0.1)

    def _handle_soft_state_cascade(self, event: Event) -> None:
        """
        Handles cascading soft state changes down the scales (e.g., Prefect -> Leviathan -> Centurion).
        Payload expects:
        - source_unit_id: The ID of the unit/formation where the cascade started
        - source_scale: "prefect", "leviathan", "interceptor", "centurion", "legionnaire"
        - morale_modifier: float (optional)
        - suppression_modifier: float (optional)
        """
        payload = event.payload
        source_id = payload.get("source_unit_id")
        morale_mod = payload.get("morale_modifier", 0.0)
        suppress_mod = payload.get("suppression_modifier", 0.0)

        # In a fully realized CEB, we traverse the WSM graph DB to find all downstream linked units.
        # For this implementation, we apply it to linked engagements if coming from Prefect,
        # or if coming from Leviathan, apply to linked Interceptor engagements, etc.
        if event.source_scale == "prefect":
            prefect_unit = self.wsm.current_state.prefect_state.units.get(source_id)
            if not prefect_unit: return
            
            engagement_id = prefect_unit.linked_centurion_engagement_id
            if engagement_id:
                cent_state = self.wsm.current_state.centurion_engagements.get(engagement_id)
                if cent_state:
                    for unit in cent_state.units.values():
                        if unit.faction == prefect_unit.faction:
                            unit.soft_state.apply_suppression(suppress_mod)
                            unit.soft_state.morale = max(0.0, min(1.0, unit.soft_state.morale + morale_mod))

        elif event.source_scale == "leviathan":
            # Leviathan fleet rout cascades to Prefect strategic morale, which cascades to Centurion.
            # Here we demonstrate cascading back UP to Prefect, which would then re-fire a cascade DOWN.
            lev_state = None
            for state in self.wsm.current_state.leviathan_engagements.values():
                if source_id in state.units:
                    lev_state = state
                    break
            
            if lev_state:
                unit = lev_state.units[source_id]
                # Publish a secondary event for the Prefect scale
                self.publish(Event(
                    event_type="SOFT_STATE_CASCADE",
                    source_scale="leviathan_to_prefect",
                    payload={"faction": unit.faction, "morale_modifier": morale_mod}
                ))

    def _handle_influence_vector(self, event: Event) -> None:
        """
        Handles cross-scale physical influences like Orbital Bombardment or Air Support.
        """
        payload = event.payload
        target_scale = payload.get("target_scale")
        
        if target_scale == "centurion":
            engagement_id = payload.get("target_engagement_id")
            cent_state = self.wsm.current_state.centurion_engagements.get(engagement_id)
            if cent_state:
                if event.source_scale == "leviathan" and payload.get("type") == "orbital_bombardment":
                    # Apply template damage to the specified Centurion hex
                    q, r = payload.get("target_hex", (0, 0))
                    # Mark the hex as bombarded (in a full engine, this asks OutcomeModeller to apply the exact damage template)
                    cent_state.map_hexes[f"{q},{r}"] = "cratered"
                    
                elif event.source_scale == "interceptor" and payload.get("type") == "air_superiority":
                    # Apply suppression to all enemy units
                    winning_faction = payload.get("faction")
                    for unit in cent_state.units.values():
                        if unit.faction != winning_faction:
                            unit.soft_state.apply_suppression(0.2)
