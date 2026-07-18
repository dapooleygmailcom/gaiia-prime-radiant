import json
from typing import Any, Callable, Dict
import ollama

class RuleCompiler:
    """
    Compiles raw rule text into deterministic Python functions using an LLM.
    The resulting Python code is returned as a string, which can be safely exec'd
    by the engine in a controlled environment.
    """
    def __init__(self, model_name: str = "qwen2.5-coder:7b"):
        self.model_name = model_name

    def compile_rule(self, rule_query: str, rule_text: str) -> str:
        """
        Takes a rule query and the raw rule text retrieved from RAG-Doll.
        Asks the LLM to write a Python function `evaluate_rule(context: dict) -> dict`
        that implements the logic.
        """
        prompt = f"""
You are the Prime Radiant rule compiler. 
Your job is to read a raw game rule and compile it into a deterministic Python function.

RULE QUERY: {rule_query}
RAW RULE TEXT: 
{rule_text}

Write a python function named `evaluate_rule(context: dict) -> dict` that implements this rule.
The `context` dict will contain variables like 'unit', 'target', 'roll', etc., depending on the rule.
The function must return a dictionary of results (e.g., {{'damage': 3, 'suppression': 0.5}}).

Return ONLY valid Python code. Do not include markdown formatting or explanations.
"""
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={"temperature": 0.0}
            )
            code_str = response.get("response", "")
            
            # Clean up markdown if the LLM still included it
            if code_str.startswith("```python"):
                code_str = code_str[len("```python"):].strip()
            if code_str.endswith("```"):
                code_str = code_str[:-3].strip()
                
            return code_str
            
        except Exception as e:
            return f"def evaluate_rule(context: dict) -> dict:\n    raise Exception('Rule Compilation Failed: {e}')"

    def execute_compiled_rule(self, code_str: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the compiled rule safely.
        """
        # Create an isolated namespace
        local_env = {}
        try:
            exec(code_str, {}, local_env)
            if "evaluate_rule" in local_env:
                return local_env["evaluate_rule"](context)
            else:
                raise ValueError("Compiled code did not define 'evaluate_rule'.")
        except Exception as e:
            raise Exception(f"Failed to execute rule: {e}\n\nCode:\n{code_str}")
