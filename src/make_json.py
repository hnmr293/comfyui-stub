import os
import json

from .defn import NodeDefn, COMFYUI_TYPENAME_TO_JSON_TYPENAME


SCHEMA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "schemas",
)


def load_base_schema(major_version: int = 1, minor_version: int = 0) -> dict:
    """
    return ComfyUI Workflow schema

    allowed versions:
    - 0.4
    - 1.0 (default)
    """

    base_schema_path = os.path.join(
        SCHEMA_DIR,
        "workflow_v1.0.json",
    )

    if not os.path.exists(base_schema_path):
        raise ValueError(f"Unsupported version: {major_version}.{minor_version} (reading: {base_schema_path})")

    with open(base_schema_path, "r") as f:
        base_schema = json.load(f)

    return base_schema


def load_base_api_schema(major_version: int = None, minor_version: int = None) -> dict:
    """
    return ComfyUI API schema

    allowed versions:
    - (None, None) (default): unofficial (undocumented) version
    """

    if major_version is None and minor_version is None:
        base_schema_path = os.path.join(
            SCHEMA_DIR,
            "workflow_api_unofficial.json",
        )
    else:
        raise ValueError(f"Unsupported version: {major_version}.{minor_version}")

    if not os.path.exists(base_schema_path):
        raise ValueError(f"Unsupported version: {major_version}.{minor_version} (reading: {base_schema_path})")

    with open(base_schema_path, "r") as f:
        base_schema = json.load(f)

    return base_schema


def create_node_types_for_api(defns: list[NodeDefn]) -> dict:
    """
    returns custom node definitions such as:
    {
        "type": "object",
        "properties": {
            "class_type": {
                "type": "string",
                "const": "MyNode",
            },
            "_meta": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string"
                    }
                },
                "required": ["title"],
            },
            "inputs": {
                "type": "object",
                "properties": {
                    "param1": {"type": "integer"},
                    "param2": {"type": "number"},
                    "param3": {"type": "string"},
                },
                "required": ["param1", "param2", "param3"],
            },
        },
        "required": ["class_type", "_meta", "inputs"],
    }
    """

    result = {}

    for defn in defns:
        inputs = {}
        required = []
        for p in defn.input_types:
            name, typ, req = p.name, p.type, p.required
            desc = p.desc

            if isinstance(typ, (list, tuple)):
                # selection
                if len(typ) == 0:
                    # とりあえず ^^;
                    typ = [""]
                inputs[name] = {"enum": list(typ)}
            elif typ in COMFYUI_TYPENAME_TO_JSON_TYPENAME:
                # comfyui builtin type
                json_type = COMFYUI_TYPENAME_TO_JSON_TYPENAME[typ]
                inputs[name] = {"type": json_type}
                if json_type in ("integer", "number"):
                    if "min" in desc:
                        inputs[name]["minimum"] = desc["min"]
                    if "max" in desc:
                        inputs[name]["maximum"] = desc["max"]
                    # - step は json schema で表現できないので無視する
                    #   （min が 0 のときのみ multipleOf で表現できる）
                    # - round は json schema で表現できないので無視する
                    # - default は無視する
            else:
                # extension type
                # i beleave it must be linked with another node
                inputs[name] = {"$ref": "#/definitions/link"}

            if req:
                required.append(name)

        result[defn.name] = {
            "type": "object",
            "properties": {
                "class_type": {
                    "type": "string",
                    "const": defn.name,
                },
                "_meta": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                        },
                    },
                    "required": ["title"],
                },
                "inputs": {
                    "type": "object",
                    "properties": inputs,
                    "required": required,
                },
            },
            "required": ["class_type", "_meta", "inputs"],
        }

    return result


def create_schema_for_api(
    defns: list[NodeDefn],
    base_major_version: int = None,
    base_minor_version: int = None,
) -> dict:
    schema = load_base_api_schema(base_major_version, base_minor_version)
    json_defns: dict = schema.setdefault("definitions", {})

    node_types: list = json_defns.setdefault("nodeType", {}).setdefault("oneOf", [])
    # {
    #     "definitions": {
    #         "nodeType": {
    #             "oneOf": [
    #                 ...
    #             ]
    #         }
    #     }
    # }

    for name, defn in create_node_types_for_api(defns).items():
        node_types.append(defn)

    root: str = schema["$ref"].split("/")[-1]
    root_elem = json_defns[root]
    if "oneOf" not in root_elem:
        oneof = [root_elem]
    else:
        oneof = root_elem["oneOf"]

    oneof.append({"$ref": "#/definitions/nodeType"})
    json_defns[root]["oneOf"] = oneof

    return schema
