from dataclasses import dataclass
import json
import time
from urllib import request
from typing import Any, Generic, TypeVar, TypeAlias, Literal, overload

#
# Node Input / Output Types
#


_Any: TypeAlias = Any


class ComfyTypes:
    INT: TypeAlias = int
    """integer"""

    FLOAT: TypeAlias = float
    """real number"""

    STRING: TypeAlias = str
    """string"""

    BOOLEAN: TypeAlias = bool
    """boolean"""

    Any: TypeAlias = _Any

    SELECTION = Literal

    ### markmarkmark ###


#
# Node Input / Output
#


_T = TypeVar("_T")


@dataclass(frozen=True)
class ComfyInput(Generic[_T]):
    node: "_Node"
    """node instance"""

    index: int
    """index of this input"""

    name: str
    """name of this input"""

    type: _T
    """type of this input"""

    value: Any


@dataclass(frozen=True)
class ComfyOutput(Generic[_T]):
    node: "_Node"
    """node instance"""

    index: int
    """index of this output"""

    name: str | None

    type: _T
    """type of this output"""

    def __sub__(self, other: ComfyInput[_T]) -> "Link":
        # self - other == workflow.link(self, other)
        wf = self.node._context
        if wf is None:
            raise RuntimeError("call under workflow context")
        if not (wf is other.node._context):
            raise RuntimeError("not same workflow context")

        # add nodes and create link self -> other
        if not any(self.node is n.node for n in wf._nodes):
            wf.add(self.node)
        if not any(other.node is n.node for n in wf._nodes):
            wf.add(other.node)

        return wf.link(self, other)


#
# Node Base Class
#


class _Node:
    _context: "Workflow | None" = None

    def __init__(self, name: str):
        self.name = name
        self._inputs: list[ComfyInput] = []
        self._outputs: list[ComfyOutput] = []

    def _add_input(self, inp: ComfyInput):
        if self._context is None:
            self._inputs.append(inp)
        else:
            self._context._add_input(self, inp)
        return inp

    def _add_output(self, out: ComfyOutput):
        if self._context is None:
            self._outputs.append(out)
        else:
            self._context._add_output(self, out)
        return out

    @property
    def input_length(self) -> int:
        return len(self._inputs)

    @property
    def output_length(self) -> int:
        return len(self._outputs)

    def input(self, index: int | str) -> ComfyInput[Any]:
        if isinstance(index, int):
            return self._inputs[index]
        for inp in self._inputs:
            if inp.name == index:
                return inp
        raise IndexError(f"invalid index {index} for input")

    def output(self, index: int | str) -> ComfyOutput[Any]:
        if isinstance(index, int):
            return self._outputs[index]
        for out in self._outputs:
            if out.name is not None and out.name == index:
                return out
        for out in self._outputs:
            if out.type.__name__ == index:
                return out
        raise IndexError(f"invalid index {index} for output")

    __truediv__ = output  # self / n == self.output(n)
    __rtruediv__ = input  # n / self == self.input(n)


#
# Workflow
#


@dataclass(frozen=True)
class Node:
    node: _Node
    id: int


@dataclass(frozen=True)
class Link:
    src: int
    src_index: int
    dst: int
    dst_index: int


class Workflow:
    def __init__(self):
        self._nodes: list[Node] = []
        self._links: list[Link] = []
        self._id = 0

    def add(self, node: _Node) -> _Node:
        self._nodes.append(Node(node, self._id))
        self._id += 1
        return node

    def node_id(self, node: _Node) -> int:
        for n in self._nodes:
            if n.node is node:
                return n.id
        raise ValueError(f"Node {node} not found in workflow")

    def find_link_with_dst(self, dst_node: Node, dst_index: int) -> Link:
        for link in self._links:
            if link.dst == dst_node.id and link.dst_index == dst_index:
                return link
        n = dst_node.node
        v = n.input(dst_index)
        raise ValueError(f"link not found for {n.name}:{dst_index}:{v.name} ({v.type.__name__})")

    def find_link_with_src(self, src_node: Node, src_index: int) -> Link:
        for link in self._links:
            if link.src == src_node.id and link.src_index == src_index:
                return link
        n = src_node.node
        v = n.output(src_index)
        raise ValueError(f"link not found for {n.name}:{src_index} ({v.type.__name__})")

    def link(self, source: ComfyOutput[_T], drain: ComfyInput[_T]) -> Link:
        if source.type != drain.type:
            raise ValueError(f"type mismatch: {source.type} != {drain.type}")

        src_node = source.node
        dst_node = drain.node

        src_id = self.node_id(src_node)
        dst_id = self.node_id(dst_node)

        # update input

        dst_node._inputs[drain.index] = ComfyInput(
            dst_node,
            drain.index,
            drain.name,
            drain.type,
            _LINKED,
        )

        link = Link(src_id, source.index, dst_id, drain.index)
        self._links.append(link)

        return link

    def check(self):
        errors = []
        # check inputs
        for n in self._nodes:
            for i in range(n.node.input_length):
                inp = n.node.input(i)
                val = inp.value
                if val is _WILL_BE_LINKED:
                    errors.append(f"{n.node.name}:{i}:{inp.name} ({inp.type.__name__}) is not linked")
        # check links
        for l in self._links:
            pass

        if len(errors) != 0:
            msg = "\n  ".join(errors)
            raise ValueError(f"Workflow check failed: \n  {msg}")

    def to_dict(self) -> dict:
        result = {}

        for n in self._nodes:
            node = n.node
            id = n.id

            ndict = {
                "class_type": node.name,
                "_meta": {"title": node.name},
                "inputs": {},
            }

            for i in range(node.input_length):
                inp = node.input(i)
                if inp.value is _LINKED:
                    link = self.find_link_with_dst(n, inp.index)
                    src, src_index = link.src, link.src_index
                    ndict["inputs"][inp.name] = [
                        str(src),
                        src_index,
                    ]
                elif inp.value is _NOT_GIVEN:
                    # omitted
                    continue
                else:
                    ndict["inputs"][inp.name] = inp.value

            result[str(id)] = ndict

        return result

    def call(
        self,
        url: str = "http://127.0.0.1:8188",
        timeout: float = 60.0,
    ):
        self.check()
        prompt_data = json.dumps({"prompt": self.to_dict()}, ensure_ascii=False)
        req = request.Request(f"{url}/prompt", data=prompt_data.encode("utf-8"))
        res = request.urlopen(req)
        data = json.loads(res.read())

        prompt_id = data["prompt_id"]

        t0 = time.time()
        while time.time() - t0 < timeout:
            with request.urlopen(f"{url}/history/{prompt_id}") as res:
                data: dict = json.loads(res.read()).get(prompt_id, {})
                if "status" not in data:
                    time.sleep(0.01)
                    continue
                completed = data["status"].get("completed", False)
                if not completed:
                    time.sleep(0.01)
                    continue
                return data

        raise TimeoutError(f"timeout {timeout} sec")

    async def acall(
        self,
        url: str = "http://127.0.0.1:8188",
        timeout: float = 60.0,
    ):
        self.check()
        data = json.dumps({"prompt": self.to_dict()}, ensure_ascii=False)

        import asyncio
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data.encode("utf-8")) as res:
                data = await res.json()

        prompt_id = data["prompt_id"]

        t0 = time.time()
        while time.time() - t0 < timeout:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/history/{prompt_id}") as res:
                    data = await res.json()
                    data = data.get(prompt_id, {})
                    if "status" not in data:
                        await asyncio.sleep(0.01)
                        continue
                    completed = data["status"].get("completed", False)
                    if not completed:
                        await asyncio.sleep(0.01)
                        continue
                    return data

        raise TimeoutError(f"timeout {timeout} sec")

    def __enter__(self):
        # hook _Node.(_add_input|_add_output)
        assert _Node._context is None, "already in workflow context"
        _Node._context = self
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        _Node._context = None
        self.check()

    def _add_input(self, this: _Node, inp: ComfyInput):
        # _Node._add_input から呼ばれる
        if not isinstance(inp.value, ComfyOutput):
            this._inputs.append(inp)
            return inp

        src = inp.value
        dst = ComfyInput(inp.node, inp.index, inp.name, inp.type, _WILL_BE_LINKED)
        this._inputs.append(inp)

        if not any(this is n.node for n in self._nodes):
            self.add(this)

        self.link(src, dst)
        return inp

    def _add_output(self, this: _Node, out: ComfyOutput):
        # _Node._add_output から呼ばれる
        this._outputs.append(out)
        if not any(this is n.node for n in self._nodes):
            self.add(this)
        return out


_WILL_BE_LINKED = object()
_NOT_GIVEN = object()
_LINKED = object()

# AUTOGENERATED STUBS
