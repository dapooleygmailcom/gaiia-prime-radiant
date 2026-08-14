from engine.simulation.dynamic_engine import DynamicEngine

def setup_5_turn_test(sim_id: str):
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

def test_agentic_5_turn_engagement():
    """
    Run a full 5-turn engagement to test state persistence, memory context, and multi-turn mechanics.
    """
    engine, lib, hor = setup_5_turn_test("agentic_5_turn_duel")
    
    objective = "Close with the enemy and destroy them. Manage your heat, ammo, and facing across multiple turns."
    
    # We execute all phases for 5 turns (Initiative, Movement, Combat)
    # By passing initiative_winner=None, the engine will randomly select initiative each turn.
    engine.arbiter.orchestrate_game(engine, objective=objective, target_phase=None, turns=5, initiative_winner=None)
    
    # Assertions to ensure the simulation completed all 5 turns
    state = engine.wsm.get_state()
    assert state.turn == 5, f"Expected simulation to reach turn 5, but stopped at turn {state.turn}"
    
    # We can print out the final damage states just to be sure
    print("\n--- FINAL COMBAT REPORT ---")
    if hasattr(lib, 'damage_state') and lib.damage_state:
        print(f"Liberator (lib1) Damage Grid: {dict(lib.damage_state.armor_grids)}")
    if hasattr(hor, 'damage_state') and hor.damage_state:
        print(f"Horatius (hor1) Damage Grid: {dict(hor.damage_state.armor_grids)}")

if __name__ == '__main__':
    test_agentic_5_turn_engagement()
