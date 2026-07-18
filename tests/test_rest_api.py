from fastapi.testclient import TestClient
from api.rest_api import app

client = TestClient(app)

def test_api_simulation_lifecycle():
    # 1. Create a new simulation session
    res_new = client.post("/simulation/new", json={
        "corpus_profile": "data/renegade_legion_profile.json",
        "mode": "advisory"
    })
    assert res_new.status_code == 200
    data = res_new.json()
    assert "simulation_id" in data
    sim_id = data["simulation_id"]
    assert data["turn"] == 0
    assert data["units_count"] == 2

    # 2. Get the state
    res_state = client.get(f"/simulation/{sim_id}/state")
    assert res_state.status_code == 200
    state_data = res_state.json()
    assert state_data["simulation_id"] == sim_id
    
    # We check if units exist in centurion_engagements or similar, 
    # but the API doesn't expose flat `units` anymore if it's purely GlobalWorldState.
    # The GlobalWorldState has `centurion_engagements` and `prefect_state`.
    assert "prefect_state" in state_data
