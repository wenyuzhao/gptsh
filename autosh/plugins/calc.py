from agentia.plugins import tool, Plugin
from typing import Annotated
from . import banner


class CalculatorPlugin(Plugin):
    NAME = "calc"

    @tool
    def evaluate(
        self,
        expression: Annotated[
            str, "The math expression to evaluate. Must be an valid python expression."
        ],
    ):
        """
        Execute a math expression and return the result. The expression must be an valid python expression that can be execuated by `eval()`.
        """
        banner("CALC", expression)

        result = eval(expression)
        return result
