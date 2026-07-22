import uuid
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from api.schemas import NewSimulationRequest, NewSimulationResponse, RecommendActionsRequest, AdvanceTurnRequest
from engine.simulation.dynamic_engine import DynamicEngine

app = FastAPI(title="Gaiia Prime Radiant REST API", version="0.1.0")

# In-memory dictionary storing active simulations
# Stores {"engine": DynamicEngine, "config": NewSimulationRequest}
active_simulations: Dict[str, Any] = {}

@app.post("/simulation/new", response_model=NewSimulationResponse)
def create_simulation(req: NewSimulationRequest):
    sim_id = str(uuid.uuid4())
    engine = DynamicEngine(sim_id)
    engine.initialize_default_scenario()

    active_simulations[sim_id] = {
        "engine": engine,
        "config": req
    }
    
    state = engine.wsm.get_state()
    return NewSimulationResponse(
        simulation_id=sim_id,
        turn=state.turn,
        units_count=len(state.units)
    )

@app.get("/simulation/{sim_id}/state")
def get_state(sim_id: str):
    if sim_id not in active_simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    engine = active_simulations[sim_id]["engine"]
    return engine.wsm.current_state

@app.post("/simulation/{sim_id}/recommend_actions")
def recommend_actions(sim_id: str, req: RecommendActionsRequest):
    if sim_id not in active_simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    engine = active_simulations[sim_id]["engine"]
    
    try:
        recommendation = engine.recommend_actions(req.unit_id, req.objective)
        return {"recommendation": recommendation}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/simulation/{sim_id}/advance_turn")
def advance_turn(sim_id: str, req: AdvanceTurnRequest):
    if sim_id not in active_simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    engine = active_simulations[sim_id]["engine"]
    
    try:
        result = engine.advance_turn(req.unit_id, req.chosen_action)
        return {"result": result, "new_state": engine.wsm.current_state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

