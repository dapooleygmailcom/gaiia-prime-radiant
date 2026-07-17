from engine.kernel.world_state_manager import WorldStateManager, CenturionUnit
from engine.kernel.soft_state_layer import SoftState

def test_wsm_initialization():
    wsm = WorldStateManager("test_sim")
    state = wsm.get_state()
    assert state.simulation_id == "test_sim"
    assert state.turn == 0
    assert len(state.units) == 0

def test_wsm_add_unit_and_hex():
    wsm = WorldStateManager("test_sim")
    unit = CenturionUnit(id="u1", name="Unit 1", faction="tog", position=[1, 2])
    wsm.add_unit(unit)
    wsm.set_hex(1, 2, "woods")

    state = wsm.get_state()
    assert len(state.units) == 1
    assert state.units["u1"].name == "Unit 1"
    assert state.map_hexes["1,2"] == "woods"

def test_wsm_snapshot_and_rollback():
    wsm = WorldStateManager("test_sim")
    unit = CenturionUnit(id="u1", name="Unit 1", faction="tog", position=[1, 2])
    wsm.add_unit(unit)
    
    # Take initial turn 0 snapshot
    wsm.take_snapshot()

    # Change state in turn 1
    wsm.current_state.turn = 1
    wsm.current_state.units["u1"].position = [3, 4]
    wsm.current_state.units["u1"].soft_state.apply_suppression(0.5)

    # Verify changed state
    assert wsm.current_state.units["u1"].position == [3, 4]
    assert wsm.current_state.units["u1"].soft_state.suppression == 0.5

    # Rollback to turn 0
    success = wsm.rollback(0)
    assert success is True
    assert wsm.current_state.turn == 0
    assert wsm.current_state.units["u1"].position == [1, 2]
    assert wsm.current_state.units["u1"].soft_state.suppression == 0.0

def test_wsm_advance_turn():
    wsm = WorldStateManager("test_sim")
    unit = CenturionUnit(
        id="u1", 
        name="Unit 1", 
        faction="tog", 
        soft_state=SoftState(morale=0.8, suppression=0.3)
    )
    wsm.add_unit(unit)

    wsm.advance_turn()
    assert wsm.current_state.turn == 1
    # Check suppression decayed by 0.2
    assert wsm.current_state.units["u1"].soft_state.suppression == 0.1
    # Check morale didn't recover because suppression was > 0 during the turn (before decay or condition)
    # Actually, in advance_turn morale recovery occurs when suppression == 0.
    # Since suppression decayed from 0.3 -> 0.1, it's still > 0, so morale stays at 0.8.
    assert wsm.current_state.units["u1"].soft_state.morale == 0.8
