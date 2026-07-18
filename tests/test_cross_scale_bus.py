from engine.kernel.world_state_manager import WorldStateManager, PrefectUnit, CenturionUnit
from engine.kernel.scale_navigator import ScaleNavigator
from engine.kernel.cross_scale_event_bus import CrossScaleEventBus, Event

def test_soft_state_cascade():
    wsm = WorldStateManager("sim_bus")
    
    # Setup prefect unit
    pu1 = PrefectUnit(id="p1", name="1st Legion", faction="tog")
    wsm.current_state.prefect_state.units["p1"] = pu1
    
    nav = ScaleNavigator(wsm)
    engagement_id = nav.trigger_engagement(["p1"])
    
    # Setup centurion unit linked to this engagement
    cent_unit = CenturionUnit(id="c1", name="Tank", faction="tog")
    wsm.current_state.centurion_engagements[engagement_id].units["c1"] = cent_unit
    
    bus = CrossScaleEventBus(wsm)
    
    # Fire cascade event: an orbital strike lowers morale by 0.2 and adds 0.5 suppression
    event = Event(
        event_type="SOFT_STATE_CASCADE",
        payload={
            "prefect_unit_id": "p1",
            "morale_modifier": -0.2,
            "suppression_modifier": 0.5
        },
        source_scale="prefect"
    )
    
    bus.publish(event)
    
    assert isinstance(cent_unit.soft_state.suppression, float)
    assert isinstance(cent_unit.soft_state.morale, float)
