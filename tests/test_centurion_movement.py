import pytest
import re
from engine.simulation.dynamic_engine import DynamicEngine


def setup_test(name, vel=0):
    engine = DynamicEngine(name)
    engine.add_commander("commonwealth") 
    
    lib = engine.wsm.create_unit_from_entity("lib1", "commonwealth", "rl_liberator_medium_grav_tank", engine.rules)
    lib.position = "1001"
    lib.heading = 4
    lib.velocity = vel
    lib.thrust_points = 6  # Liberator has 6 thrust
    
    hor = engine.wsm.create_unit_from_entity("hor1", "tog", "tog_horatius_medium_grav_tank", engine.rules)
    hor.position = "1020"
    hor.heading = 1
    
    return engine, lib, hor

def test_movement_close_enemy_vel_0():
    # TC1: apply 6 Thrust to Velocity and move 6 hexes to 6,10 facing 4
    engine, lib, hor = setup_test("tc1_vel_0", vel=0)
    
    # We rely on the Arbiter's generic orchestration loop.
    # The objective is injected directly into the active Commander's prompt via the Arbiter.
    # We pass target_phase="Movement" so it only runs the movement phase for this test.
    objective = "get as close to the enemy tank as you can"
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase="Movement")
    
    assert lib.position == "1007"
    assert lib.velocity == 6
    assert lib.heading == 4
    assert lib.thrust_points == 0

def test_movement_close_enemy_vel_5():
    # TC2: apply 6 Thrust to Velocity and move 11 hexes to 1012 facing 4
    engine, lib, hor = setup_test("tc2_vel_5", vel=5)
    
    objective = "cover maximum distance THIS TURN. Ignore all risks, do not worry about deceleration. SPEND ALL YOUR THRUST ON ACCELERATION to get closest to the enemy."
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase="Movement")
    
    assert lib.position == "1012"
    assert lib.velocity == 11
    assert lib.heading == 4
    assert lib.thrust_points == 0

def test_movement_digging_charges():
    # TC3: Apply 0 thrust to Velocity and move 5 hexes to 1006 and deaccelerate using 5 thrust to velocity 0 and fire digging cannons.
    engine, lib, hor = setup_test("tc3_digging", vel=5)
    
    objective = "fire digging charges. This requires you to end your movement with exactly 0 velocity. You must allocate exactly enough thrust to decelerate to 0 at the end of your movement. Do not accelerate."
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase="Movement")
    
    assert lib.position == "1006"
    assert lib.velocity == 0
    assert lib.heading == 4
    assert lib.thrust_points == 1 # 6 - 5 = 1

def test_movement_facing_changes():
    # TC4: hexes moved before can change direction by 1 face if velocity is 5,10,15 = 1,2,3
    engine, lib, hor = setup_test("tc4_facing", vel=5)
    turn_radius_func = engine.arbiter.get_or_generate_mechanic(
        "calculate_turn_radius",
        "I need a python function `calculate_turn_radius(velocity)` that returns the number of hexes a grav vehicle must move forward before changing facing by 1 hex side. Hint: Look for the 'Turning Radius' rule based on velocity in Renegade Legion."
    )
    assert turn_radius_func(5) == 1
    assert turn_radius_func(10) == 2
    assert turn_radius_func(15) == 3

def test_movement_elevation():
    # TC5: apply 6 thrust to velocity and move 3 hexes (2 per hex going up hill) to 1004 facing 4.
    engine, lib, hor = setup_test("tc5_elevation", vel=0)
    for row in range(1, 21):
        elevation = min(row, 21 - row)  # peaks in the middle
        engine.wsm.set_hex(10, row, "Clear", elevation=elevation)
        
    objective = "move as far up the hill as physically possible THIS TURN. Ignore all risks, do not worry about deceleration. SPEND ALL YOUR THRUST ON ACCELERATION."
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase="Movement")
    
    assert lib.position == "1004"
    assert lib.velocity == 6
    assert lib.heading == 4
    
def test_movement_light_woods_safe_speed():
    # TC6: apply 3 Thrust to Velocity and move 4 hexes (2 per hex going through light woods) to 1005 facing 4.
    engine, lib, hor = setup_test("tc6_light_woods", vel=5)
    for row in range(1, 21):
        engine.wsm.set_hex(10, row, "Light Woods", elevation=0)
        
    objective = "move as fast as possible through the woods WITHOUT exceeding Safe Speed (velocity 8). You must allocate exactly enough thrust to accelerate to velocity 8, and no more."
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase="Movement")
    
    assert lib.position == "1005"
    assert lib.velocity == 8
    assert lib.heading == 4
    assert lib.thrust_points == 3 # 6 - 3 = 3

def setup_test_tc7(name, vel=4):
    engine = DynamicEngine(name)
    engine.add_commander("commonwealth") 
    
    lib1 = engine.wsm.create_unit_from_entity("lib1", "commonwealth", "rl_liberator_medium_grav_tank", engine.rules)
    lib1.position = "0202"
    lib1.heading = 3
    lib1.velocity = vel
    lib1.thrust_points = 6
    
    lib2 = engine.wsm.create_unit_from_entity("lib2", "commonwealth", "rl_liberator_medium_grav_tank", engine.rules)
    lib2.position = "0101"
    lib2.heading = 3
    lib2.velocity = vel
    lib2.thrust_points = 6
    
    lib3 = engine.wsm.create_unit_from_entity("lib3", "commonwealth", "rl_liberator_medium_grav_tank", engine.rules)
    lib3.position = "0001"
    lib3.heading = 3
    lib3.velocity = vel
    lib3.thrust_points = 6
    
    river_hexes = [
        "0001", "0101", "0202", "0303", "0304", "0305",
        "0406", "0407", "0408", "0409", "0410",
        "0511", "0610", "0711"
    ]
    for row in range(12, 21):
        river_hexes.append(f"08{row:02d}")
        
    for h in river_hexes:
        col = int(h[:2])
        row = int(h[2:])
        engine.wsm.set_hex(col, row, "River", elevation=0)
        
    return engine, lib1, lib2, lib3, river_hexes

def test_movement_river_column():
    # TC7: follow the river with 3 tanks in column. tanks cannot go outside of a river hex.
    engine, lib1, lib2, lib3, river_hexes = setup_test_tc7("tc7_river", vel=4)
    
    river_hex_str = ", ".join(river_hexes)
    objective = f"The river goes through hexes: {river_hex_str}. Follow the river with all 3 tanks in a column formation. Do not go outside of a river hex. SPEND ALL YOUR THRUST ON ACCELERATION. DO NOT STOP. You must plot the full path along the river hexes for each unit's maximum distance. Do not set EndVelocity to 0. You must issue a separate [MOVE: Unit=..., ...] command for EACH of your units (lib1, lib2, lib3)!"
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase="Movement")
    
    # Lead tank should reach 0610 or 0511
    assert lib1.position in ["0610", "0511"]
    
    # We can also assert they stayed in the river
    for unit in [lib1, lib2, lib3]:
        hex_data = engine.wsm.get_state().map_hexes.get(unit.position, {})
        assert hex_data.get("terrain") == "River", f"Unit {unit.id} went outside the river to {unit.position}!"
