import copy
import re
from typing import Dict, List, Optional, Any, Union, Tuple
from pydantic import BaseModel, Field, field_validator
import networkx as nx

from engine.kernel.soft_state_layer import SoftState
from engine.rules.rules_interface import RulesInterface
from engine.kernel.spatial_models import (
    ManagedSpatialWorldState,
    SpatialBoard,
    HexCell,
    TerrainType,
    HexCoordinateConverter
)


class DamageState(BaseModel):
    armor_grids: Dict[str, List[int]] = Field(default_factory=dict, description="Maps facing to array of remaining depths per column")
    internal_grids: Dict[str, List[List[bool]]] = Field(default_factory=dict, description="Maps internal grid name to 2D array (cols x depth) of destroyed status (True = destroyed)")


class CenturionUnit(BaseModel):
    id: str
    name: str
    tvlg_ammo: int = Field(default=0, description="Remaining TVLG ammo")
    smlm_ammo: int = Field(default=0, description="Remaining SMLM ammo")
    faction: str  # "commonwealth" or "tog"
    position: Any = Field(default="0001", description="Hex coordinate as 4-digit string (e.g. '1001') or [col, row]")
    velocity: int = 0
    heading: int = 0
    thrust_points: int = 10
    pilot_skill: int = 5
    soft_state: SoftState = Field(default_factory=SoftState)
    is_destroyed: bool = False
    spotted_by: List[str] = Field(default_factory=list, description="Factions that have spotted this unit")
    entity_profile: Optional[Dict[str, Any]] = Field(default=None, description="The agnostic RAG-Doll entity profile (SSD data)")
    damage_state: DamageState = Field(default_factory=DamageState, description="Tracks current integrity of armor and internals")

    @field_validator("position", mode="before")
    @classmethod
    def normalize_position(cls, v: Any) -> Any:
        if isinstance(v, (list, tuple)):
            return v
        return str(v)


class CenturionWorldState(BaseModel):
    simulation_id: str
    turn: int = 0
    units: Dict[str, CenturionUnit] = Field(default_factory=dict)
    map_hexes: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Hex key to {'terrain': type, 'elevation': int}")


class PrefectUnit(BaseModel):
    id: str
    name: str
    faction: str
    position: Any = Field(default="0001", description="Hex coordinate string or [col, row]")
    supply_level: float = Field(default=1.0, description="1.0 is fully supplied, 0.0 is out of supply")
    soft_state: SoftState = Field(default_factory=SoftState)
    is_destroyed: bool = False
    linked_centurion_engagement_id: Optional[str] = Field(default=None, description="If this unit is currently in a tactical battle")


class PrefectWorldState(BaseModel):
    turn: int = 0
    units: Dict[str, PrefectUnit] = Field(default_factory=dict)
    map_hexes: Dict[str, str] = Field(default_factory=dict, description="Operational hex terrain")
    supply_routes: List[str] = Field(default_factory=list, description="Active supply routes")


class LeviathanUnit(BaseModel):
    id: str
    name: str
    faction: str
    position: Any = Field(default="0001", description="Hex coordinate string or [col, row]")
    velocity: int = 0
    heading: int = 0
    soft_state: SoftState = Field(default_factory=SoftState)
    is_destroyed: bool = False
    entity_profile: Optional[Dict[str, Any]] = Field(default=None)
    damage_state: DamageState = Field(default_factory=DamageState)
    linked_interceptor_engagement_id: Optional[str] = Field(default=None)


class LeviathanWorldState(BaseModel):
    simulation_id: str
    turn: int = 0
    units: Dict[str, LeviathanUnit] = Field(default_factory=dict)
    map_hexes: Dict[str, str] = Field(default_factory=dict)


class InterceptorUnit(BaseModel):
    id: str
    name: str
    faction: str
    position: Any = Field(default="0001", description="Hex coordinate as string")
    velocity: int = 0
    heading: int = 0
    soft_state: SoftState = Field(default_factory=SoftState)
    is_destroyed: bool = False
    entity_profile: Optional[Dict[str, Any]] = Field(default=None)
    damage_state: DamageState = Field(default_factory=DamageState)


class InterceptorWorldState(BaseModel):
    simulation_id: str
    turn: int = 0
    units: Dict[str, InterceptorUnit] = Field(default_factory=dict)


class LegionnaireUnit(BaseModel):
    id: str
    name: str
    faction: str
    position: Any = Field(default="0001", description="Square coordinate as string")
    stance: str = "standing"
    soft_state: SoftState = Field(default_factory=SoftState)
    is_incapacitated: bool = False
    entity_profile: Optional[Dict[str, Any]] = Field(default=None)


class LegionnaireWorldState(BaseModel):
    simulation_id: str
    turn: int = 0
    units: Dict[str, LegionnaireUnit] = Field(default_factory=dict)
    map_squares: Dict[str, str] = Field(default_factory=dict)


class GlobalWorldState(BaseModel):
    simulation_id: str
    spatial_state: Optional[ManagedSpatialWorldState] = None
    prefect_state: PrefectWorldState = Field(default_factory=PrefectWorldState)
    centurion_engagements: Dict[str, CenturionWorldState] = Field(default_factory=dict, description="Active tactical battles")
    leviathan_engagements: Dict[str, LeviathanWorldState] = Field(default_factory=dict, description="Active space battles")
    interceptor_engagements: Dict[str, InterceptorWorldState] = Field(default_factory=dict, description="Active fighter battles")
    legionnaire_engagements: Dict[str, LegionnaireWorldState] = Field(default_factory=dict, description="Active personal battles")


class WorldStateManager:
    """
    Manages the authoritative, hierarchical Pydantic state graphs.
    Supports checkpoint snapshotting, rollback, NetworkX graph synchronization,
    and standardized ManagedSpatialWorldState integration.
    """
    def __init__(self, simulation_id: str):
        self.simulation_id = simulation_id
        spatial = ManagedSpatialWorldState(simulation_id=simulation_id)
        self.current_state = GlobalWorldState(simulation_id=simulation_id, spatial_state=spatial)
        self.snapshots: Dict[int, GlobalWorldState] = {}
        self.graph = nx.DiGraph()

    @property
    def spatial_state(self) -> ManagedSpatialWorldState:
        if self.current_state.spatial_state is None:
            self.current_state.spatial_state = ManagedSpatialWorldState(simulation_id=self.simulation_id)
        return self.current_state.spatial_state

    def branch(self, new_simulation_id: str) -> "WorldStateManager":
        """
        Creates a new simulation branch with a deep-copied state graph.
        """
        new_wsm = WorldStateManager(new_simulation_id)
        new_wsm.current_state = copy.deepcopy(self.current_state)
        new_wsm.current_state.simulation_id = new_simulation_id
        new_wsm.snapshots = copy.deepcopy(self.snapshots)
        new_wsm.graph = copy.deepcopy(self.graph)
        return new_wsm

    def get_centurion_state(self, engagement_id: str = "default") -> CenturionWorldState:
        if engagement_id not in self.current_state.centurion_engagements:
            self.current_state.centurion_engagements[engagement_id] = CenturionWorldState(simulation_id=self.simulation_id)
        return self.current_state.centurion_engagements[engagement_id]

    def get_prefect_state(self) -> PrefectWorldState:
        return self.current_state.prefect_state

    def get_state(self) -> CenturionWorldState:
        # Legacy method for tests: returns the first/default centurion state
        return self.get_centurion_state("default")

    def get_belief_state(self, faction_id: str) -> CenturionWorldState:
        belief = copy.deepcopy(self.get_state())
        visible_units = {}
        for uid, unit in belief.units.items():
            if unit.faction == faction_id or faction_id in unit.spotted_by:
                visible_units[uid] = unit
        belief.units = visible_units
        return belief

    def _format_pos_aliases(self, pos: Any) -> Tuple[str, str, str]:
        c, r = HexCoordinateConverter.parse_coord(pos)
        return f"{c:02d}{r:02d}", f"{c},{r}", f"{c}_{r}"

    def add_unit(self, unit: CenturionUnit):
        self.get_state().units[unit.id] = unit
        # Add to graph
        self.graph.add_node(unit.id, type="centurion_unit", unit=unit)
        
        # Link to graph hex
        pos_4d, pos_comma, pos_under = self._format_pos_aliases(unit.position)
        c, r = HexCoordinateConverter.parse_coord(unit.position)
        
        hex_node_ids = [
            f"hex_{unit.position}",
            f"hex_{pos_4d}",
            f"hex_{pos_comma}",
            f"hex_{pos_under}"
        ]
        
        # Ensure at least one canonical hex node exists
        primary_hex_node = f"hex_{pos_under}"
        if not self.graph.has_node(primary_hex_node):
            self.graph.add_node(primary_hex_node, type="hex", col=c, row=r)
            
        for hid in hex_node_ids:
            if self.graph.has_node(hid):
                self.graph.add_edge(unit.id, hid, relation="LOCATED_IN")
                
        # Always link to primary and hex_{unit.position}
        if not self.graph.has_edge(unit.id, primary_hex_node):
            self.graph.add_edge(unit.id, primary_hex_node, relation="LOCATED_IN")
        if isinstance(unit.position, (list, tuple)) and not self.graph.has_edge(unit.id, f"hex_{c}_{r}"):
            self.graph.add_node(f"hex_{c}_{r}", type="hex", col=c, row=r)
            self.graph.add_edge(unit.id, f"hex_{c}_{r}", relation="LOCATED_IN")

    def set_hex(
        self,
        col: Optional[int] = None,
        row: Optional[int] = None,
        terrain_type: str = "Clear",
        elevation: int = 0,
        obstacle_height: int = 0,
        q: Optional[int] = None,
        r: Optional[int] = None
    ):
        if col is None and q is not None:
            col = q
        if row is None and r is not None:
            row = r
        if col is None or row is None:
            col, row = 0, 0

        # Update ManagedSpatialWorldState
        cell = self.spatial_state.set_hex_data((col, row), terrain=terrain_type, elevation=elevation, obstacle_height=obstacle_height)

        # Update legacy dictionary maps for backward compatibility
        hex_id_4d = f"{col:02d}{row:02d}"
        hex_id_comma = f"{col},{row}"
        hex_id_under = f"{col}_{row}"

        cent_state = self.get_state()
        cent_state.map_hexes[hex_id_4d] = {"terrain": terrain_type, "elevation": elevation}
        cent_state.map_hexes[hex_id_comma] = {"terrain": terrain_type, "elevation": elevation}
        cent_state.map_hexes[hex_id_under] = {"terrain": terrain_type, "elevation": elevation}

        # Also support legacy string query e.g. state.map_hexes["1,2"] == "woods"
        cent_state.map_hexes[f"{col},{row}"] = terrain_type

        # Add graph nodes
        for node_id in [f"hex_{hex_id_4d}", f"hex_{hex_id_comma}", f"hex_{hex_id_under}"]:
            self.graph.add_node(
                node_id,
                type="hex",
                col=col,
                row=row,
                terrain=terrain_type,
                elevation=elevation,
                obstacle_height=obstacle_height
            )

    def create_unit_from_entity(self, id: str, faction: str, entity_name: str, rules: RulesInterface) -> CenturionUnit:
        profile = rules.get_entity_data(entity_name)
        thrust = profile.get("attributes", {}).get("Maximum Thrust", 10)
        
        damage_state = DamageState()
        grids = profile.get("grids", {})
        
        for grid_name, grid_data in grids.items():
            if "Depth" in grid_data:
                width = grid_data.get("Width", 10)
                depth = grid_data.get("Depth", 0)
                damage_state.armor_grids[grid_name] = [depth] * width
            elif "Columns" in grid_data and isinstance(grid_data["Columns"], list):
                cols = grid_data["Columns"]
                width = len(cols)
                depth = len(cols[0]) if width > 0 else 0
                damage_state.internal_grids[grid_name] = [[False] * depth for _ in range(width)]
                
        tvlg_ammo = next((m['Count'] for m in profile.get('collections',{}).get('Missiles',[]) if m['Type']=='TVLG'), 0)
        smlm_ammo = next((m['Count'] for m in profile.get('collections',{}).get('Missiles',[]) if m['Type']=='SMLM'), 0)
        
        unit = CenturionUnit(
            id=id,
            name=profile.get("name", entity_name),
            faction=faction,
            tvlg_ammo=tvlg_ammo,
            smlm_ammo=smlm_ammo,
            thrust_points=thrust,
            entity_profile=profile,
            damage_state=damage_state
        )
        self.add_unit(unit)
        return unit

    def take_snapshot(self) -> int:
        turn = self.get_state().turn
        self.snapshots[turn] = copy.deepcopy(self.current_state)
        return turn

    def rollback(self, turn: int) -> bool:
        if turn in self.snapshots:
            self.current_state = copy.deepcopy(self.snapshots[turn])
            self._rebuild_graph_from_state()
            return True
        return False

    def _rebuild_graph_from_state(self):
        self.graph = nx.DiGraph()
        
        # Rebuild hexes and units from Centurion state
        for eng_id, eng_state in self.current_state.centurion_engagements.items():
            for hex_id_str, hex_data in eng_state.map_hexes.items():
                col, row = HexCoordinateConverter.parse_coord(hex_id_str)
                terrain = hex_data.get("terrain", "Clear") if isinstance(hex_data, dict) else str(hex_data)
                elevation = hex_data.get("elevation", 0) if isinstance(hex_data, dict) else 0
                
                self.graph.add_node(
                    f"hex_{hex_id_str}",
                    type="hex",
                    col=col,
                    row=row,
                    terrain=terrain,
                    elevation=elevation
                )
                self.graph.add_node(
                    f"hex_{col}_{row}",
                    type="hex",
                    col=col,
                    row=row,
                    terrain=terrain,
                    elevation=elevation
                )
                
            for uid, unit in eng_state.units.items():
                self.graph.add_node(uid, type="centurion_unit", unit=unit)
                c, r = HexCoordinateConverter.parse_coord(unit.position)
                
                if isinstance(unit.position, (list, tuple)):
                    self.graph.add_edge(uid, f"hex_{unit.position}", relation="LOCATED_IN")
                    self.graph.add_edge(uid, f"hex_{c}_{r}", relation="LOCATED_IN")
                else:
                    self.graph.add_edge(uid, f"hex_{unit.position}", relation="LOCATED_IN")
                    self.graph.add_edge(uid, f"hex_{c}_{r}", relation="LOCATED_IN")
                
        # Rebuild Prefect state
        for hex_id_str, terrain in self.current_state.prefect_state.map_hexes.items():
            self.graph.add_node(f"pref_hex_{hex_id_str}", type="prefect_hex", terrain=terrain)
            
        for uid, unit in self.current_state.prefect_state.units.items():
            self.graph.add_node(uid, type="prefect_unit", unit=unit)
            self.graph.add_edge(uid, f"pref_hex_{unit.position}", relation="LOCATED_IN")

    def advance_turn(self):
        self.take_snapshot()
        state = self.get_state()
        state.turn += 1
        for unit in state.units.values():
            if not unit.is_destroyed:
                unit.soft_state.decay_suppression()
                unit.soft_state.recover_morale()

    def serialize(self) -> str:
        return self.current_state.model_dump_json()

    @classmethod
    def deserialize(cls, json_str: str) -> "WorldStateManager":
        state = GlobalWorldState.model_validate_json(json_str)
        wsm = cls(state.simulation_id)
        wsm.current_state = state
        return wsm
