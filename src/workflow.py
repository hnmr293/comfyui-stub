from dataclasses import dataclass
import json
from urllib import request
import time
from typing import TypeVar

from .stub_base import _Node, ComfyInput, ComfyOutput


_T = TypeVar("_T")


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


_LINKED = object()


class WorkflowBase:
    def __init__(self, nodes_module):
        self._nodes: list[Node] = []
        self._links: list[Link] = []
        self._id = 0
        self._WILL_BE_LINKED = nodes_module._WILL_BE_LINKED
        self._NOT_GIVEN = nodes_module._NOT_GIVEN

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
                if val is self._WILL_BE_LINKED:
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
                elif inp.value is self._NOT_GIVEN:
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


class Workflow(WorkflowBase):
    def __init__(self, nodes_module):
        super().__init__(nodes_module)
        self.__node_class: type[_Node] = nodes_module._Node
        self.__ComfyInput: type[ComfyInput] = nodes_module.ComfyInput
        self.__ComfyOutput: type[ComfyOutput] = nodes_module.ComfyOutput

    def __enter__(self):
        # _Node.(_add_input|_add_output) のフック
        self.__node_class._context = self

        # output(1) - input(2) でリンクを作れるようにする
        def sub(src: ComfyOutput, dst: ComfyInput):
            if not any(src.node is n.node for n in self._nodes):
                self.add(src.node)
            if not any(dst.node is n.node for n in self._nodes):
                self.add(dst.node)
            return self.link(src, dst)

        self.__ComfyOutput.__sub__ = sub  # type: ignore

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.__node_class._context = None
        del self.__ComfyOutput.__sub__
        self.check()

    def _add_input(self, this: _Node, inp: ComfyInput):
        # _Node._add_input から呼ばれる
        if not isinstance(inp.value, self.__ComfyOutput):
            this._inputs.append(inp)
            return inp

        src = inp.value
        dst = self.__ComfyInput(inp.node, inp.index, inp.name, inp.type, self._WILL_BE_LINKED)
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
