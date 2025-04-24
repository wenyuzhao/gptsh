from agentia.plugins import tool, Plugin
from typing import Annotated
from . import simple_banner


class CalculatorPlugin(Plugin):
    NAME = "calc"

    @tool(
        metadata={
            "banner": simple_banner("CALC", dim=lambda a: a.get("expression", ""))
        }
    )
    def evaluate(
        self,
        expression: Annotated[
            str, "The math expression to evaluate. Must be an valid python expression."
        ],
    ):
        """
        Execute a math expression and return the result. The expression must be an valid python expression that can be execuated by `eval()`.
        """

        result = eval(expression)
        return result
