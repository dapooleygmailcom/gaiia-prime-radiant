from typing import List, Dict, Any
from engine.kernel.world_state_manager import CenturionUnit, CenturionWorldState
from engine.modeller.outcome_modeller import OutcomeModeller
from engine.planner.action_planner import ActionPlanner
from engine.planner.doctrine_profiles import DoctrineProfileManager

class AdversarialPlanner(ActionPlanner):
    """
    APβ Planner (Faction B - TOG / Adversarial Counter-Simulator).
    Uses a doctrine profile to bias action scoring.
    """
    def __init__(
        self,
        modeller: OutcomeModeller,
        doctrine_manager: DoctrineProfileManager,
        faction: str = "tog",
        doctrine: str = "aggressive"
    ):
        super().__init__(modeller)
        self.doctrine_manager = doctrine_manager
        self.faction = faction
        self.doctrine = doctrine

    def plan_actions(
        self,
        unit: CenturionUnit,
        world_state: CenturionWorldState,
        objective: str = "maximize_damage"
    ) -> List[Dict[str, Any]]:
        """
        Enumerates actions and applies doctrine biases.
        """
        # Call base class to get the generic actions and base scores
        actions = super().plan_actions(unit, world_state, objective)
        
        # Apply doctrine modifier to each action
        for action in actions:
            action_type = action.get("action_type")
            modifier = self.doctrine_manager.get_action_modifier(
                faction=self.faction,
                doctrine=self.doctrine,
                action_type=action_type
            )
            action["score"] = action["score"] * modifier

        # Re-sort descending by the modified score
        actions.sort(key=lambda x: x["score"], reverse=True)
        return actions
