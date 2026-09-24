import os
import pytest
from engine.kernel.spatial_models import (
    HexCoordinateConverter,
    HexOrientation,
    TerrainType,
    HexCell,
    SpatialBoard,
    ManagedSpatialWorldState
)
from engine.kernel.spatial_los import SpatialLOSArbiter, SpatialPathfinder
from engine.ingestion.vassal_importer import VassalMapImporter
from engine.kernel.world_state_manager import WorldStateManager, CenturionUnit
from engine.simulation.dynamic_engine import DynamicEngine


def test_coordinate_conversions():
    # 1. Alphanumeric Parsing
    c, r = HexCoordinateConverter.parse_coord("A1")
    assert (c, r) == (1, 1)

    c, r = HexCoordinateConverter.parse_coord("B05")
    assert (c, r) == (2, 5)

    c, r = HexCoordinateConverter.parse_coord("AA12")
    assert (c, r) == (27, 12)

    # 2. 4-digit String Parsing
    c, r = HexCoordinateConverter.parse_coord("1001")
    assert (c, r) == (10, 1)

    c, r = HexCoordinateConverter.parse_coord("0102")
    assert (c, r) == (1, 2)

    # 3. Formatter
    assert HexCoordinateConverter.format_coord_digits(10, 1) == "1001"
    assert HexCoordinateConverter.format_coord_alpha(1, 1) == "A1"
    assert HexCoordinateConverter.format_coord_alpha(27, 12) == "AA12"

    # 4. Axial and Cube distance
    q, r_ax = HexCoordinateConverter.col_row_to_axial(1, 1)
    x, y, z = HexCoordinateConverter.axial_to_cube(q, r_ax)
    assert x + y + z == 0

    c1 = HexCoordinateConverter.axial_to_cube(*HexCoordinateConverter.col_row_to_axial(1, 1))
    c2 = HexCoordinateConverter.axial_to_cube(*HexCoordinateConverter.col_row_to_axial(1, 5))
    dist = HexCoordinateConverter.cube_distance(c1, c2)
    assert dist == 4


def test_vassal_xml_import_string():
    xml_sample = """
    <VASSAL.build.module.Map mapName="Desert Theater">
      <VASSAL.build.module.map.boardPicker.Board 
          boardName="Board 01" 
          width="1000" height="800">
        <VASSAL.build.module.map.boardPicker.board.HexGrid 
            dx="66.4" 
            dy="57.5" 
            x0="33.2" 
            y0="38.0" 
            sideways="false" 
            stagger="true">
          <VASSAL.build.module.map.boardPicker.board.mapgrid.HexGridNumbering 
              type="alphaNumeric" 
              firstRow="1" 
              firstCol="1" 
              hDesc="0101" 
              vDesc="A1"/>
        </VASSAL.build.module.map.boardPicker.board.HexGrid>
        <Zone name="Eastern Forest" location="0505"/>
        <Zone name="Central Ridge" location="0303"/>
      </VASSAL.build.module.map.boardPicker.Board>
    </VASSAL.build.module.Map>
    """
    importer = VassalMapImporter(simulation_id="test_vassal")
    spatial_state = importer.import_xml_string(xml_sample)

    assert "board_01" in spatial_state.boards
    board = spatial_state.boards["board_01"]
    assert board.orientation == HexOrientation.POINTY_TOP
    assert len(board.hexes) > 0

    # Verify parsed zones
    cell_forest = board.get_hex("0505")
    assert cell_forest is not None
    assert cell_forest.base_terrain == TerrainType.LIGHT_WOODS
    assert cell_forest.obstacle_height == 1

    cell_ridge = board.get_hex("0303")
    assert cell_ridge is not None
    assert cell_ridge.elevation == 1


def test_wsm_vassal_loading_and_los():
    wsm = WorldStateManager("sim_los_test")
    
    # Create 5 in-line hexes: 0101 to 0105
    for row in range(1, 6):
        wsm.set_hex(1, row, "Clear", elevation=0)

    # Place hill in the middle (0103)
    wsm.set_hex(1, 3, "Clear", elevation=2)

    # Origin at 0101 (elevation 0), Target at 0105 (elevation 0)
    origin_cell = wsm.spatial_state.get_cell("0101")
    target_cell = wsm.spatial_state.get_cell("0105")

    is_clear, blockers, reason = SpatialLOSArbiter.check_los(origin_cell, target_cell, wsm.spatial_state)
    assert not is_clear
    assert "0103" in blockers

    # Now raise target to elevation 5 -> LOS should clear over hill
    wsm.set_hex(1, 5, "Clear", elevation=5)
    target_cell = wsm.spatial_state.get_cell("0105")
    is_clear_elevated, _, _ = SpatialLOSArbiter.check_los(origin_cell, target_cell, wsm.spatial_state)
    assert is_clear_elevated


def test_smoke_blocks_los():
    wsm = WorldStateManager("sim_smoke_los")
    for row in range(1, 5):
        wsm.set_hex(1, row, "Clear", elevation=0)

    # Drop dense smoke on 0102
    cell_02 = wsm.spatial_state.get_cell("0102")
    cell_02.dynamic_effects.append("Dense Smoke")

    is_clear, blockers, _ = SpatialLOSArbiter.check_los("0101", "0104", wsm.spatial_state)
    assert not is_clear
    assert "0102" in blockers


def test_spatial_pathfinder():
    wsm = WorldStateManager("sim_path_test")
    # Setup 4x4 grid
    for c in range(1, 5):
        for r in range(1, 5):
            wsm.set_hex(c, r, "Clear", elevation=0)

    # Place impassable deep water on 0102 and 0202
    wsm.set_hex(1, 2, "Deep Water", elevation=0)
    wsm.set_hex(2, 2, "Deep Water", elevation=0)

    path, cost = SpatialPathfinder.find_path("0101", "0103", wsm.spatial_state, unit_mode="tracked")
    assert path is not None
    assert len(path) >= 3
    # Verify path does not step onto deep water
    for step in path:
        assert step.base_terrain != TerrainType.WATER_DEEP


def test_dynamic_engine_spatial_integration():
    engine = DynamicEngine("engine_spatial_test")
    engine.initialize_default_scenario()

    # Query LOS between default units
    is_clear, blockers, reason = engine.check_los("cw_tank_1", "tog_grav_1")
    assert isinstance(is_clear, bool)

    # Pathfind from cw_tank_1 to tog_grav_1
    path, cost = engine.find_path("cw_tank_1", "tog_grav_1")
    assert path is not None
    assert cost > 0.0


def test_vassal_raster_terrain_classifier(tmp_path):
    from PIL import Image
    from engine.ingestion import VassalRasterTerrainClassifier

    # Create a synthetic 200x200 board image with green (woods) and blue (water) zones
    img = Image.new("RGB", (200, 200), color=(230, 220, 180)) # Clear/sand
    # Paint top-left green for woods
    for x in range(0, 100):
        for y in range(0, 100):
            img.putpixel((x, y), (34, 139, 34)) # Forest Green
    # Paint bottom-right blue for river
    for x in range(100, 200):
        for y in range(100, 200):
            img.putpixel((x, y), (30, 100, 220)) # Water Blue

    test_img_path = os.path.join(tmp_path, "synthetic_board.png")
    img.save(test_img_path)

    classifier = VassalRasterTerrainClassifier(test_img_path)
    grid_results = classifier.scan_hex_grid(dx=50.0, dy=50.0, x0=25.0, y0=25.0)

    # Check top-left hex (0101) is woods
    assert "0101" in grid_results
    assert "Woods" in grid_results["0101"]["terrain"]

    # Check bottom-right hex (0303) is water/river
    assert "0303" in grid_results
    assert "Water" in grid_results["0303"]["terrain"] or "River" in grid_results["0303"]["terrain"]
