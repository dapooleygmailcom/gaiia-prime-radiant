import heapq
from typing import Dict, List, Optional, Tuple, Union, Any
import networkx as nx

from engine.kernel.spatial_models import (
    HexCell,
    ManagedSpatialWorldState,
    TerrainType,
    HexCoordinateConverter
)


class SpatialLOSArbiter:
    """
    Computes mathematically exact Line-of-Sight (LOS) raycasting between hexes
    using 3D Cube Coordinate linear interpolation and terrain/obstacle occlusion.
    """

    @staticmethod
    def _lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    @classmethod
    def _cube_lerp(cls, c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[float, float, float]:
        return (
            cls._lerp(float(c1[0]), float(c2[0]), t),
            cls._lerp(float(c1[1]), float(c2[1]), t),
            cls._lerp(float(c1[2]), float(c2[2]), t),
        )

    @staticmethod
    def _cube_round(frac: Tuple[float, float, float]) -> Tuple[int, int, int]:
        rx = round(frac[0])
        ry = round(frac[1])
        rz = round(frac[2])

        x_diff = abs(rx - frac[0])
        y_diff = abs(ry - frac[1])
        z_diff = abs(rz - frac[2])

        if x_diff > y_diff and x_diff > z_diff:
            rx = -ry - rz
        elif y_diff > z_diff:
            ry = -rx - rz
        else:
            rz = -rx - ry

        return (int(rx), int(ry), int(rz))

    @classmethod
    def check_los(
        cls,
        origin: Union[HexCell, str, Tuple[int, int]],
        target: Union[HexCell, str, Tuple[int, int]],
        world_state: ManagedSpatialWorldState
    ) -> Tuple[bool, List[str], str]:
        """
        Determines if Line of Sight exists between origin and target hex.
        Returns:
            - is_clear (bool)
            - blocking_hex_ids (List[str])
            - explanation (str)
        """
        origin_cell = origin if isinstance(origin, HexCell) else world_state.get_cell(origin)
        target_cell = target if isinstance(target, HexCell) else world_state.get_cell(target)

        if not origin_cell or not target_cell:
            return False, [], "Invalid origin or target hex coordinate."

        c1 = (origin_cell.cube_x, origin_cell.cube_y, origin_cell.cube_z)
        c2 = (target_cell.cube_x, target_cell.cube_y, target_cell.cube_z)

        # Cube distance
        dist = HexCoordinateConverter.cube_distance(c1, c2)
        if dist <= 1:
            return True, [], "Adjacent hex: automatic Line of Sight."

        # Index lookup by (cube_x, cube_y, cube_z)
        cube_map: Dict[Tuple[int, int, int], HexCell] = {
            (c.cube_x, c.cube_y, c.cube_z): c for c in world_state.global_hexes.values()
        }

        # Eye height: +0.5 above cell base elevation
        origin_eye = origin_cell.elevation + 0.5
        target_eye = target_cell.elevation + 0.5

        blocking_hexes: List[str] = []

        # Raycast along line of sight
        for step in range(1, dist):
            t = step / float(dist)
            interp_cube = cls._cube_round(cls._cube_lerp(c1, c2, t))
            inter_cell = cube_map.get(interp_cube)

            if not inter_cell:
                continue

            ray_elevation = cls._lerp(origin_eye, target_eye, t)
            obstacle_top = float(inter_cell.elevation + inter_cell.obstacle_height)

            # Terrain or obstacle blocks sight if it reaches or exceeds the ray line
            if obstacle_top >= ray_elevation:
                blocking_hexes.append(inter_cell.hex_id)

            # Check dynamic obscuration (Dense Smoke, Fire, etc.)
            terrain_val = inter_cell.base_terrain.value if hasattr(inter_cell.base_terrain, "value") else str(inter_cell.base_terrain)
            if terrain_val in ["Dense Smoke", "Fire"] or any(e in ["Dense Smoke", "Fire"] for e in inter_cell.dynamic_effects):
                if inter_cell.hex_id not in blocking_hexes:
                    blocking_hexes.append(inter_cell.hex_id)

        if blocking_hexes:
            return False, blocking_hexes, f"LOS blocked by obstacle/elevation at hexes: {', '.join(blocking_hexes)}"

        return True, [], "Clear Line of Sight"


class SpatialPathfinder:
    """
    A* / Dijkstra Pathfinding across the ManagedSpatialWorldState.
    """

    @classmethod
    def find_path(
        cls,
        start: Union[HexCell, str, Tuple[int, int]],
        goal: Union[HexCell, str, Tuple[int, int]],
        world_state: ManagedSpatialWorldState,
        unit_mode: str = "ground",
        max_cost: float = 999.0
    ) -> Tuple[Optional[List[HexCell]], float]:
        """
        Calculates the lowest-cost movement path between two hexes.
        Returns (path_cells, total_cost).
        """
        start_cell = start if isinstance(start, HexCell) else world_state.get_cell(start)
        goal_cell = goal if isinstance(goal, HexCell) else world_state.get_cell(goal)

        if not start_cell or not goal_cell:
            return None, 0.0

        if start_cell.hex_id == goal_cell.hex_id:
            return [start_cell], 0.0

        frontier: List[Tuple[float, str]] = []
        heapq.heappush(frontier, (0.0, start_cell.hex_id))

        came_from: Dict[str, Optional[str]] = {start_cell.hex_id: None}
        cost_so_far: Dict[str, float] = {start_cell.hex_id: 0.0}

        goal_c = (goal_cell.cube_x, goal_cell.cube_y, goal_cell.cube_z)
        found = False

        while frontier:
            current_priority, current_id = heapq.heappop(frontier)
            current_cell = world_state.get_cell(current_id)
            if not current_cell:
                continue

            if current_id == goal_cell.hex_id:
                found = True
                break

            for nbr_q, nbr_r in current_cell.neighbors_axial():
                nbr_col, nbr_row = HexCoordinateConverter.axial_to_col_row(nbr_q, nbr_r, stagger_odd=True)
                nbr_cell = world_state.get_cell((nbr_col, nbr_row))
                if not nbr_cell:
                    continue

                if nbr_cell.is_blocked_for_movement(unit_mode):
                    continue

                # Compute step cost
                elev_diff = nbr_cell.elevation - current_cell.elevation
                step_cost = nbr_cell.movement_cost_multiplier
                if elev_diff > 0:
                    step_cost += float(elev_diff) * 1.0  # Uphill cost

                new_cost = cost_so_far[current_id] + step_cost
                if new_cost > max_cost:
                    continue

                if nbr_cell.hex_id not in cost_so_far or new_cost < cost_so_far[nbr_cell.hex_id]:
                    cost_so_far[nbr_cell.hex_id] = new_cost
                    nbr_c = (nbr_cell.cube_x, nbr_cell.cube_y, nbr_cell.cube_z)
                    h = HexCoordinateConverter.cube_distance(nbr_c, goal_c)
                    priority = new_cost + float(h)
                    heapq.heappush(frontier, (priority, nbr_cell.hex_id))
                    came_from[nbr_cell.hex_id] = current_id

        if not found:
            return None, 0.0

        # Reconstruct path
        path_ids: List[str] = []
        curr = goal_cell.hex_id
        while curr is not None:
            path_ids.append(curr)
            curr = came_from.get(curr)
        path_ids.reverse()

        path_cells = [world_state.get_cell(hid) for hid in path_ids if world_state.get_cell(hid) is not None]
        return path_cells, cost_so_far[goal_cell.hex_id]
