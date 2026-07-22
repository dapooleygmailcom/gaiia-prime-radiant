import re
import traceback
import random
import ollama
from typing import Dict, Any, Optional

from engine.rules.rules_interface import RulesInterface
from engine.kernel.world_state_manager import WorldStateManager
from engine.rules.rule_cache import RuleCache

class MasterArbiter:
    """
    The Master Arbiter is the LLM-driven core that generates deterministic Python 
    math and logic based on the Rules retrieved from the RAG-Doll.
    """
    def __init__(self, rules_interface: RulesInterface, dynamic_globals: Dict[str, Any], model_name="qwen2.5:14b"):
        self.rules = rules_interface
        self.dynamic_globals = dynamic_globals
        self.model_name = model_name
        self.cache = RuleCache()

    def extract_command(self, text: str):
        match = re.search(r'\[(GENERATE_ENGINE_RULE):\s*(.*?)\]', text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).upper(), match.group(2).strip()
        return None, None

    def extract_python_code(self, text: str):
        match = re.search(r'```python(.*?)```', text, re.DOTALL | re.IGNORECASE)
        if match:
            code = match.group(1).strip()
            # Remove any GENERATE_ENGINE_RULE commands mistakenly placed inside the python block
            code = re.sub(r'\[GENERATE_ENGINE_RULE:\s*.*?\]', '', code, flags=re.IGNORECASE).strip()
            return code
        return None

    def get_or_generate_mechanic(self, mechanic_name: str, situation_description: str, rfi_logger=None, simulation_id: str = "none"):
        """
        Retrieves compiled python from SQL cache, or prompts the LLM to generate it, 
        then injects it into dynamic_globals and returns the callable function.
        """
        # 1. Check Cache
        cached_code = self.cache.get_compiled(mechanic_name)
        if cached_code:
            print(f"[Master Arbiter] Loaded compiled mechanic '{mechanic_name}' from SQL cache.")
            try:
                exec(cached_code, self.dynamic_globals, self.dynamic_globals)
                return self.dynamic_globals.get(mechanic_name)
            except Exception as e:
                print(f"[Master Arbiter] Error executing cached code for {mechanic_name}: {e}")
        
        print(f"[Master Arbiter] Generating mechanic '{mechanic_name}' from rules...")
        # 2. Ask RAG for the rules
        rag_result = self.rules.query_rule(situation_description)
        rule_text = rag_result.get("text", "")
        
        # 3. Prompt LLM to generate the python function
        system_prompt = f"""You are the Master Arbiter for a high-fidelity simulation engine.
You must write a deterministic Python function named `{mechanic_name}` to resolve game rules based on the following reference material.
DO NOT use approximations. Use high-fidelity implementations.

REFERENCE RULE:
{rule_text}

SITUATION TO MODEL:
{situation_description}

Your task: Write the appropriate python function. 
You must wrap your code in a ```python ... ``` block.
You must issue the command [GENERATE_ENGINE_RULE: {mechanic_name}] at the end of your response.
"""
        messages = [{"role": "system", "content": system_prompt}]
        
        try:
            response = ollama.chat(model=self.model_name, messages=messages)
        except Exception:
            response = ollama.chat(model="llama3.1:8b", messages=messages)
            
        content = response["message"]["content"]
        
        code = self.extract_python_code(content)
        cmd_type, cmd_args = self.extract_command(content)
        
        if code:
            try:
                # Save to cache
                self.cache.set_compiled(mechanic_name, code)
                # Execute into globals
                exec(code, self.dynamic_globals, self.dynamic_globals)
                
                # Log the generated code to RFI
                if rfi_logger:
                    rfi_logger.log_uncertain_query(
                        query=situation_description,
                        retrieved_chunks=[rag_result],
                        interpretation=code,
                        confidence=0.5, # Always uncertain because LLM generated code
                        simulation_id=simulation_id,
                        turn_id="dynamic_gen"
                    )
                return self.dynamic_globals.get(mechanic_name)
            except Exception as e:
                print(f"Master Arbiter Error compiling code: {e}")
                print(traceback.format_exc())
                return None
        return None

    def answer_commander_query(self, query: str) -> str:
        """Acts as DM answering a player's query based on RAG rules."""
        rag_result = self.rules.query_rule(query)
        rule_text = rag_result.get("text", "")
        
        system_prompt = (
            "You are the Master Arbiter (Game Master) for Renegade Legion. "
            "Answer the commander's question concisely using only the provided rule text. "
            "If the rules do not say, use reasonable physics.\n"
            "ENGINE SPECIFIC DEFINITIONS:\n"
            "- Posture: This is the offensive/defensive mindset the side adopts (e.g., Aggressive, Defensive, Neutral). It is NOT the heading, facing, or orientation of the unit.\n"
            "- Hex Grid: Moving down the map (increasing Y) means moving towards bottom (Heading 4). Moving up (decreasing Y) means moving towards top (Heading 1)."
        )
        user_prompt = f"Commander asks: {query}\n\nRule Reference:\n{rule_text}"
        
        try:
            response = ollama.chat(model=self.model_name, messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ])
        except Exception:
            response = ollama.chat(model="llama3.1:8b", messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ])
            
        return response["message"]["content"]

    def orchestrate_game(self, engine: Any, objective: str, target_phase: str = None, turns: int = 1):
        """
        The main system-agnostic orchestrator loop.
        Queries RAG for the turn sequence and drives the simulation.
        If target_phase is provided, it will only execute that specific phase (useful for isolated tests).
        """
        print(f"[MASTER ARBITER] Orchestrating game loop. Objective: {objective}")
        
        # 1. Ask RAG for sequence of play
        seq_rule = self.rules.query_rule("What is the sequence of play for a game turn?")
        
        prompt = f"Based on this rule text:\n{seq_rule.get('text', '')}\nList the phases of a turn in chronological order. Output a comma-separated list of phase names ONLY. e.g. 'Initiative Phase, Movement Phase, Combat Phase'"
        try:
            response = ollama.chat(model=self.model_name, messages=[{"role": "system", "content": "You are the Master Arbiter."}, {"role": "user", "content": prompt}])
        except Exception:
            response = ollama.chat(model="llama3.1:8b", messages=[{"role": "system", "content": "You are the Master Arbiter."}, {"role": "user", "content": prompt}])
            
        # Fallback if LLM gives weird formatting
        content = response["message"]["content"].replace('\n', '')
        phases = [p.strip() for p in content.split(",") if p.strip()]
        if not phases:
            phases = ["Initiative Phase", "Movement Phase", "Combat Phase"]
            
        print(f"[MASTER ARBITER] Discovered phases from rules: {phases}")
        
        for turn in range(1, turns + 1):
            engine.wsm.get_state().turn = turn
            print(f"\n=================== TURN {turn} ===================")
            
            for phase in phases:
                if target_phase and target_phase not in phase:
                    continue # Skip phases we aren't testing right now
                    
                print(f"\n--- {phase.upper()} ---")
                # Simplified initiative: just let commonwealth go for the test
                active_faction = "commonwealth"
                
                self.run_phase_dialogue(engine, phase, active_faction, objective)

    def run_phase_dialogue(self, engine: Any, phase: str, active_faction: str, objective: str):
        """
        Executes a phase via dialogue between the Arbiter and the active Commander.
        """
        commander = engine.commanders.get(active_faction)
        if not commander:
            return
            
        state_desc = f"Turn {engine.wsm.get_state().turn}\n"
        for u in engine.wsm.get_state().units.values():
            max_thrust = u.entity_profile.get("attributes", {}).get("Maximum Thrust", 0) if hasattr(u, 'entity_profile') else 0
            state_desc += f"Unit {u.id} ({u.faction}): pos={u.position}, heading={u.heading}, velocity={u.velocity}, max_thrust={max_thrust}\n"
            
        arbiter_prompt = (
            f"The state is:\n{state_desc}\n"
            f"Simulation Objective: {objective}\n\n"
            f"It is your {phase}. Please ask me any questions about the rules, your capabilities, or terms you do not understand before deciding.\n"
            f"*IMPORTANT RULE: Hex facing needs to be set as clockwise from top, where top is 1, bottom is 4.*\n"
            f"When you are ready to act, issue your command in a structured format, e.g. [MOVE: Posture=Aggressive, Heading=<number>, EndVelocity=<number>, Path=1001,1002,1003]"
        )
        
        messages = [
            {"role": "system", "content": f"You are the {active_faction.upper()} commander. First ask the Game Master (Arbiter) questions about the rules, then decide your move. Use the Simulation Objective to guide your actions."},
            {"role": "user", "content": arbiter_prompt}
        ]
        
        print(f"[ARBITER -> {active_faction.upper()}]:\n{arbiter_prompt}\n")
        
        final_action = None
        for _ in range(3): # Allow up to 3 dialogue exchanges
            try:
                response = ollama.chat(model=commander.model_name, messages=messages)
            except Exception:
                response = ollama.chat(model="llama3.1:8b", messages=messages)
                
            content = response["message"]["content"]
            print(f"[{active_faction.upper()} COMMANDER]:\n{content}\n")
            messages.append(response["message"])
            
            # Check if an action was issued
            if "[" in content and "]" in content and ":" in content:
                final_action = content
                break
                
            # If not acting yet, assume it's a question for the Arbiter
            arbiter_answer = self.answer_commander_query(content)
            print(f"[MASTER ARBITER]:\n{arbiter_answer}\n")
            messages.append({"role": "user", "content": arbiter_answer})
            
        if final_action:
            print(f"[MASTER ARBITER]: Action received. Verifying against rules and applying physics via deterministic scripts...")
            if "Movement" in phase:
                resolve_func = self.get_or_generate_mechanic("resolve_movement", "Resolve a movement command string against a unit's physics.")
                if resolve_func:
                    unit = next((u for u in engine.wsm.get_state().units.values() if u.faction == active_faction), None)
                    if unit:
                        try:
                            resolve_func(unit, engine.wsm, final_action)
                        except Exception as e:
                            print(f"[MASTER ARBITER]: Error applying movement: {e}")
        else:
            print("[MASTER ARBITER]: Commander failed to issue a valid action command within dialogue limits.")
class SideCommander:
    """
    The Side Commander uses the WSM to evaluate state, then executes logic
    from the DynamicEngine to make decisions.
    """
    def __init__(self, faction_name: str, dynamic_globals: Dict[str, Any], model_name="qwen2.5:14b"):
        self.faction_name = faction_name
        self.dynamic_globals = dynamic_globals
        self.model_name = model_name

    def evaluate_and_act(self, wsm: WorldStateManager, phase: str, context: str = "") -> str:
        """
        Queries the state and returns the commander's orders based on the current phase.
        """
        print(f"\n--- Waking {self.faction_name.upper()} Side Commander ({phase} Phase) ---")
        state_desc = f"Turn {wsm.get_state().turn}\n"
        for u in wsm.get_state().units.values():
            max_thrust = u.entity_profile.get("attributes", {}).get("Maximum Thrust", 0) if hasattr(u, 'entity_profile') else 0
            state_desc += f"Unit {u.id} ({u.faction}): pos={u.position}, heading={u.heading}, velocity={u.velocity}, max_thrust={max_thrust}, destroyed={u.is_destroyed}\n"
            
        if phase == "Movement Phase" or "Movement" in phase:
            sys_prompt = f"You are the Side Commander for {self.faction_name.upper()}.\nCurrent State:\n{state_desc}\nYour goal is to get as close to the enemy as you can.\n"
            sys_prompt += "Decide your posture and movement. Postures: Neutral, Aggressive, Defensive.\n"
            sys_prompt += "You can ask the Game Master (Master Arbiter) for any rules you need before deciding.\n"
            sys_prompt += "Issue your command like this when ready:\n[MOVE: Posture=Aggressive, Heading=<number>, EndVelocity=<number>]\nExplain your reasoning first."
        elif phase == "Combat Phase" or "Combat" in phase:
            sys_prompt = f"You are the Side Commander for {self.faction_name.upper()}.\nCurrent State:\n{state_desc}\nYour goal is to destroy the enemy tank and survive.\n"
            sys_prompt += f"{context}\n" if context else ""
            sys_prompt += "Decide your fire barrage at enemy units. You may fire multiple weapons in your arc simultaneously.\n"
            sys_prompt += "Issue command exactly like this when ready:\n[FIRE: Target=hor1, TargetFacing=Front, Weapons=Laser;150mm;TVLG, Painting=True]\nExplain your logic."
        else:
            sys_prompt = f"You are the Side Commander for {self.faction_name.upper()}.\nCurrent phase is {phase}. Do nothing or ask the Arbiter what to do."

        messages = [{"role": "system", "content": sys_prompt}]
        try:
            response = ollama.chat(model=self.model_name, messages=messages)
        except Exception:
            response = ollama.chat(model="llama3.1:8b", messages=messages)
            
        content = response["message"]["content"]
        print(f"[{self.faction_name.upper()} Commander]:\n{content.strip()}\n")
        
        # Log to reasoning trace
        trace_path = "C:/Users/dapoo/.gemini/antigravity-ide/brain/68c2581d-4958-44bc-8dcc-ceb65471fe04/reasoning_trace.md"
        with open(trace_path, "a") as f:
            f.write(f"### {self.faction_name.upper()} Commander ({phase} Phase, Turn {wsm.get_state().turn})\n")
            f.write(f"{content.strip()}\n\n---\n")
            
        return content


class DynamicEngine:
    """
    The unified controller that houses the dynamic globals and orchestrates
    the Arbiter and Commanders.
    """
    def __init__(self, simulation_id: str):
        self.simulation_id = simulation_id
        self.rules = RulesInterface()
        self.wsm = WorldStateManager(simulation_id)
        
        # The shared namespace where Master Arbiter injects functions
        self.dynamic_globals: Dict[str, Any] = {}
        self.arbiter = MasterArbiter(self.rules, self.dynamic_globals)
        self.commanders: Dict[str, SideCommander] = {}
        
    def add_commander(self, faction: str):
        self.commanders[faction] = SideCommander(faction, self.dynamic_globals)

    def initialize_default_scenario(self):
        # Initialize basic Centurion grid map
        self.wsm.set_hex(1, 1, "woods")
        self.wsm.set_hex(1, 2, "plain")
        self.wsm.set_hex(2, 1, "rough")
        self.wsm.set_hex(2, 2, "plain")

        # Spawn friendly Commonwealth and adversarial TOG units
        try:
            cw_unit = self.wsm.create_unit_from_entity("cw_tank_1", "commonwealth", "rl_liberator_medium_grav_tank", self.rules)
            cw_unit.position = "0101"
        except Exception as e:
            print(f"Warning: Falling back to manual cw_unit creation. Error: {e}")
            from engine.kernel.world_state_manager import CenturionUnit
            from engine.kernel.soft_state_layer import SoftState
            cw_unit = CenturionUnit(
                id="cw_tank_1",
                name="Commonwealth Grav Tank Alpha",
                faction="commonwealth",
                position="0101",
                velocity=0,
                thrust_points=10,
                soft_state=SoftState(morale=1.0, suppression=0.0)
            )
            self.wsm.add_unit(cw_unit)

        try:
            tog_unit = self.wsm.create_unit_from_entity("tog_grav_1", "tog", "tog_horatius_medium_grav_tank", self.rules)
            tog_unit.position = "0202"
        except Exception as e:
            print(f"Warning: Falling back to manual tog_unit creation. Error: {e}")
            from engine.kernel.world_state_manager import CenturionUnit
            from engine.kernel.soft_state_layer import SoftState
            tog_unit = CenturionUnit(
                id="tog_grav_1",
                name="TOG Grav Tank Victrix",
                faction="tog",
                position="0202",
                velocity=0,
                thrust_points=10,
                soft_state=SoftState(morale=1.0, suppression=0.0)
            )
            self.wsm.add_unit(tog_unit)

        self.add_commander("commonwealth")
        self.add_commander("tog")
        self.wsm.take_snapshot()

    def recommend_actions(self, unit_id: str, objective: str) -> str:
        # Find unit
        unit = self.wsm.get_state().units.get(unit_id)
        if not unit:
            raise ValueError(f"Unit {unit_id} not found")
            
        commander = self.commanders.get(unit.faction)
        if not commander:
            raise ValueError(f"No commander for faction {unit.faction}")
            
        # We will assume Movement Phase for now in this simple API integration
        return commander.evaluate_and_act(self.wsm, "Movement Phase", context=f"Objective: {objective}")

    def advance_turn(self, unit_id: str, chosen_action: Dict[str, Any]) -> str:
        unit = self.wsm.get_state().units.get(unit_id)
        if not unit:
            raise ValueError(f"Unit {unit_id} not found")
            
        command_str = chosen_action.get("command", "")
        if not command_str:
            raise ValueError("No command string provided in chosen_action")
            
        if "MOVE" in command_str:
            resolve_func = self.arbiter.get_or_generate_mechanic("resolve_movement", "Resolve a movement command string against a unit's physics.")
            if resolve_func:
                resolve_func(unit, self.wsm, command_str)
                return "Movement resolved successfully."
            else:
                raise RuntimeError("Failed to generate or retrieve resolve_movement mechanic")
                
        return "Command not recognized or unsupported phase."

