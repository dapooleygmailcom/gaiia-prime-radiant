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
    assert "cw_tank_1" in state_data["units"]
    assert "tog_grav_1" in state_data["units"]

    # 3. Request action recommendation for cw_tank_1
    res_rec = client.post(f"/simulation/{sim_id}/recommend", json={
        "unit_id": "cw_tank_1"
    })
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert rec_data["unit_id"] == "cw_tank_1"
    recs = rec_data["recommendations"]
    assert len(recs) > 0
    # The top recommendation is likely to fire at tog_grav_1 since it has higher score than moving
    first_choice = recs[0]
    assert first_choice["action_type"] in ("fire", "move")

    # 4. Advance the turn using first choice
    res_adv = client.post(f"/simulation/{sim_id}/advance", json={
        "unit_id": "cw_tank_1",
        "chosen_action": first_choice
    })
    assert res_adv.status_code == 200
    adv_data = res_adv.json()
    assert adv_data["status"] == "Turn advanced"
    assert adv_data["turn"] == 1
