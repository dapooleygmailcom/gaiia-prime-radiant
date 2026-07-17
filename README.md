# Gaiia Prime Radiant — Simulation Engine Foundation MVP

Gaiia Prime Radiant is a rule-governed simulation engine designed to simulate wargame rules and business policy systems by querying Gaiia RAG-Doll.

## Components
- **World State Manager (WSM)**: Manages in-memory hierarchical state models.
- **Soft State Layer**: Updates and maintains unit variables such as morale and suppression.
- **Rules Interface**: Implements three-path query routing.
- **Compliance Layer**: Modulates unit action compliance probabilities.
- **Rule Feedback Interface**: Logs uncertain rules for refinement.
- **Outcome Modeller**: Monte Carlo resolution of actions based on governing rules.
- **Action Planner**: APα computes optimal legal actions for friendly forces.
