from engine.kernel.world_state_manager import WorldStateManager, PrefectUnit, CenturionUnit
from engine.kernel.scale_navigator import ScaleNavigator

def test_trigger_engagement():
    wsm = WorldStateManager("sim1")
    
    # Add some prefect units
    pu1 = PrefectUnit(id="p1", name="1st Legion", faction="tog")
    wsm.current_state.prefect_state.units["p1"] = pu1
    
    nav = ScaleNavigator(wsm)
    engagement_id = nav.trigger_engagement(["p1"])
    
    assert engagement_id in wsm.current_state.centurion_engagements
    assert pu1.linked_centurion_engagement_id == engagement_id
    assert engagement_id in nav.active_engagements
    
def test_resolve_engagement():
    wsm = WorldStateManager("sim2")
    pu1 = PrefectUnit(id="p1", name="1st Legion", faction="tog")
    wsm.current_state.prefect_state.units["p1"] = pu1
    
    nav = ScaleNavigator(wsm)
    engagement_id = nav.trigger_engagement(["p1"])
    
    nav.resolve_engagement(engagement_id)
    
    assert pu1.linked_centurion_engagement_id is None
    assert engagement_id not in nav.active_engagements
    
def test_advance_prefect_turn():
    wsm = WorldStateManager("sim3")
    nav = ScaleNavigator(wsm)
    
    engagement_id = nav.trigger_engagement([])
    
    # Add a centurion unit to test turn clock
    cent_unit = CenturionUnit(id="c1", name="Tank", faction="tog")
    cent_unit.soft_state.apply_suppression(1.0)
    wsm.current_state.centurion_engagements[engagement_id].units["c1"] = cent_unit
    
    assert wsm.current_state.prefect_state.turn == 0
    assert wsm.current_state.centurion_engagements[engagement_id].turn == 0
    
    nav.advance_prefect_turn(centurion_turns_per_prefect_turn=2)
    
    assert wsm.current_state.prefect_state.turn == 1
    assert wsm.current_state.centurion_engagements[engagement_id].turn == 2
    # Check that the centurion unit advanced 2 turns (suppression decays by 0.2 per turn)
    assert cent_unit.soft_state.suppression == 0.6
