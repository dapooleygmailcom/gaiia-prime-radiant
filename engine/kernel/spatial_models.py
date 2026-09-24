import re
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any
from pydantic import BaseModel, Field, field_validator


class HexOrientation(str, Enum):
    POINTY_TOP = "pointy_top"   # Vertical columns stagger (sideways=False in Vassal)
    FLAT_TOP = "flat_top"       # Horizontal rows stagger (sideways=True in Vassal)


class TerrainType(str, Enum):
    CLEAR = "Clear"
    LIGHT_WOODS = "Light Woods"
    HEAVY_WOODS = "Heavy Woods"
    ROUGH = "Rough"
    CRATERED = "Cratered"
    MARSH = "Marsh"
    RIVER = "River"
    WATER_DEEP = "Deep Water"
    WATER_SHALLOW = "Shallow Water"
    PAVED_ROAD = "Paved Road"
    DIRT_ROAD = "Dirt Road"
    URBAN_LOW = "Urban (Low-Rise)"
    URBAN_HIGH = "Urban (High-Rise)"
    BARRICADE = "Barricade"
    SMOKE_DENSE = "Dense Smoke"
    SMOKE_DISPERSING = "Dispersing Smoke"
    FIRE = "Fire"


class HexEdgeFeature(str, Enum):
    NONE = "none"
    CLIFF = "cliff"
    WALL = "wall"
    BOCAGE = "bocage"
    RIVER = "river"
    BRIDGE = "bridge"
    STREAM = "stream"
    ROAD_CROSSING = "road_crossing"


class HexCoordinateConverter:
    """
    Unified geometric coordinate translations across Offset, Axial (q,r),
    Cube (x,y,z), Alphanumeric (A1, AA1), and Vassal/Cartesian pixel projections.
    """

    @staticmethod
    def parse_coord(coord: Union[str, List[int], Tuple[int, int]]) -> Tuple[int, int]:
        """
        Parses coordinates in forms:
        - [1, 2] or (1, 2) -> (1, 2)
        - "1,2" or "1_2" -> (1, 2)
        - "0102" or "1001" (4-digit numeric string) -> (1, 2) / (10, 1)
        - "A1" or "AA12" (Alphanumeric Vassal format) -> (col, row)
        """
        if isinstance(coord, (list, tuple)):
            return int(coord[0]), int(coord[1])
        
        c_str = str(coord).strip()
        if "," in c_str:
            parts = c_str.split(",")
            return int(parts[0].strip()), int(parts[1].strip())
        if "_" in c_str:
            parts = c_str.split("_")
            # Might have board prefix like "board1_0102" or "1_2"
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return int(parts[0]), int(parts[1])
            elif len(parts) >= 2 and parts[-1].isdigit():
                last = parts[-1]
                if len(last) == 4 and last.isdigit():
                    return int(last[:2]), int(last[2:])
                return int(parts[-2]), int(parts[-1])
        
        # 4-digit pure numeric string (e.g., "1001" -> col 10, row 1)
        if len(c_str) == 4 and c_str.isdigit():
            return int(c_str[:2]), int(c_str[2:])

        # Alphanumeric e.g. "A1", "B02", "AA12"
        match = re.match(r"^([A-Za-z]+)(\d+)$", c_str)
        if match:
            alpha = match.group(1).upper()
            row = int(match.group(2))
            col = 0
            for char in alpha:
                col = col * 26 + (ord(char) - ord('A') + 1)
            return col, row

        # 2-digit pure numeric (e.g., "12" -> col 1, row 2)
        if len(c_str) == 2 and c_str.isdigit():
            return int(c_str[0]), int(c_str[1])

        # Fallback if digits exist
        nums = re.findall(r"\d+", c_str)
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
        elif len(nums) == 1:
            n = int(nums[0])
            if n > 99:
                s = str(n).zfill(4)
                return int(s[:2]), int(s[2:])
            return n, 1

        return 0, 0

    @staticmethod
    def format_coord_digits(col: int, row: int) -> str:
        """Formats to canonical 4-digit string '0101'."""
        return f"{col:02d}{row:02d}"

    @staticmethod
    def format_coord_alpha(col: int, row: int) -> str:
        """Formats to alphanumeric string 'A1', 'AA1'."""
        alpha = ""
        c = col
        while c > 0:
            c -= 1
            alpha = chr(ord('A') + (c % 26)) + alpha
            c //= 26
        return f"{alpha}{row}"

    @staticmethod
    def col_row_to_axial(col: int, row: int, stagger_odd: bool = True, orientation: HexOrientation = HexOrientation.POINTY_TOP) -> Tuple[int, int]:
        """Converts offset (col, row) to Axial (q, r)."""
        if orientation == HexOrientation.POINTY_TOP:
            q = col
            r = row - ((col + (1 if stagger_odd else 0)) // 2)
            return q, r
        else: # FLAT_TOP
            q = col - ((row + (1 if stagger_odd else 0)) // 2)
            r = row
            return q, r

    @staticmethod
    def axial_to_col_row(q: int, r: int, stagger_odd: bool = True, orientation: HexOrientation = HexOrientation.POINTY_TOP) -> Tuple[int, int]:
        """Converts Axial (q, r) to offset (col, row)."""
        if orientation == HexOrientation.POINTY_TOP:
            col = q
            row = r + ((col + (1 if stagger_odd else 0)) // 2)
            return col, row
        else: # FLAT_TOP
            row = r
            col = q + ((row + (1 if stagger_odd else 0)) // 2)
            return col, row

    @staticmethod
    def axial_to_cube(q: int, r: int) -> Tuple[int, int, int]:
        x = q
        z = r
        y = -x - z
        return x, y, z

    @staticmethod
    def cube_to_axial(x: int, y: int, z: int) -> Tuple[int, int]:
        return x, z

    @classmethod
    def cube_distance(cls, c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> int:
        return max(abs(c1[0] - c2[0]), abs(c1[1] - c2[1]), abs(c1[2] - c2[2]))


class HexCell(BaseModel):
    """
    Authoritative representation of a single hexagonal cell within the simulation world state.
    """
    hex_id: str = Field(description="Canonical format: '0101' or 'A1' or 'B1_0101'")
    col: int
    row: int
    axial_q: int
    axial_r: int
    cube_x: int
    cube_y: int
    cube_z: int

    # Topography & Obstacles
    elevation: int = Field(default=0, description="Base terrain elevation level (0, 1, 2...)")
    base_terrain: TerrainType = Field(default=TerrainType.CLEAR)
    obstacle_height: int = Field(default=0, description="Height of obstacle above base elevation (e.g. 1 for woods, 2 for building)")

    # Tactical Modifiers
    armor_cover_mod: int = Field(default=0, description="Vehicle cover modifier")
    infantry_tem: int = Field(default=0, description="Infantry Terrain Effect Modifier (+1, +2 DRM)")
    movement_cost_multiplier: float = Field(default=1.0, description="Movement Point cost factor")

    # Edge Features (hex sides 0 to 5)
    edge_features: Dict[int, HexEdgeFeature] = Field(default_factory=dict)

    # Dynamic In-Play Effects
    dynamic_effects: List[str] = Field(default_factory=list, description="Active smoke, fire, craters, or wrecks")
    pixel_center: Optional[Tuple[float, float]] = Field(default=None, description="(X, Y) pixel center on source board raster")

    def distance_to(self, other: "HexCell") -> int:
        c1 = (self.cube_x, self.cube_y, self.cube_z)
        c2 = (other.cube_x, other.cube_y, other.cube_z)
        return HexCoordinateConverter.cube_distance(c1, c2)

    def neighbors_axial(self) -> List[Tuple[int, int]]:
        OFFSETS = [(+1, 0), (+1, -1), (0, -1), (-1, 0), (-1, +1), (0, +1)]
        return [(self.axial_q + dq, self.axial_r + dr) for dq, dr in OFFSETS]

    def is_blocked_for_movement(self, unit_mode: str = "ground") -> bool:
        if self.base_terrain in [TerrainType.WATER_DEEP] and unit_mode in ["tracked", "wheeled", "infantry"]:
            return True
        return False


class SpatialBoard(BaseModel):
    """
    Discrete board definition with geometric raster dimensions and HexGrid calibration.
    """
    board_id: str
    board_name: str
    image_file: Optional[str] = None
    width_px: int = 0
    height_px: int = 0
    dx: float = 66.4
    dy: float = 57.5
    x0: float = 33.2
    y0: float = 38.0
    orientation: HexOrientation = HexOrientation.POINTY_TOP
    stagger_odd: bool = True
    hexes: Dict[str, HexCell] = Field(default_factory=dict)

    def get_hex(self, coord: Union[str, Tuple[int, int], List[int]]) -> Optional[HexCell]:
        c, r = HexCoordinateConverter.parse_coord(coord)
        key_4digit = HexCoordinateConverter.format_coord_digits(c, r)
        key_alpha = HexCoordinateConverter.format_coord_alpha(c, r)
        return self.hexes.get(key_4digit) or self.hexes.get(key_alpha) or self.hexes.get(f"{c},{r}")

    def set_cell(
        self,
        col: int,
        row: int,
        terrain: Union[TerrainType, str] = TerrainType.CLEAR,
        elevation: int = 0,
        obstacle_height: int = 0
    ) -> HexCell:
        hex_id = HexCoordinateConverter.format_coord_digits(col, row)
        axial_q, axial_r = HexCoordinateConverter.col_row_to_axial(col, row, self.stagger_odd, self.orientation)
        cx, cy, cz = HexCoordinateConverter.axial_to_cube(axial_q, axial_r)

        # Calculate pixel center
        px_x = self.x0 + (col - 1) * self.dx
        stagger_offset = (self.dy / 2.0) if (col % 2 != 0 if self.stagger_odd else col % 2 == 0) else 0.0
        px_y = self.y0 + (row - 1) * self.dy + stagger_offset

        # Parse terrain
        if isinstance(terrain, str):
            matched = False
            for t in TerrainType:
                if t.value.lower() == terrain.lower() or t.name.lower() == terrain.lower():
                    terrain = t
                    matched = True
                    break
            if not matched:
                terrain = TerrainType.CLEAR

        cell = HexCell(
            hex_id=hex_id,
            col=col,
            row=row,
            axial_q=axial_q,
            axial_r=axial_r,
            cube_x=cx,
            cube_y=cy,
            cube_z=cz,
            elevation=elevation,
            base_terrain=terrain,
            obstacle_height=obstacle_height,
            pixel_center=(px_x, px_y)
        )
        self.hexes[hex_id] = cell
        return cell

    def pixel_to_hex(self, x: float, y: float) -> Tuple[int, int]:
        """Maps raster pixel (X, Y) to (col, row)."""
        c = max(1, round((x - self.x0) / self.dx) + 1)
        stagger_offset = (self.dy / 2.0) if (c % 2 != 0 if self.stagger_odd else c % 2 == 0) else 0.0
        r = max(1, round((y - self.y0 - stagger_offset) / self.dy) + 1)
        return c, r


class ManagedSpatialWorldState(BaseModel):
    """
    Authoritative Spatial State Manager for Prime Radiant.
    Manages multi-board composite layouts, global coordinate indices, and dynamic terrain overlays.
    """
    simulation_id: str
    boards: Dict[str, SpatialBoard] = Field(default_factory=dict)
    global_hexes: Dict[str, HexCell] = Field(default_factory=dict)
    board_layout: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Layout matrix for composite boards: {board_id: {'offset_col': 0, 'offset_row': 0, 'rotation': 0, 'crop': 'A-GG'}}"
    )

    def add_board(self, board: SpatialBoard, offset_col: int = 0, offset_row: int = 0):
        self.boards[board.board_id] = board
        self.board_layout[board.board_id] = {"offset_col": offset_col, "offset_row": offset_row}
        
        for hid, cell in board.hexes.items():
            g_col = cell.col + offset_col
            g_row = cell.row + offset_row
            g_id = f"{g_col:02d}{g_row:02d}"
            
            axial_q, axial_r = HexCoordinateConverter.col_row_to_axial(g_col, g_row, board.stagger_odd, board.orientation)
            cx, cy, cz = HexCoordinateConverter.axial_to_cube(axial_q, axial_r)
            
            g_cell = cell.model_copy(update={
                "hex_id": g_id,
                "col": g_col,
                "row": g_row,
                "axial_q": axial_q,
                "axial_r": axial_r,
                "cube_x": cx,
                "cube_y": cy,
                "cube_z": cz
            })
            self.global_hexes[g_id] = g_cell
            # Also register raw ID if only single board
            if len(self.boards) == 1:
                self.global_hexes[cell.hex_id] = g_cell

    def get_cell(self, coord: Union[str, Tuple[int, int], List[int]]) -> Optional[HexCell]:
        c, r = HexCoordinateConverter.parse_coord(coord)
        key_4d = HexCoordinateConverter.format_coord_digits(c, r)
        if key_4d in self.global_hexes:
            return self.global_hexes[key_4d]
        
        key_alpha = HexCoordinateConverter.format_coord_alpha(c, r)
        if key_alpha in self.global_hexes:
            return self.global_hexes[key_alpha]
            
        key_comma = f"{c},{r}"
        if key_comma in self.global_hexes:
            return self.global_hexes[key_comma]
            
        key_underscore = f"{c}_{r}"
        if key_underscore in self.global_hexes:
            return self.global_hexes[key_underscore]

        # Scan global hexes by col, row
        for cell in self.global_hexes.values():
            if cell.col == c and cell.row == r:
                return cell

        return None

    def set_hex_data(
        self,
        coord: Union[str, Tuple[int, int], List[int]],
        terrain: Union[TerrainType, str] = TerrainType.CLEAR,
        elevation: int = 0,
        obstacle_height: int = 0,
        board_id: str = "default"
    ) -> HexCell:
        c, r = HexCoordinateConverter.parse_coord(coord)
        if board_id not in self.boards:
            default_board = SpatialBoard(board_id=board_id, board_name="Default Board")
            self.add_board(default_board)
            
        board = self.boards[board_id]
        cell = board.set_cell(c, r, terrain=terrain, elevation=elevation, obstacle_height=obstacle_height)
        
        g_id = HexCoordinateConverter.format_coord_digits(c, r)
        self.global_hexes[g_id] = cell
        self.global_hexes[f"{c},{r}"] = cell
        self.global_hexes[f"{c}_{r}"] = cell
        return cell

    def export_legacy_map_hexes(self) -> Dict[str, Dict[str, Any]]:
        """Exports map hexes in legacy dict format {'1001': {'terrain': 'Clear', 'elevation': 0}}"""
        out = {}
        for hid, cell in self.global_hexes.items():
            out[hid] = {
                "terrain": cell.base_terrain.value if hasattr(cell.base_terrain, "value") else str(cell.base_terrain),
                "elevation": cell.elevation,
                "obstacle_height": cell.obstacle_height
            }
        return out
