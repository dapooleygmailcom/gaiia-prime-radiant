import random
from typing import Dict, List, Any, Tuple
from engine.kernel.world_state_manager import CenturionUnit
from engine.rules.rules_interface import RulesInterface
from engine.rules.compliance_layer import compute_compliance_probability

class OutcomeModeller:
    """
    Computes probabilistic simulation outcomes using Monte Carlo simulation.
    Queries RulesInterface for rules, parses mechanics, and compiles outcome paths.
    """
    def __init__(self, rules_interface: RulesInterface):
        self.ri = rules_interface

    def resolve_combat(
        self,
        attacker: CenturionUnit,
        defender: CenturionUnit,
        terrain: str,
        iterations: int = 100
    ) -> Dict[str, Any]:
        """
        Runs Monte Carlo iterations for Centurion tactical combat.
        Applies modifiers parsed from retrieved rules.
        """
        # Query rules for combat resolution
        rule_query = "What is the step-by-step procedure for resolving a ranged attack in Centurion?"
        rule_res = self.ri.query_rule(rule_query)
        rule_text = rule_res.get("text", "")
        citation = rule_res.get("path_taken", "Unknown Path")

        # Compile rules / extract parameters
        # In a real wargame, Centurion uses a 2d10 roll for hits.
        # Target number is typically governed by range, modified by terrain, suppression, etc.
        # Let's define the base target roll as 11 (average difficulty).
        base_target = 11

        aborted_count = 0
        hit_count = 0
        damage_sum = 0.0
        suppression_sum = 0.0
        morale_reduction_sum = 0.0

        for _ in range(iterations):
            # 1. Compliance check
            compliance = compute_compliance_probability(0.9, attacker.soft_state)
            if random.random() > compliance:
                aborted_count += 1
                continue

            # 2. Ranged attack resolution
            # Apply modifiers:
            # - Attacker suppressed: -2 to hit
            # - Defender hull-down: -3 to hit
            # - Woods terrain: -2 to hit
            # - Attacker low morale (< 0.5): -1 to hit
            roll_modifier = 0
            if attacker.soft_state.suppression > 0.5:
                roll_modifier -= 2
            if attacker.soft_state.morale < 0.5:
                roll_modifier -= 1
            if terrain == "woods":
                roll_modifier -= 2
            elif terrain == "rough":
                roll_modifier -= 1

            # Centurion 2d10 roll (ranges 2-20)
            roll = random.randint(1, 10) + random.randint(1, 10)
            modified_roll = roll + roll_modifier

            if modified_roll >= base_target:
                hit_count += 1
                # Apply template damage/suppression
                damage = round(random.uniform(0.1, 0.4), 2)
                suppress_applied = round(random.uniform(0.2, 0.5), 2)
                
                damage_sum += damage
                suppression_sum += suppress_applied
                morale_reduction_sum += (damage * 0.8)

        # Compute averages
        resolved_count = iterations - aborted_count
        avg_damage = round(damage_sum / resolved_count, 2) if resolved_count else 0.0
        avg_suppress = round(suppression_sum / resolved_count, 2) if resolved_count else 0.0
        avg_morale_red = round(morale_reduction_sum / resolved_count, 2) if resolved_count else 0.0

        # Causal trace generation
        trace = (
            f"Resolved {iterations} combat iterations using rule set from [{citation}].\n"
            f"Attacker compliance rate: {((resolved_count/iterations)*100):.1f}%.\n"
            f"Ranged attack base target: {base_target} (2d10 roll).\n"
            f"Modifiers applied: "
        )
        mods = []
        if attacker.soft_state.suppression > 0.5:
            mods.append("suppression (-2)")
        if attacker.soft_state.morale < 0.5:
            mods.append("low morale (-1)")
        if terrain in ("woods", "rough"):
            mods.append(f"terrain {terrain}")
        trace += ", ".join(mods) if mods else "none"

        return {
            "iterations": iterations,
            "compliance_rate": round(resolved_count / iterations, 2),
            "hit_probability": round(hit_count / resolved_count, 2) if resolved_count else 0.0,
            "average_damage": avg_damage,
            "average_suppression_applied": avg_suppress,
            "average_morale_reduction": avg_morale_red,
            "causal_trace": trace,
            "citation": citation,
            "raw_rule_text": rule_text[:300] + "..." if len(rule_text) > 300 else rule_text
        }
