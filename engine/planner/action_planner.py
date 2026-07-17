from typing import List, Dict, Any
from engine.kernel.world_state_manager import CenturionUnit, CenturionWorldState
from engine.modeller.outcome_modeller import OutcomeModeller

class ActionPlanner:
    """
    APα Planner (Faction A - Commonwealth / Human-advised).
    Enumerates legal actions for a unit, runs outcome simulations to score them,
    and returns a ranked list of recommended actions.
    """
    def __init__(self, modeller: OutcomeModeller):
        self.modeller = modeller

    def plan_actions(
        self,
        unit: CenturionUnit,
        world_state: CenturionWorldState,
        objective: str = "maximize_damage"
    ) -> List[Dict[str, Any]]:
        """
        Enumerates legal actions for a unit, scores them, and returns ranked choices.
        """
        actions = []

        # Find enemy units (different faction)
        enemies = [
            u for u in world_state.units.values()
            if u.faction != unit.faction and not u.is_destroyed
        ]

        # Action Option 1: Fire at Enemies
        for enemy in enemies:
            # Query terrain of the target hex
            terrain = world_state.map_hexes.get(f"{enemy.position[0]},{enemy.position[1]}", "plain")
            
            # Estimate outcome via OutcomeModeller
            outcome = self.modeller.resolve_combat(unit, enemy, terrain, iterations=50)
            
            # Scoring logic
            score = outcome["hit_probability"] * 100 + outcome["average_damage"] * 50
            actions.append({
                "action_type": "fire",
                "target_unit_id": enemy.id,
                "description": f"Fire at {enemy.name} in {terrain}",
                "score": round(score, 2),
                "expected_outcome": outcome,
                "citation": outcome.get("citation", "RAG-Doll query")
            })

        # Action Option 2: Move / Maneuver (E.g. towards objective)
        # Move forward, sideways, etc.
        directions = [[0, 1], [1, 0], [-1, 0], [0, -1]]
        for i, d in enumerate(directions):
            new_pos = [unit.position[0] + d[0], unit.position[1] + d[1]]
            new_pos_str = f"{new_pos[0]},{new_pos[1]}"
            terrain = world_state.map_hexes.get(new_pos_str, "plain")
            
            # Simple scoring: prefer defensive terrain (woods, rough)
            score = 10.0
            if terrain == "woods":
                score = 30.0
            elif terrain == "rough":
                score = 20.0
                
            actions.append({
                "action_type": "move",
                "destination": new_pos,
                "description": f"Move unit to {new_pos_str} ({terrain})",
                "score": score,
                "expected_outcome": {
                    "average_damage": 0.0,
                    "causal_trace": f"Move to hex coordinate {new_pos_str} safely."
                },
                "citation": "Centurion Movement Rules Section 2.1"
            })

        # Sort actions descending by score
        actions.sort(key=lambda x: x["score"], reverse=True)
        return actions
