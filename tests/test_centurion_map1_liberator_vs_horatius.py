import os
import pytest
from engine.simulation.dynamic_engine import DynamicEngine
from engine.kernel.spatial_models import HexCoordinateConverter, TerrainType


def setup_map1_duel(sim_id: str, lib_pos: str = "0605", hor_pos: str = "0610"):
    """
    Initializes a Centurion Liberator vs Horatius duel on authentic Vassal Map 1,
    with complete tank counter metadata and physical world state.
    """
    engine = DynamicEngine(sim_id)
    engine.add_commander("commonwealth")
    engine.add_commander("tog")

    # Ingest Centurion Map 1 from the Vassal module
    vmod_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "../data/vassal_modules/Renegade_Legion_Centurion_1.2.vmod"
    ))
    engine.load_vassal_map(vmod_path, board_id="map_1")

    # Spawn Commonwealth Liberator Grav Tank with Vassal counter binding
    lib = engine.wsm.create_unit_from_entity("lib1", "commonwealth", "rl_liberator_medium_grav_tank", engine.rules)
    lib.position = lib_pos
    lib.heading = 3  # Facing South-East
    lib.velocity = 0
    lib.thrust_points = 6

    # Spawn TOG Horatius Grav Tank with Vassal counter binding
    hor = engine.wsm.create_unit_from_entity("hor1", "tog", "tog_horatius_medium_grav_tank", engine.rules)
    hor.position = hor_pos
    hor.heading = 6  # Facing North-West
    hor.velocity = 0
    hor.thrust_points = 6

    return engine, lib, hor


def test_centurion_map1_world_state_and_counters():
    """
    Validates that Map 1 is correctly ingested into the WorldStateManager
    and the Liberator and Horatius tank counters are bound to the authoritative world state.
    """
    engine, lib, hor = setup_map1_duel("test_map1_wsm_setup")

    # 1. Verify Map 1 spatial properties in World State
    spatial = engine.wsm.spatial_state
    assert "map_1" in spatial.boards
    board = spatial.boards["map_1"]
    assert board.board_name == "Map 1"
    assert len(board.hexes) == 660
    assert abs(board.dx - 83.92) < 0.1
    assert abs(board.dy - 96.90) < 0.1

    # Verify hexes exist across the entire 26x14 sheet
    assert spatial.get_cell("0101") is not None
    assert spatial.get_cell("2614") is not None

    # 2. Verify Liberator Counter metadata in World State
    assert lib.counter_name == "Liberator"
    assert lib.counter_image == "images/Gravtank-Liberator.png"
    assert lib.counter_prototype == "RL/CW Grav Tank"
    assert lib.thrust_points == 6
    assert lib.tvlg_ammo == 4

    # 3. Verify Horatius Counter metadata in World State
    assert hor.counter_name == "Horatius"
    assert hor.counter_image == "images/Gravtank-Horatius.png"
    assert hor.counter_prototype == "TOG Grav Tank"
    assert hor.thrust_points == 6
    assert hor.smlm_ammo >= 1

    # 4. Verify graph spatial relationships
    assert engine.wsm.graph.has_node("lib1")
    assert engine.wsm.graph.has_node("hor1")


def test_centurion_map1_los_and_pathfinding():
    """
    Validates Line-of-Sight and pathfinding between Liberator and Horatius on Map 1.
    """
    engine, lib, hor = setup_map1_duel("test_map1_los_path", lib_pos="0605", hor_pos="0610")

    # Check LOS on open ground
    is_clear, blockers, reason = engine.check_los("lib1", "hor1")
    assert is_clear is True
    assert len(blockers) == 0

    # Compute optimal movement path along Map 1 hex grid
    path, mp_cost = engine.find_path("lib1", "hor1")
    assert path is not None
    assert len(path) == 6  # 0605 -> 0606 -> 0607 -> 0608 -> 0609 -> 0610
    assert mp_cost == 5.0

    # Test dynamic obstacle occlusion (e.g. Smoke counter dropped in between)
    cell_mid = engine.wsm.spatial_state.get_cell("0607")
    cell_mid.dynamic_effects.append("Dense Smoke")

    is_clear_smoke, blockers_smoke, _ = engine.check_los("lib1", "hor1")
    assert is_clear_smoke is False
    assert "0607" in blockers_smoke


def test_centurion_map1_agentic_combat_duel():
    """
    Executes an agentic combat turn on Map 1 between Liberator (0605) and Horatius (0610).
    Range = 5 hexes (Medium range band 4-6).
    """
    engine, lib, hor = setup_map1_duel("test_map1_combat", lib_pos="0605", hor_pos="0610")

    objective = "Destroy the enemy tank 'hor1'. Fire all eligible weapons at it with painting laser."
    
    # Run combat phase
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase="Combat")

    # Verify combat execution and state transition
    if hasattr(lib, 'tvlg_ammo'):
        assert lib.tvlg_ammo < 4, "Liberator should have fired TVLG missiles at 5-hex range."


def test_centurion_map1_multi_turn_engagement():
    """
    Executes a multi-turn engagement on Map 1 with initiative and movement.
    """
    engine, lib, hor = setup_map1_duel("test_map1_multi_turn", lib_pos="0505", hor_pos="1010")

    objective = "Maneuver to flank the enemy tank and fire heavy weapons."
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase=None, turns=2, initiative_winner="commonwealth")

    state = engine.wsm.get_state()
    assert state.turn == 2
