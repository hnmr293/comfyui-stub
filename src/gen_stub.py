import os
import re
import json
from dataclasses import dataclass
import uuid
from typing import Iterator

from .defn import NodeDefn as NodeDefn
from . import stub_base


@dataclass(frozen=True)
class NodeDefn1(NodeDefn):
    id: str


def generate_stub(defns: list[NodeDefn]) -> str:
    """generate python source file"""

    defns = [NodeDefn1(**vars(defn), id=uuid.uuid4().hex) for defn in defns]

    stub_path = os.path.join(
        os.path.dirname(__file__),
        "stub_base.py",
    )
    with open(stub_path, "r") as f:
        stub = f.read()

    # 1. add types

    default_types = stub_base.ComfyTypes
    extra_types = {}
    type_decls = []

    for defn in defns:
        types = []
        for p in defn.input_types:
            name, typ, req = p.name, p.type, p.required
            types.append(typ)
        for p in defn.output_types:
            name, typ = p.name, p.type
            types.append(typ)

        for typ in types:
            if isinstance(typ, (list, tuple)):
                # selection
                continue

            assert isinstance(typ, str), (typ, defn)

            if typ == "*":
                # reroute
                continue

            if hasattr(default_types, typ):
                continue

            if typ in extra_types:
                continue

            extra_types[typ] = typ

            decl = f'{typ} = type("{typ}", (object,), {{}})'
            type_decls.append(decl)

    ### markmarkmark ###
    # ^ ここに追加する

    mark = re.compile(r"([ \t]*)### markmarkmark ###")
    m = mark.search(stub)
    assert m is not None, "mark not found"

    indent = m.group(1)

    type_decls_str = indent + f"\n{indent}".join(type_decls)

    stub = mark.sub(type_decls_str, stub)

    # 2. add node classes

    """
    class MyNode:
        @classmethod
        def INPUT_TYPES(s) -> dict:
            return {
                "required": {
                    "param1": ("INT",),
                    "param2": ("FLOAT", {"default": 0.5}),
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
    
    ^ こんなノードがあったとして
    v こう変換する
    
    class MyNode(_Node):
        def __init__(
            self,
            param1: ComfyTypes.INT = _WILL_BE_LINKED,
            param2: ComfyTypes.FLOAT = 0.5,
            param3: ComfyTypes.STRING | None = _NOT_GIVEN,
        ):
            super().__init__("MyNode")
            self._add_input(ComfyInput(self, 0, "param1", ComfyTypes.INT, param1))
            self._add_input(ComfyInput(self, 1, "param2", ComfyTypes.FLOAT, param2))
            self._add_input(ComfyInput(self, 2, "param3", ComfyTypes.STRING, param3))
            self._add_output(ComfyOutput(self, 0, None, ComfyTypes.LATENT))
        @property
        def input_length(self) -> Literal[3]: return 3
        @property
        def output_length(self) -> Literal[1]: return 1
        @overload
        def input(self, index: Literal[0, "param1"]) -> ComfyInput[ComfyTypes.INT]: ...
        @overload
        def input(self, index: Literal[1, "param2"]) -> ComfyInput[ComfyTypes.FLOAT]: ...
        @overload
        def input(self, index: Literal[2, "param3"]) -> ComfyInput[ComfyTypes.STRING]: ...
        def input(self, index: int | str) -> ComfyInput[Any]: return super().input(index)
        @overload
        def output(self, index: Literal[0, "LATENT"]) -> ComfyOutput[ComfyTypes.LATENT]: ...
        def output(self, index: int | str) -> ComfyOutput[Any]: return super().output(index)
        
    コンストラクタには静的な入力値を渡す
    動的な入力値は触らない（内部で _WILL_BE_LINKED もしくは _NOT_GIVEN（オプショナル引数の場合）を渡す）
    check 時に _WILL_BE_LINKED が残っていたらエラーとする
    """

    node_classes = []
    for defn in defns:
        node_class = _create_class_def(defn)
        node_classes.append(node_class)

    namespace = _create_namespace_def(defns)

    fmt = "# fmt: off"

    return fmt + "\n\n" + stub + "\n\n" + "\n\n\n".join(node_classes) + "\n\n" + namespace


def _create_class_def(defn: NodeDefn1) -> str:
    header = f"class {defn.class_name}_{defn.id}(_Node):"

    ctor_params_list = ["self"]
    ctor_inputs_list = []
    ctor_outputs_list = []
    methods_list = []

    method = f"""
    @property
    def input_length(self) -> Literal[{len(defn.input_types)}]: return {len(defn.input_types)}
    """.rstrip()
    methods_list.append(method)

    method = f"""
    @property
    def output_length(self) -> Literal[{len(defn.output_types)}]: return {len(defn.output_types)}
    """.rstrip()
    methods_list.append(method)

    non_alnum = re.compile(r"[^a-zA-Z0-9_]")

    for i, p in enumerate(defn.input_types):
        name, typ, req, desc = p.name, p.type, p.required, p.desc
        name = non_alnum.sub("_", name)

        if isinstance(typ, (list, tuple)):
            # selection
            if len(typ) == 0:
                ty = "Any"
            else:
                xs = [(json.dumps(t) if isinstance(t, str) else str(t)) for t in typ]
                literals = ", ".join(xs)
                ty = f"ComfyTypes.SELECTION[{literals}]"
        else:
            if typ == "*":
                typ = "Any"
            ty = f"ComfyTypes.{typ}"

        # param1: ComfyTypes.INT = _WILL_BE_LINKED,
        ty1 = ty
        if req:
            if "default" in desc:
                default = desc["default"]
                if isinstance(default, str):
                    default = json.dumps(default)
            else:
                default = "_WILL_BE_LINKED"
        else:
            ty1 = f"{ty} | None"
            if "default" in desc:
                default = desc["default"]
                if isinstance(default, str):
                    default = json.dumps(default)
            else:
                default = "_NOT_GIVEN"
        ctor_params_list.append(f"{name}: {ty1} = {default}")

        # self._inputs.append(ComfyInput(self, 0, "param1", ComfyTypes.INT, param1))
        ctor_inputs_list.append(f"self._add_input(ComfyInput(self, {i}, {json.dumps(name)}, {ty}, {name}))")

        # @overload
        # def input(self, index: Literal[0, "param1"]) -> ComfyInput[ComfyTypes.INT]: ...
        method = f"""
    @overload
    def input(self, index: Literal[{i}, {json.dumps(name)}]) -> ComfyInput[{ty}]: ...
        """.rstrip()
        methods_list.append(method)

    method = f"""
    def input(self, index: int | str) -> ComfyInput[Any]: return super().input(index)
        """.rstrip()
    methods_list.append(method)

    consumed_output_typenames = set()
    for i, p in enumerate(defn.output_types):
        name, typ = p.name, p.type

        allowed_typename = None
        if isinstance(typ, (list, tuple)):
            # selection
            if len(typ) == 0:
                ty = "Any"
            else:
                xs = [(json.dumps(t) if isinstance(t, str) else str(t)) for t in typ]
                literals = ", ".join(xs)
                ty = f"ComfyTypes.SELECTION[{literals}]"
        else:
            if typ == "*":
                typ = "Any"
            else:
                allowed_typename = typ
            ty = f"ComfyTypes.{typ}"

        # self._outputs.append(ComfyOutput(self, 0, None, ComfyTypes.LATENT))
        out_name = json.dumps(name) if name is not None else "None"
        ctor_outputs_list.append(f"self._add_output(ComfyOutput(self, {i}, {out_name}, {ty}))")

        # @overload
        # def output(self, index: Literal[0, "LATENT"]) -> ComfyOutput[ComfyTypes.LATENT]: ...
        allowed_values = [str(i)]
        if name is not None:
            allowed_values.append(json.dumps(name))
        if allowed_typename is not None and allowed_typename not in consumed_output_typenames:
            allowed_values.append(json.dumps(allowed_typename))
            consumed_output_typenames.add(allowed_typename)
        method = f"""
    @overload
    def output(self, index: Literal[{", ".join(allowed_values)}]) -> ComfyOutput[{ty}]: ...
        """.rstrip()
        methods_list.append(method)

    method = f"""
    def output(self, index: int | str) -> ComfyOutput[Any]: return super().output(index)
        """.rstrip()
    methods_list.append(method)

    ctor_params = ",\n        ".join(ctor_params_list)
    ctor_inputs = "\n        ".join(ctor_inputs_list)
    ctor_outputs = "\n        ".join(ctor_outputs_list)

    ctor = f"""
    def __init__(
        {ctor_params},
    ):
        super().__init__({json.dumps(defn.name)})
        {ctor_inputs}
        {ctor_outputs}
    """.rstrip()

    methods = "".join(methods_list)  # @overload の前に改行が入っている

    class_def = header + ctor + methods
    return class_def


def _create_namespace_def(defns: list[NodeDefn1]) -> str:
    namespace = {}

    non_alnum = re.compile(r"[^a-zA-Z0-9_]")

    for defn in defns:
        cats = defn.category
        ns = namespace
        for c in cats:
            c = non_alnum.sub("", c)
            if len(c) == 0:
                # どうしよう？
                print(f"non-ascii category: {cats}")
                print("skipping...")
                continue
            if c[0].isdigit():
                # 先頭が数字はダメ
                c = "_" + c
            if c not in ns:
                ns[c] = {}
            ns = ns[c]

        # assert defn.class_name not in ns, (defn, ns)
        # エイリアスで同じノードの実体が別の名前で登録されていることがある
        # そこで name で管理する
        # ただし識別子として ill-formed である可能性があるので修正する

        name = defn.name
        name = non_alnum.sub("_", name)

        assert name not in ns, (defn, ns)
        ns[name] = defn

    def ns_to_s(ns: dict, level: int = 0) -> Iterator[str]:
        indent = " " * 4 * level
        for name, defn_or_ns in ns.items():
            if isinstance(defn_or_ns, dict):
                # ns
                yield f"{indent}class {name}:"
                yield from ns_to_s(defn_or_ns, level + 1)
            else:
                # defn
                assert isinstance(defn_or_ns, NodeDefn1)
                yield f"{indent}{name} = {defn_or_ns.class_name}_{defn_or_ns.id}"

    return "\n".join(ns_to_s(namespace))
