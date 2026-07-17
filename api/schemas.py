from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class NewSimulationRequest(BaseModel):
    corpus_profile: str = "data/renegade_legion_profile.json"
    mode: str = "advisory"  # "autonomous", "advisory", "hitl"
    hitl_faction: Optional[str] = None  # "commonwealth" or "tog"
    information_mode: str = "full"  # "full" or "fog_of_war"

class NewSimulationResponse(BaseModel):
    simulation_id: str
    turn: int
    units_count: int

class RecommendActionsRequest(BaseModel):
    unit_id: str
    objective: str = "maximize_damage"

class AdvanceTurnRequest(BaseModel):
    unit_id: str
    chosen_action: Dict[str, Any]
