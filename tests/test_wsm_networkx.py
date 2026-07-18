from engine.kernel.world_state_manager import WorldStateManager, CenturionUnit

def test_networkx_graph_integration():
    wsm = WorldStateManager("sim_nx")
    
    # Set a hex
    wsm.set_hex(q=2, r=3, terrain_type="rough")
    
    # Add a unit
    unit = CenturionUnit(id="nx_tank_1", name="Liberator", faction="tog", position=[2, 3])
    wsm.add_unit(unit)
    
    # Check that graph is populated
    assert wsm.graph.has_node("nx_tank_1")
    assert wsm.graph.has_node("hex_2_3")
    
    # Check edges
    assert wsm.graph.has_edge("nx_tank_1", "hex_2_3")
    edge_data = wsm.graph.get_edge_data("nx_tank_1", "hex_2_3")
    assert edge_data["relation"] == "LOCATED_IN"
    
def test_networkx_graph_rebuild_on_rollback():
    wsm = WorldStateManager("sim_nx2")
    
    # Add initial unit
    unit1 = CenturionUnit(id="tank_a", name="Liberator", faction="tog", position=[0, 0])
    wsm.add_unit(unit1)
    
    wsm.advance_turn()
    
    # Now in turn 1. Add another unit
    unit2 = CenturionUnit(id="tank_b", name="Liberator", faction="tog", position=[1, 1])
    wsm.add_unit(unit2)
    
    assert wsm.graph.has_node("tank_a")
    assert wsm.graph.has_node("tank_b")
    
    # Rollback to turn 0
    wsm.rollback(0)
    
    # tank_b should not exist in the graph anymore
    assert wsm.graph.has_node("tank_a")
    assert not wsm.graph.has_node("tank_b")
