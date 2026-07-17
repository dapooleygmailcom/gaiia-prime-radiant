from engine.planner.adversarial_planner import AdversarialPlanner
from engine.planner.doctrine_profiles import DoctrineProfileManager
from engine.modeller.outcome_modeller import OutcomeModeller
from engine.rules.rules_interface import RulesInterface
from engine.kernel.world_state_manager import CenturionUnit, CenturionWorldState

class DummyRulesInterface:
    def evaluate_compliance(self, rule_id: str, unit) -> float:
        return 1.0

class DummyModeller:
    def resolve_combat(self, attacker, defender, terrain, iterations):
        return {"hit_probability": 0.5, "average_damage": 2.0, "citation": "Dummy"}

def test_adversarial_planner_aggressive_bias():
    modeller = DummyModeller()
    doctrine_manager = DoctrineProfileManager()
    planner = AdversarialPlanner(modeller, doctrine_manager, faction="tog", doctrine="aggressive")
    
    world_state = CenturionWorldState(simulation_id="test")
    unit = CenturionUnit(id="tog1", name="TOG Tank", faction="tog", position=[0, 0])
    world_state.units["tog1"] = unit
    world_state.units["cw1"] = CenturionUnit(id="cw1", name="CW Tank", faction="commonwealth", position=[1, 1])
    
    # Plan actions
    actions = planner.plan_actions(unit, world_state)
    
    # The aggressive doctrine (fire=1.5, move=0.8) should make "fire" score much higher than default
    # DummyModeller gives score = 0.5 * 100 + 2.0 * 50 = 150 base score for fire
    # Move score base is 10.
    # With aggressive doctrine, fire = 150 * 1.5 = 225.
    
    fire_actions = [a for a in actions if a["action_type"] == "fire"]
    assert len(fire_actions) > 0
    assert fire_actions[0]["score"] == 225.0
