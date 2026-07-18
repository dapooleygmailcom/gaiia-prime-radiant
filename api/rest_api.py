import uuid
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from api.schemas import NewSimulationRequest, NewSimulationResponse
from engine.kernel.world_state_manager import WorldStateManager, CenturionUnit
from engine.kernel.soft_state_layer import SoftState
from engine.rules.rules_interface import RulesInterface

app = FastAPI(title="Gaiia Prime Radiant REST API", version="0.1.0")

# In-memory dictionary storing active simulations
# Stores {"wsm": WorldStateManager, "config": NewSimulationRequest}
active_simulations: Dict[str, Any] = {}

# Instantiate rule integration globally
rules_interface = RulesInterface()

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
    try:
        cw_unit = wsm.create_unit_from_entity("cw_tank_1", "commonwealth", "rl_liberator", rules_interface)
        cw_unit.position = [0, 0]
        cw_unit.soft_state = SoftState(morale=1.0, suppression=0.0)
    except Exception as e:
        print(f"Warning: Falling back to manual cw_unit creation. Error: {e}")
        cw_unit = CenturionUnit(
            id="cw_tank_1",
            name="Commonwealth Grav Tank Alpha",
            faction="commonwealth",
            position=[0, 0],
            velocity=0,
            thrust_points=10,
            soft_state=SoftState(morale=1.0, suppression=0.0)
        )
        wsm.add_unit(cw_unit)

    try:
        tog_unit = wsm.create_unit_from_entity("tog_grav_1", "tog", "tog_horatius", rules_interface)
        tog_unit.position = [1, 1]
        tog_unit.soft_state = SoftState(morale=1.0, suppression=0.0)
    except Exception as e:
        print(f"Warning: Falling back to manual tog_unit creation. Error: {e}")
        tog_unit = CenturionUnit(
            id="tog_grav_1",
            name="TOG Grav Tank Victrix",
            faction="tog",
            position=[1, 1],
            velocity=0,
            thrust_points=10,
            soft_state=SoftState(morale=1.0, suppression=0.0)
        )
        wsm.add_unit(tog_unit)

    wsm.take_snapshot()

    active_simulations[sim_id] = {
        "wsm": wsm,
        "config": req
    }
    return NewSimulationResponse(
        simulation_id=sim_id,
        turn=wsm.get_state().turn,
        units_count=len(wsm.get_state().units)
    )

@app.get("/simulation/{sim_id}/state")
def get_state(sim_id: str):
    if sim_id not in active_simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    wsm = active_simulations[sim_id]["wsm"]
    return wsm.current_state

