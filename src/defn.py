"""
node definition
"""

from dataclasses import dataclass
from abc import ABC

# ComfyUI imports
from nodes import NODE_CLASS_MAPPINGS


COMFYUI_TYPENAME_TO_JSON_TYPENAME = {
    "INT": "integer",
    "FLOAT": "number",
    "STRING": "string",
    "BOOLEAN": "boolean",
}


@dataclass(frozen=True)
class NodeParam:
    name: str
    type: str | list
    required: bool
    desc: dict


@dataclass(frozen=True)
class NodeOutput:
    name: str | None
    type: str


@dataclass(frozen=True)
class NodeDefn:
    name: str
    """node name"""

    class_name: str

    input_types: list[NodeParam]
    """input names and types
    
    if type is list, it means that this input is a selection.
    """

    output_types: list[NodeOutput]
    """output names and types"""

    category: list[str]


class _NodeType(ABC):
    @classmethod
    def INPUT_TYPES(cls) -> dict: ...

    FUNCTION: str

    RETURN_TYPES: tuple[str, ...]

    RETURN_NAMES: tuple[str, ...]  # 存在しないかも


def _get_input_params(klass: type[_NodeType]) -> list[NodeParam]:
    input_types = klass.INPUT_TYPES()
    input_types_required: dict = input_types.get("required", {})
    input_types_optional: dict = input_types.get("optional", {})

    result = []

    def get_param(key, value, required):
        assert isinstance(key, str), (key, value, required, klass)
        assert isinstance(value, (tuple, list)), (key, value, required, klass)

        if isinstance(value, list):
            # LoadLatent
            assert len(value) == 1, (key, value, klass)
            assert isinstance(value[0], list), (key, value, klass)
            param = NodeParam(key, value[0], required, {})
            return param

        assert len(value) in (1, 2)

        if len(value) == 1:
            typ = value[0]
            desc = {}
        else:
            typ, desc = value
            assert isinstance(desc, dict)

        assert isinstance(typ, (str, list, tuple)), (typ, value, klass)

        if isinstance(typ, tuple):
            typ = list(typ)

        param = NodeParam(key, typ, required, desc)
        return param

    for key, value in input_types_required.items():
        param = get_param(key, value, True)
        result.append(param)

    for key, value in input_types_optional.items():
        param = get_param(key, value, False)
        result.append(param)

    return result


def _get_outputs(klass: type[_NodeType]) -> list[NodeOutput]:
    return_types = klass.RETURN_TYPES
    return_names = getattr(klass, "RETURN_NAMES", None)

    assert return_names is None or len(return_names) == len(return_types)

    result = []
    for i, typ in enumerate(return_types):
        if return_names is not None:
            name = return_names[i]
        else:
            name = None
        result.append(NodeOutput(name, typ))

    return result


"""
class Node:
    @classmethod
    def INPUT_TYPES(s) -> dict:
        return {
            "required": {
                "param1": ("INT",),
                "param2": ("FLOAT",),
            },
            "optional": {
                "param3": ("STRING", {"desc": "desc"}),
            },
        }
    FUNCTION = "function_name"
    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("name1",)
    
    def function_name(self, param1, param2, param3=None):
        ...
"""


def _create_defn(name: str, klass: type[_NodeType]) -> NodeDefn:
    input_params = _get_input_params(klass)
    outputs = _get_outputs(klass)
    category = getattr(klass, "CATEGORY", "").split("/")

    return NodeDefn(
        name=name,
        class_name=klass.__name__,
        input_types=input_params,
        output_types=outputs,
        category=category,
    )


def collect_defns() -> dict[str, NodeDefn]:
    result = {}
    for name, klass in NODE_CLASS_MAPPINGS.items():
        defn = _create_defn(name, klass)
        result[name] = defn
    return result
