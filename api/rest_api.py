import uuid
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from api.schemas import NewSimulationRequest, NewSimulationResponse, RecommendActionsRequest, AdvanceTurnRequest
from engine.kernel.world_state_manager import WorldStateManager, CenturionUnit
from engine.kernel.soft_state_layer import SoftState
from engine.rules.rules_interface import RulesInterface
from engine.modeller.outcome_modeller import OutcomeModeller
from engine.planner.action_planner import ActionPlanner

app = FastAPI(title="Gaiia Prime Radiant REST API", version="0.1.0")

# In-memory dictionary storing active simulations
active_simulations: Dict[str, WorldStateManager] = {}

# Instantiate rule integration globally
rules_interface = RulesInterface()
outcome_modeller = OutcomeModeller(rules_interface)
action_planner = ActionPlanner(outcome_modeller)

@app.post("/simulation/new", response_model=NewSimulationResponse)
def create_simulation(req: NewSimulationRequest):
    sim_id = str(uuid.uuid4())
    wsm = WorldStateManager(sim_id)
    
    # Initialize basic Centurion grid map
    wsm.set_hex(0, 0, "woods")
    wsm.set_hex(0, 1, "plain")
    wsm.set_hex(1, 0, "rough")
    wsm.set_hex(1, 1, "plain")

    # Spawn friendly Commonwealth and adversarial TOG units
    cw_unit = CenturionUnit(
        id="cw_tank_1",
        name="Commonwealth Grav Tank Alpha",
        faction="commonwealth",
        position=[0, 0],
        velocity=0,
        thrust_points=10,
        soft_state=SoftState(morale=1.0, suppression=0.0)
    )
    tog_unit = CenturionUnit(
        id="tog_grav_1",
        name="TOG Grav Tank Victrix",
        faction="tog",
        position=[1, 1],
        velocity=0,
        thrust_points=10,
        soft_state=SoftState(morale=1.0, suppression=0.0)
    )

    wsm.add_unit(cw_unit)
    wsm.add_unit(tog_unit)
    wsm.take_snapshot()

    active_simulations[sim_id] = wsm
    return NewSimulationResponse(
        simulation_id=sim_id,
        turn=wsm.current_state.turn,
        units_count=len(wsm.current_state.units)
    )

@app.get("/simulation/{sim_id}/state")
def get_state(sim_id: str):
    if sim_id not in active_simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    wsm = active_simulations[sim_id]
    return wsm.current_state

@app.post("/simulation/{sim_id}/recommend")
def recommend_actions(sim_id: str, req: RecommendActionsRequest):
    if sim_id not in active_simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    wsm = active_simulations[sim_id]
    
    unit = wsm.current_state.units.get(req.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    actions = action_planner.plan_actions(unit, wsm.current_state, req.objective)
    return {"unit_id": req.unit_id, "recommendations": actions}

@app.post("/simulation/{sim_id}/advance")
def advance_turn(sim_id: str, req: AdvanceTurnRequest):
    if sim_id not in active_simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    wsm = active_simulations[sim_id]

    unit = wsm.current_state.units.get(req.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    action = req.chosen_action
    action_type = action.get("action_type")

    # Resolve action
    if action_type == "fire":
        target_id = action.get("target_unit_id")
        target = wsm.current_state.units.get(target_id)
        if target:
            # Resolve combat with outcome modeller
            terrain = wsm.current_state.map_hexes.get(f"{target.position[0]},{target.position[1]}", "plain")
            outcome = outcome_modeller.resolve_combat(unit, target, terrain)
            
            # Apply outcomes to target
            target.soft_state.apply_suppression(outcome["average_suppression_applied"])
            target.soft_state.apply_casualty(outcome["average_damage"])
            if target.soft_state.morale <= 0.1:
                target.is_destroyed = True

    elif action_type == "move":
        dest = action.get("destination")
        if dest and len(dest) == 2:
            unit.position = dest

    # Advance the WSM turn
    wsm.advance_turn()

    return {
        "status": "Turn advanced",
        "turn": wsm.current_state.turn,
        "state": wsm.current_state
    }
