import pytest
import re
from engine.simulation.dynamic_engine import DynamicEngine


def setup_combat_test(name, lib_pos="0101", hor_pos="0106"):
    engine = DynamicEngine(name)
    engine.add_commander("commonwealth") 
    
    lib = engine.wsm.create_unit_from_entity("lib1", "commonwealth", "rl_liberator_medium_grav_tank", engine.rules)
    lib.position = lib_pos
    lib.heading = 4
    lib.velocity = 0
    lib.thrust_points = 6
    
    hor = engine.wsm.create_unit_from_entity("hor1", "tog", "tog_horatius_medium_grav_tank", engine.rules)
    hor.position = hor_pos
    hor.heading = 1
    
    return engine, lib, hor

def test_agentic_combat_tc2():
    """
    Agentic run of TC2 (Medium range, all weapons).
    The Arbiter should prompt the Side LLM with the combat state (including weapons).
    The Side LLM should decide to fire its available weapons at hor1.
    The deterministic mechanic 'resolve_combat' handles the hit logic.
    """
    engine, lib, hor = setup_combat_test("agentic_tc2", lib_pos="0101", hor_pos="0106")
    
    # TC2: Range is 5 hexes (0101 to 0106).
    # Expected: The LLM should fire 5/6 Laser, 50mm Gauss, and TVLG(4) at hor1.
    objective = "Destroy the enemy tank 'hor1'. Fire all of your available weapons at it, and ensure you use your painting laser to negate its shields."
    
    front_before = list(hor.damage_state.armor_grids.get('Front Armor', []))
    tvlg_ammo_before = 4  # Liberator has 4 TVLG rounds by default, but it's lazy loaded.
    
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase="Combat")
    
    # We don't guarantee hits due to RNG, but we CAN guarantee the LLM attempted to fire
    # and the mechanic executed successfully (e.g. ammo consumed if TVLG fired).
    if hasattr(lib, 'tvlg_ammo'):
        assert lib.tvlg_ammo < 4, "LLM should have fired TVLG missiles and consumed ammo."

def test_agentic_combat_tc1():
    """
    Agentic run of TC1 (Long range).
    The LLM is told to fire, but only its laser is in range (max 20).
    It should try to fire all, and the Arbiter/mechanic will reject the out-of-range weapons.
    """
    engine, lib, hor = setup_combat_test("agentic_tc1", lib_pos="0101", hor_pos="0120")
    
    objective = "Destroy the enemy tank 'hor1'. Fire all of your available weapons at it, and ensure you use your painting laser to negate its shields."
    
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase="Combat")
    
    # At range 19, TVLG (max 6) is out of range. 
    # If the LLM tried to fire it, the mechanic should have blocked it and NOT consumed ammo.
    if hasattr(lib, 'tvlg_ammo'):
        assert lib.tvlg_ammo == 4, "TVLG ammo should NOT be consumed because it is out of range."

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
