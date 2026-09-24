import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any, Union

from engine.kernel.spatial_models import (
    ManagedSpatialWorldState,
    SpatialBoard,
    HexCell,
    HexOrientation,
    TerrainType,
    HexEdgeFeature,
    HexCoordinateConverter
)
from engine.kernel.world_state_manager import WorldStateManager


class VassalMapImporter:
    """
    High-fidelity importer for Vassal module map files (.vmod, .vmdx, .zip, and buildFile.xml).
    Converts Vassal board/hexgrid declarations into ManagedSpatialWorldState objects
    with mathematically rigorous coordinate grids and spatial graph connectivity.
    """

    def __init__(self, simulation_id: str = "vassal_sim"):
        self.simulation_id = simulation_id

    def import_archive(self, archive_path: str, extract_dir: Optional[str] = None) -> ManagedSpatialWorldState:
        """
        Extracts and parses a .vmod, .vmdx, or .zip Vassal module.
        """
        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Vassal archive not found at: {archive_path}")

        if not zipfile.is_zipfile(archive_path):
            raise ValueError(f"File is not a valid ZIP/Vassal archive: {archive_path}")

        target_dir = extract_dir or os.path.join(os.path.dirname(archive_path), f"_extracted_{os.path.splitext(os.path.basename(archive_path))[0]}")
        os.makedirs(target_dir, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(target_dir)

        # Look for buildFile.xml or buildFile
        build_file = os.path.join(target_dir, "buildFile.xml")
        if not os.path.exists(build_file):
            build_file = os.path.join(target_dir, "buildFile")
        if not os.path.exists(build_file):
            raise FileNotFoundError("Neither 'buildFile.xml' nor 'buildFile' found in extracted Vassal archive.")

        return self.import_xml_file(build_file, assets_root=target_dir)

    def import_xml_file(self, xml_path: str, assets_root: Optional[str] = None) -> ManagedSpatialWorldState:
        """
        Parses a buildFile.xml directly.
        """
        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"XML build file not found at: {xml_path}")

        assets_dir = assets_root or os.path.dirname(xml_path)
        with open(xml_path, "r", encoding="utf-8", errors="ignore") as f:
            xml_content = f.read()

        return self.import_xml_string(xml_content, assets_root=assets_dir)

    def import_xml_string(self, xml_content: str, assets_root: str = "") -> ManagedSpatialWorldState:
        """
        Parses XML string definition of Vassal module structure.
        """
        root = ET.fromstring(xml_content)
        world_state = ManagedSpatialWorldState(simulation_id=self.simulation_id)

        # Locate Map elements
        map_elements = list(root.iter("VASSAL.build.module.Map"))
        if not map_elements:
            # Fallback: check if the root itself or generic map containers exist
            map_elements = [root]

        for map_elem in map_elements:
            map_name = map_elem.get("mapName", map_elem.get("name", "Default Map"))
            
            # Find Board elements
            board_elements = map_elem.findall(".//VASSAL.build.module.map.boardPicker.Board")
            if not board_elements:
                board_elements = map_elem.findall(".//Board")

            for b_idx, board_elem in enumerate(board_elements):
                board = self._parse_board_element(board_elem, assets_root, default_id=f"board_{b_idx + 1}")
                world_state.add_board(board)

        return world_state

    def _parse_board_element(self, board_elem: ET.Element, assets_root: str, default_id: str) -> SpatialBoard:
        raw_name = board_elem.get("boardName", board_elem.get("name", default_id))
        board_id = re.sub(r"[^\w-]", "_", raw_name).lower()
        image_name = board_elem.get("image", board_elem.get("imageFile", ""))
        image_path = os.path.join(assets_root, "images", image_name) if image_name else None

        width = int(float(board_elem.get("width", "0") or "0"))
        height = int(float(board_elem.get("height", "0") or "0"))

        board = SpatialBoard(
            board_id=board_id,
            board_name=raw_name,
            image_file=image_path if image_path and os.path.exists(image_path) else image_name,
            width_px=width,
            height_px=height
        )

        # Locate HexGrid
        hex_grid = board_elem.find(".//VASSAL.build.module.map.boardPicker.board.HexGrid")
        if hex_grid is None:
            hex_grid = board_elem.find(".//HexGrid")

        if hex_grid is not None:
            board.dx = float(hex_grid.get("dx", "66.4"))
            board.dy = float(hex_grid.get("dy", "57.5"))
            board.x0 = float(hex_grid.get("x0", "33.2"))
            board.y0 = float(hex_grid.get("y0", "38.0"))
            
            sideways = hex_grid.get("sideways", "false").lower() == "true"
            board.orientation = HexOrientation.FLAT_TOP if sideways else HexOrientation.POINTY_TOP
            board.stagger_odd = hex_grid.get("stagger", "true").lower() == "true"

            # Parse numbering style if present
            num_elem = hex_grid.find(".//VASSAL.build.module.map.boardPicker.board.mapgrid.HexGridNumbering")
            if num_elem is None:
                num_elem = hex_grid.find(".//HexGridNumbering")

            h_desc = num_elem.get("hDesc", "0101") if num_elem is not None else "0101"
            v_desc = num_elem.get("vDesc", "A1") if num_elem is not None else "A1"
            num_type = num_elem.get("type", "alphaNumeric") if num_elem is not None else "alphaNumeric"
            
            first_col = int(num_elem.get("firstCol", "1")) if num_elem is not None else 1
            first_row = int(num_elem.get("firstRow", "1")) if num_elem is not None else 1

            # Estimate number of columns and rows
            cols_count = max(1, int((width - board.x0) / board.dx) + 1) if width > 0 else 33
            rows_count = max(1, int((height - board.y0) / board.dy) + 1) if height > 0 else 20

            for c_idx in range(cols_count):
                col = first_col + c_idx
                for r_idx in range(rows_count):
                    row = first_row + r_idx
                    board.set_cell(col=col, row=row, terrain=TerrainType.CLEAR, elevation=0)
        else:
            # If no explicit hexgrid, create a standard 10x10 grid by default
            for c in range(1, 11):
                for r in range(1, 11):
                    board.set_cell(col=c, row=r, terrain=TerrainType.CLEAR, elevation=0)

        # Parse any RegionGrid / ZonedGrid / Terrain tags
        self._parse_terrain_zones(board_elem, board)

        return board

    def _parse_terrain_zones(self, board_elem: ET.Element, board: SpatialBoard):
        """
        Parses region overlays, zones, and terrain overrides from XML extensions if available.
        """
        for zone in board_elem.iter("Zone"):
            z_name = zone.get("name", "").lower()
            location = zone.get("location", "")
            if location:
                cell = board.get_hex(location)
                if cell:
                    if "wood" in z_name or "forest" in z_name:
                        cell.base_terrain = TerrainType.LIGHT_WOODS
                        cell.obstacle_height = 1
                    elif "hill" in z_name or "ridge" in z_name:
                        cell.elevation = 1
                    elif "river" in z_name or "water" in z_name:
                        cell.base_terrain = TerrainType.RIVER
                    elif "urban" in z_name or "building" in z_name:
                        cell.base_terrain = TerrainType.URBAN_LOW
                        cell.obstacle_height = 1

    def assemble_composite_scenario(
        self,
        boards: List[SpatialBoard],
        layout_matrix: Dict[str, Dict[str, Any]]
    ) -> ManagedSpatialWorldState:
        """
        Stitches multiple boards into a unified scenario map with global coordinate alignment.
        layout_matrix format:
        {
            "board_01": {"offset_col": 0, "offset_row": 0, "crop": None},
            "board_02": {"offset_col": 33, "offset_row": 0, "crop": "A-GG"}
        }
        """
        world_state = ManagedSpatialWorldState(simulation_id=self.simulation_id)
        for board in boards:
            layout = layout_matrix.get(board.board_id, {"offset_col": 0, "offset_row": 0})
            offset_col = layout.get("offset_col", 0)
            offset_row = layout.get("offset_row", 0)
            world_state.add_board(board, offset_col=offset_col, offset_row=offset_row)
        return world_state

    def load_into_wsm(self, wsm: WorldStateManager, source: Union[str, ManagedSpatialWorldState], board_id: Optional[str] = None):
        """
        Loads an imported Vassal map directly into a WorldStateManager instance.
        """
        if isinstance(source, str):
            if source.endswith((".vmod", ".vmdx", ".zip")):
                spatial_state = self.import_archive(source)
            else:
                spatial_state = self.import_xml_file(source)
        else:
            spatial_state = source

        wsm.current_state.spatial_state = spatial_state

        # Sync all global hexes into Centurion World State and NetworkX graph
        cells_to_sync = []
        if board_id and board_id in spatial_state.boards:
            cells_to_sync = list(spatial_state.boards[board_id].hexes.values())
        else:
            cells_to_sync = list(spatial_state.global_hexes.values())

        for cell in cells_to_sync:
            terrain_val = cell.base_terrain.value if hasattr(cell.base_terrain, "value") else str(cell.base_terrain)
            wsm.set_hex(
                col=cell.col,
                row=cell.row,
                terrain_type=terrain_val,
                elevation=cell.elevation,
                obstacle_height=cell.obstacle_height
            )
