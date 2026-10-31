"""
Example tool registration (not loaded: the template is not in SECTIONS).

    from pydantic import BaseModel
    from engtoolkit.core.registry import Input, register_tool
    from .models.example import ExampleResult, example_calculation

    class ExampleInputs(BaseModel):
        width: float = Input(1.0, "m", "Width", gt=0)
        height: float = Input(2.0, "m", "Height", gt=0)

    @register_tool("<discipline>.example", "Example", ExampleInputs,
                   reference="Cite the textbook/standard the validation test checks against")
    def example_tool(inp: ExampleInputs) -> ExampleResult:
        return example_calculation(inp.width, inp.height)
"""
