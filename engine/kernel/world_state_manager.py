import copy
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from engine.kernel.soft_state_layer import SoftState

class CenturionUnit(BaseModel):
    id: str
    name: str
    faction: str  # "commonwealth" or "tog"
    position: List[int] = Field(default_factory=lambda: [0, 0], description="Hex coordinate [q, r]")
    velocity: int = 0
    thrust_points: int = 10
    soft_state: SoftState = Field(default_factory=SoftState)
    is_destroyed: bool = False
    spotted_by: List[str] = Field(default_factory=list, description="Factions that have spotted this unit")

class CenturionWorldState(BaseModel):
    simulation_id: str
    turn: int = 0
    units: Dict[str, CenturionUnit] = Field(default_factory=dict)
    map_hexes: Dict[str, str] = Field(default_factory=dict, description="q,r key to terrain type")

class WorldStateManager:
    """
    Manages the authoritative, hierarchical/flat Pydantic state graphs.
    Supports checkpoint snapshotting, rollback, and JSON serialization.
    """
    def __init__(self, simulation_id: str):
        self.simulation_id = simulation_id
        self.current_state = CenturionWorldState(simulation_id=simulation_id)
        self.snapshots: Dict[int, CenturionWorldState] = {}

    def get_state(self) -> CenturionWorldState:
        return self.current_state

    def get_belief_state(self, faction_id: str) -> CenturionWorldState:
        """
        Returns a filtered state containing only units visible to the given faction.
        A unit is visible if it belongs to the faction, or if the faction has spotted it.
        """
        belief = copy.deepcopy(self.current_state)
        visible_units = {}
        for uid, unit in belief.units.items():
            if unit.faction == faction_id or faction_id in unit.spotted_by:
                visible_units[uid] = unit
        belief.units = visible_units
        return belief

    def add_unit(self, unit: CenturionUnit):
        self.current_state.units[unit.id] = unit

    def set_hex(self, q: int, r: int, terrain_type: str):
        self.current_state.map_hexes[f"{q},{r}"] = terrain_type

    def take_snapshot(self) -> int:
        """Saves current state snapshot keyed by current turn."""
        turn = self.current_state.turn
        self.snapshots[turn] = copy.deepcopy(self.current_state)
        return turn

    def rollback(self, turn: int) -> bool:
        """Rolls back the current state to a previous turn snapshot."""
        if turn in self.snapshots:
            self.current_state = copy.deepcopy(self.snapshots[turn])
            return True
        return False

    def advance_turn(self):
        """Advances turn counter and updates unit soft-states (decaying suppression)."""
        self.take_snapshot()
        self.current_state.turn += 1
        for unit in self.current_state.units.values():
            if not unit.is_destroyed:
                unit.soft_state.decay_suppression()
                unit.soft_state.recover_morale()

    def serialize(self) -> str:
        return self.current_state.model_dump_json()

    @classmethod
    def deserialize(cls, json_str: str) -> "WorldStateManager":
        state = CenturionWorldState.model_validate_json(json_str)
        wsm = cls(state.simulation_id)
        wsm.current_state = state
        return wsm
