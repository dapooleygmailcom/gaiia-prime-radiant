from engine.kernel.world_state_manager import CenturionUnit
from engine.kernel.soft_state_layer import SoftState
from engine.modeller.outcome_modeller import OutcomeModeller
from engine.rules.rules_interface import RulesInterface

class MockRulesInterface:
    def query_rule(self, query: str, simulation_id: str = "default", turn_id: str = "0"):
        return {
            "text": "Ranged combat resolution: roll 2d10 vs base target 11.",
            "path_taken": "MOCK",
            "confidence": 1.0,
            "source_chunks": []
        }

def test_resolve_combat_basic():
    ri = MockRulesInterface()
    # Cast/wrap mock for typing if needed
    om = OutcomeModeller(ri) # type: ignore
    
    attacker = CenturionUnit(
        id="a1", name="Attacker", faction="cw", position=[0, 0],
        soft_state=SoftState(morale=1.0, suppression=0.0)
    )
    defender = CenturionUnit(
        id="d1", name="Defender", faction="tog", position=[0, 1],
        soft_state=SoftState(morale=1.0, suppression=0.0)
    )

    res = om.resolve_combat(attacker, defender, terrain="plain", iterations=100)
    assert res["iterations"] == 100
    assert res["compliance_rate"] > 0.8  # Attacker has high morale, compliance rate should be high
    assert "average_damage" in res
    assert "average_suppression_applied" in res
    assert res["citation"] == "MOCK"

def test_resolve_combat_low_compliance():
    ri = MockRulesInterface()
    om = OutcomeModeller(ri) # type: ignore
    
    # Morale is low but not routing (say, 0.3)
    attacker = CenturionUnit(
        id="a1", name="Attacker", faction="cw", position=[0, 0],
        soft_state=SoftState(morale=0.3, suppression=0.0)
    )
    defender = CenturionUnit(
        id="d1", name="Defender", faction="tog", position=[0, 1],
        soft_state=SoftState(morale=1.0, suppression=0.0)
    )

    res = om.resolve_combat(attacker, defender, terrain="plain", iterations=100)
    # Since morale is 0.3, compliance_prob = 0.9 * 0.3 * 1.0 * 1.0 = 0.27
    # Compliance rate should be much lower than the previous run
    assert res["compliance_rate"] < 0.5

def test_resolve_combat_routing():
    ri = MockRulesInterface()
    om = OutcomeModeller(ri) # type: ignore
    
    # Morale is routing (< 0.2)
    attacker = CenturionUnit(
        id="a1", name="Attacker", faction="cw", position=[0, 0],
        soft_state=SoftState(morale=0.15, suppression=0.0)
    )
    defender = CenturionUnit(
        id="d1", name="Defender", faction="tog", position=[0, 1],
        soft_state=SoftState(morale=1.0, suppression=0.0)
    )

    res = om.resolve_combat(attacker, defender, terrain="plain", iterations=100)
    # Compliance rate should be exactly 0
    assert res["compliance_rate"] == 0.0
