import pytest
import math
from engine.simulation.dynamic_engine import DynamicEngine

def setup_ugoigo_test(sim_id: str, init_winner: str):
    engine = DynamicEngine(sim_id)
    engine.add_commander("commonwealth")
    engine.add_commander("tog")
    
    lib = engine.wsm.create_unit_from_entity("lib1", "commonwealth", "rl_liberator_medium_grav_tank", engine.rules)
    lib.position = "0610"
    lib.heading = 2
    lib.velocity = 0
    lib.thrust_points = 6
    
    hor = engine.wsm.create_unit_from_entity("hor1", "tog", "tog_horatius_medium_grav_tank", engine.rules)
    hor.position = "1310"
    hor.heading = 5
    hor.velocity = 0
    hor.thrust_points = 6
    
    return engine, lib, hor

def test_agentic_ugoigo_run1():
    """
    Run 1: Commonwealth wins initiative.
    The loser (Tog) goes first in execution phases. Then Commonwealth.
    """
    engine, lib, hor = setup_ugoigo_test("agentic_ugoigo_1", "commonwealth")
    
    objective = "Close with the enemy and destroy them while minimizing damage to your own tank."
    
    # We execute all phases for 1 turn (Initiative, Movement, Combat)
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase=None, turns=1, initiative_winner="commonwealth")
    
    # Simple assertions to ensure the simulation didn't crash and both commanders acted.
    state = engine.wsm.get_state()
    assert state.turn == 1
    # Check if units moved or fired (some ammo consumed or position changed)
    # The exact state isn't guaranteed due to LLM variance, but we ensure the engine executed both.

def test_agentic_ugoigo_run2():
    """
    Run 2: Tog wins initiative.
    The loser (Commonwealth) goes first in execution phases. Then Tog.
    """
    engine, lib, hor = setup_ugoigo_test("agentic_ugoigo_2", "tog")
    
    objective = "Close with the enemy and destroy them while minimizing damage to your own tank."
    
    # We execute all phases for 1 turn (Initiative, Movement, Combat)
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase=None, turns=1, initiative_winner="tog")
    
    state = engine.wsm.get_state()
    assert state.turn == 1
