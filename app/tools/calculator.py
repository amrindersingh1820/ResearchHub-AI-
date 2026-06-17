import re
import math

def calculate(expression: str) -> str:
    """Safely evaluate basic mathematical expressions."""
    # Clean expression
    expression = re.sub(r'[^0-9+\-*/().\s]', '', expression)
    try:
        # Evaluate with a restricted scope
        allowed_names = {
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "sqrt": math.sqrt, "pi": math.pi, "e": math.e, "pow": pow
        }
        result = eval(expression, {"__builtins__": None}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression '{expression}': {e}"
