from engine.kernel.soft_state_layer import SoftState

def test_soft_state_initialization():
    state = SoftState()
    assert state.morale == 1.0
    assert state.suppression == 0.0
    assert state.command_cohesion == 1.0
    assert state.supply_state == 1.0

def test_apply_suppression():
    state = SoftState()
    state.apply_suppression(0.4)
    assert state.suppression == 0.4
    assert state.morale == 0.8  # Decreases by suppression * 0.5

def test_apply_extreme_suppression():
    state = SoftState()
    state.apply_suppression(1.5)
    assert state.suppression == 1.0  # Bounded at 1.0
    assert state.morale == 0.5

def test_decay_suppression():
    state = SoftState(suppression=0.5)
    state.decay_suppression(0.2)
    assert state.suppression == 0.3
    state.decay_suppression(0.5)
    assert state.suppression == 0.0

def test_recover_morale():
    state = SoftState(morale=0.5, suppression=0.0)
    state.recover_morale(0.1)
    assert state.morale == 0.6

def test_no_recover_morale_when_suppressed():
    state = SoftState(morale=0.5, suppression=0.2)
    state.recover_morale(0.1)
    assert state.morale == 0.5  # Morale should not recover while suppressed

def test_apply_casualty():
    state = SoftState()
    state.apply_casualty(0.2)
    assert state.morale == 0.7  # 1.0 - (0.2 * 1.5)
