from unittest.mock import patch
from engine.rules.rule_compiler import RuleCompiler

def test_compile_rule_mocked():
    compiler = RuleCompiler(model_name="test_model")
    
    mocked_code = """
def evaluate_rule(context: dict) -> dict:
    roll = context.get('roll', 0)
    if roll >= 8:
        return {'damage': 5, 'suppression': 0.5}
    return {'damage': 0, 'suppression': 0.0}
"""
    
    # Mock Ollama generate
    with patch('ollama.generate') as mock_generate:
        mock_generate.return_value = {"response": mocked_code}
        
        compiled_str = compiler.compile_rule("Vulcan III attack", "If you roll 8 or higher, deal 5 damage and 0.5 suppression.")
        
        assert "def evaluate_rule(context: dict)" in compiled_str
        assert "return {'damage': 5, 'suppression': 0.5}" in compiled_str
        
        # Test execution
        res1 = compiler.execute_compiled_rule(compiled_str, {"roll": 9})
        assert res1["damage"] == 5
        assert res1["suppression"] == 0.5
        
        res2 = compiler.execute_compiled_rule(compiled_str, {"roll": 4})
        assert res2["damage"] == 0
        assert res2["suppression"] == 0.0
