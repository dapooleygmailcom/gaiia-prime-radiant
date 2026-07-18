from engine.kernel.world_state_manager import WorldStateManager, PrefectUnit
from engine.modeller.system_dynamics import SystemDynamicsModeller

def test_system_dynamics_lag():
    wsm = WorldStateManager("sim_dyn")
    pu1 = PrefectUnit(id="p1", name="1st Legion", faction="tog")
    wsm.current_state.prefect_state.units["p1"] = pu1
    
    dyn = SystemDynamicsModeller(wsm)
    
    # Supply level starts at 1.0
    assert pu1.supply_level == 1.0
    
    # Trigger a supply cut with a lag of 2 turns
    dyn.trigger_supply_cut("p1", severity=0.6, lag_turns=2)
    
    # Turn 0: No effect
    dyn.advance_turn()
    assert pu1.supply_level == 1.0
    
    wsm.current_state.prefect_state.turn += 1
    
    # Turn 1: No effect
    dyn.advance_turn()
    assert pu1.supply_level == 1.0
    
    wsm.current_state.prefect_state.turn += 1
    
    # Turn 2: Effect hits!
    dyn.advance_turn()
    assert pu1.supply_level == 0.4
    
    # Since supply fell below 0.5, suppression is automatically applied (0.2)
    assert pu1.soft_state.suppression == 0.2
    
def test_system_dynamics_stock_replenishment():
    wsm = WorldStateManager("sim_dyn2")
    dyn = SystemDynamicsModeller(wsm)
    
    dyn.add_stock("fuel_depot_alpha", max_amount=100.0, replenishment=10.0)
    
    dyn.stocks["fuel_depot_alpha"].current_amount = 50.0
    
    dyn.advance_turn()
    
    assert dyn.stocks["fuel_depot_alpha"].current_amount == 60.0
