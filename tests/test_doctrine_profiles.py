from engine.planner.doctrine_profiles import DoctrineProfileManager

def test_doctrine_profile_manager_aggressive():
    manager = DoctrineProfileManager()
    
    # Test aggressive doctrine bias
    score_modifier = manager.get_action_modifier(faction="tog", doctrine="aggressive", action_type="fire")
    
    # Aggressive doctrine should heavily favor "fire" actions
    assert score_modifier > 1.0
    
    # Aggressive doctrine should penalize "move" away from enemy (or just neutral)
    move_modifier = manager.get_action_modifier(faction="tog", doctrine="aggressive", action_type="move")
    assert move_modifier <= 1.0

def test_doctrine_profile_manager_flexible():
    manager = DoctrineProfileManager()
    
    # Test flexible doctrine bias (Commonwealth)
    score_modifier = manager.get_action_modifier(faction="commonwealth", doctrine="flexible", action_type="move")
    
    # Flexible doctrine favors maneuver ("move") more than aggressive does
    assert score_modifier > 1.0
