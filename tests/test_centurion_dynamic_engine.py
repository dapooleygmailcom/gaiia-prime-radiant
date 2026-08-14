import pytest
from engine.simulation.dynamic_engine import DynamicEngine
from engine.rules.rule_feedback_interface import RuleFeedbackInterface

def test_master_arbiter_generates_grid_math():
    """
    Validates that the Master Arbiter can generate high-fidelity grid mathematics 
    for Renegade Legion damage templates based on a situation description.
    """
    import tempfile
    import os
    
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    
    engine = DynamicEngine(simulation_id="test_grid_math_001")
    rfi_logger = RuleFeedbackInterface(db_path=db_path)
    
    situation = """
    I need a function `apply_damage_template(armor_grid, damage_template, start_x, start_y)` 
    that takes a 10x10 list of lists (representing armor, where 0 is intact and 1 is destroyed), 
    and a `damage_template` which is a list of (x,y) tuples.
    The function must iterate through the tuples, offset them by `start_x` and `start_y`, 
    and set `armor_grid[start_x + x][start_y + y] = 1`.
    If the index is out of bounds, it should safely ignore it.
    Return the modified armor_grid.
    """
    
    # Force the arbiter to generate the rule
    success = engine.arbiter.generate_mechanic(situation, rfi_logger=rfi_logger, simulation_id="test_grid_math_001")
    
    assert success is True, "Master Arbiter failed to generate and compile the function."
    assert "apply_damage_template" in engine.dynamic_globals, "The generated function was not injected into dynamic globals."
    
    # Now let's test the generated math
    armor_grid = [[0 for _ in range(10)] for _ in range(10)]
    damage_template = [(0,0), (1,0), (0,1), (1,1)] # A 2x2 square
    start_x, start_y = 4, 4
    
    # Call the dynamically generated function
    func = engine.dynamic_globals["apply_damage_template"]
    result_grid = func(armor_grid, damage_template, start_x, start_y)
    
    assert result_grid[4][4] == 1
    assert result_grid[5][4] == 1
    assert result_grid[4][5] == 1
    assert result_grid[5][5] == 1
    
    # Verify bounds checking works (start at edge)
    armor_grid_2 = [[0 for _ in range(10)] for _ in range(10)]
    result_grid_2 = func(armor_grid_2, damage_template, 9, 9)
    assert result_grid_2[9][9] == 1
    # 10,9 and 9,10 and 10,10 are out of bounds and should be ignored

def test_side_commander_evaluates():
    """
    Validates that a Side Commander can call dynamically generated math.
    """
    engine = DynamicEngine(simulation_id="test_commander_001")
    
    # First generate a simple rule
    situation = """
    Write a function `calculate_hit_chance(base_skill, range_penalty)` that returns 
    base_skill - range_penalty.
    """
    engine.arbiter.generate_mechanic(situation)
    
    assert "calculate_hit_chance" in engine.dynamic_globals
    
    # Evaluate via side commander (this is mostly ensuring eval works in the shared namespace)
    engine.add_commander("TOG")
    commander = engine.commanders["TOG"]
    
    result = eval("calculate_hit_chance(80, 20)", {"__builtins__": None}, commander.dynamic_globals)
    assert result == 60
