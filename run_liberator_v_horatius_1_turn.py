"""
Radiant Simulation Runner — Centurion Liberator vs Horatius (1-Turn Live Execution).
Map: Centurion Vassal Map 1 (660 hexes, 26x14 grid)
Units: Commonwealth Liberator Gravtank (lib1) vs TOG Horatius Gravtank (hor1)
"""

import os
import sys
import json
from engine.simulation.dynamic_engine import DynamicEngine
from engine.kernel.spatial_models import HexCoordinateConverter


def run_1_turn_duel():
    print("=" * 75)
    print("  GAIIA PRIME RADIANT — CENTURION DUEL (TURN 1)")
    print("  Scenario: Commonwealth Liberator vs TOG Horatius")
    print("  Map: Vassal Centurion Map 1 (660 Tactical Hexes)")
    print("=" * 75)

    # 1. Initialize Engine
    engine = DynamicEngine("centurion_duel_turn1")
    engine.add_commander("commonwealth")
    engine.add_commander("tog")

    # 2. Ingest Centurion Map 1 from Vassal Module
    vmod_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "data/vassal_modules/Renegade_Legion_Centurion_1.2.vmod"
    ))
    print(f"\n[1] Ingesting Vassal Map from: {os.path.basename(vmod_path)}...")
    engine.load_vassal_map(vmod_path, board_id="map_1")
    
    board = engine.wsm.spatial_state.boards.get("map_1")
    print(f"    Board Loaded: '{board.board_name}' | Total Hexes: {len(board.hexes)} | Hex Grid: {board.dx:.2f}px x {board.dy:.2f}px")

    # 3. Spawn Tanks with Counter Bindings
    print("\n[2] Initializing World State Tank Counters...")
    lib = engine.wsm.create_unit_from_entity("lib1", "commonwealth", "rl_liberator_medium_grav_tank", engine.rules)
    lib.position = "0605"
    lib.heading = 3  # Facing South-East towards Horatius
    lib.velocity = 0
    lib.thrust_points = 6
    print(f"    [CW]  Unit: {lib.name} ({lib.id}) | Counter: '{lib.counter_name}' ({lib.counter_image}) | Pos: {lib.position} | Heading: {lib.heading}")

    hor = engine.wsm.create_unit_from_entity("hor1", "tog", "tog_horatius_medium_grav_tank", engine.rules)
    hor.position = "0610"
    hor.heading = 6  # Facing North-West towards Liberator
    hor.velocity = 0
    hor.thrust_points = 6
    print(f"    [TOG] Unit: {hor.name} ({hor.id}) | Counter: '{hor.counter_name}' ({hor.counter_image}) | Pos: {hor.position} | Heading: {hor.heading}")

    # 4. Spatial Geometry & Pre-Turn LOS Check
    print("\n[3] Pre-Turn Spatial Analysis on Map 1:")
    is_clear, blockers, reason = engine.check_los("lib1", "hor1")
    path, mp_cost = engine.find_path("lib1", "hor1")
    
    c1 = HexCoordinateConverter.parse_coord(lib.position)
    c2 = HexCoordinateConverter.parse_coord(hor.position)
    dist = HexCoordinateConverter.cube_distance(
        HexCoordinateConverter.axial_to_cube(*HexCoordinateConverter.col_row_to_axial(c1[0], c1[1])),
        HexCoordinateConverter.axial_to_cube(*HexCoordinateConverter.col_row_to_axial(c2[0], c2[1]))
    )
    print(f"    Direct Distance: {dist} hexes (Range Band: Medium 4-6)")
    print(f"    Line of Sight: {'CLEAR' if is_clear else 'BLOCKED'} ({reason})")
    print(f"    Shortest Movement Path: {' -> '.join([c.hex_id for c in path])} (Cost: {mp_cost:.1f} MP)")

    # 5. Execute Turn 1
    print("\n[4] Executing Turn 1 (Initiative -> Movement -> Combat)...")
    objective = (
        "Engage and destroy the enemy tank. "
        "Use available thrust to maneuver, maintain optimal range, and fire all eligible weapons "
        "including painting laser and missile batteries."
    )
    
    engine.arbiter.orchestrate_game(
        engine,
        objective=objective,
        target_phase=None,
        turns=1,
        initiative_winner="commonwealth"
    )

    # 6. Post-Turn 1 Report
    state = engine.wsm.get_state()
    print("\n" + "=" * 75)
    print(f"  TURN 1 COMPLETED (World State Turn: {state.turn})")
    print("=" * 75)
    print(f"  Commonwealth Liberator (lib1):")
    print(f"    Final Pos: {lib.position} | Velocity: {lib.velocity} | Heading: {lib.heading} | TVLG Ammo: {lib.tvlg_ammo}")
    print(f"    Armor Grids:")
    for facing, grid in lib.damage_state.armor_grids.items():
        print(f"      {facing}: {grid}")

    print(f"\n  TOG Horatius (hor1):")
    print(f"    Final Pos: {hor.position} | Velocity: {hor.velocity} | Heading: {hor.heading} | SMLM Ammo: {hor.smlm_ammo}")
    print(f"    Armor Grids:")
    for facing, grid in hor.damage_state.armor_grids.items():
        print(f"      {facing}: {grid}")

    print("\n[5] Taking Authoritative State Snapshot...")
    snap_id = engine.wsm.take_snapshot()
    print(f"    Snapshot for Turn {snap_id} persisted in WorldStateManager.")
    print("=" * 75)


if __name__ == "__main__":
    run_1_turn_duel()
