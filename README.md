# ComfyUI-Stub

[日本語 ver.](./README_ja.md)

Generates stub files for manipulating ComfyUI node lists and JSON Schema describing the inputs and outputs of each node.

The following APIs are added:

- `{ComfyUI URL}/node-api-stub`
- `{ComfyUI URL}/node-api-schema`

For example, you can retrieve and save stub files as follows:

```python
import requests
res = requests.get('http://127.0.0.1:8188/node-api-stub')
with open('nodes.py', 'w') as io:
    io.write(res.text)
```

# API

## `/node-api-stub`

Generates a stub file for Python.

The generated file has no dependencies on external files or libraries and can be imported and used on its own.

### Stub File Structure

The generated file has the following structure.

All inputs and outputs of each node are fully typed.

```python
class ComfyTypes:
    """A class (namespace) that collects types used in ComfyUI"""
    INT: TypeAlias = int
    FLOAT: TypeAlias = float
    ...

    MODEL = type("MODEL", (object,), {})
    CONDITIONING = type("CONDITIONING", (object,), {})
    ...

@dataclass(frozen=True)
class ComfyInput(Generic[_T]):
    """A class representing an input to a node"""
    ...

@dataclass(frozen=True)
class ComfyOutput(Generic[_T]):
    """A class representing an output from a node"""
    ...

class Workflow:
    """A class for manipulating workflows (described later)"""
    ...

class VAEDecode_749363c83c854e23a9bf916eb04fce09(_Node):
    """An example of a generated node (VAEDecode)"""
    # A uuid is appended to the end of the class name to avoid name collisions
    
    def __init__(
        self,
        samples: ComfyTypes.LATENT | ComfyOutput[ComfyTypes.LATENT] = _WILL_BE_LINKED,
        vae: ComfyTypes.VAE | ComfyOutput[ComfyTypes.VAE] = _WILL_BE_LINKED,
    ):
        ...
    
    @property
    def input_length(self) -> Literal[2]: return 2
    
    @property
    def output_length(self) -> Literal[1]: return 1
    
    @overload
    def input(self, index: Literal[0, "samples"]) -> ComfyInput[ComfyTypes.LATENT]: ...
    
    @overload
    def input(self, index: Literal[1, "vae"]) -> ComfyInput[ComfyTypes.VAE]: ...
    
    def input(self, index: int | str) -> ComfyInput[Any]: return super().input(index)
    
    def inputs(self) -> tuple[ComfyInput[ComfyTypes.LATENT], ComfyInput[ComfyTypes.VAE]]: return super().inputs()
    
    @overload
    def output(self, index: Literal[0, "IMAGE"]) -> ComfyOutput[ComfyTypes.IMAGE]: ...
    
    def output(self, index: int | str) -> ComfyOutput[Any]: return super().output(index)
    
    def outputs(self) -> tuple[ComfyOutput[ComfyTypes.IMAGE]]: return super().outputs()
    
    __truediv__ = output
    __rtruediv__ = input

...

class latent:
    """Use this"""
    VAEDecode = VAEDecode_749363c83c854e23a9bf916eb04fce09
    VAEEncode = VAEEncode_ce9eb09b4fae44b3a4cb0953c8888e30
    ...
```

### Building Workflows

Usage examples can be found in [test.py](./test.py).

The following assumes that the stub file is saved as `./nodes.py`.

#### 1. Low-level Construction Method

Add nodes to the workflow with `Workflow.add(node)`. Arguments not passed during node construction need to be connected to outputs from other nodes later.

For each node, you can get the nth input or output with `Node.input(n)` or `Node.output(n)`. You can retrieve them using ordinals (`0`, `1`, ...), names (`"clip"`), or type names (`"CLIP"`).

To connect the output and the input, call `Workflow.link(src, dst)`.

After adding everything, perform error checking with `Workflow.check()`.

Output the workflow with `Workflow.to_dict()`.

```python
import nodes

# Prepare workflow
wf = nodes.Workflow()

# Constants for image generation
CKPT = "SDXL/animagine-xl-3.1.safetensors"
PROMPT = "1girl, solo, original, masterpiece, best quality"
NEGATIVE_PROMPT = "bad quality, worst quality, low quality, text, watermark"

# Generate nodes
ckpt = nodes.loaders.CheckpointLoaderSimple(CKPT)
prompt = nodes.conditioning.CLIPTextEncode(PROMPT)
negative_prompt = nodes.conditioning.CLIPTextEncode(NEGATIVE_PROMPT)
latent = nodes.latent.EmptyLatentImage(512, 512, 1)
sampler = nodes.sampling.KSampler(sampler_name="euler", scheduler="normal")
decode = nodes.latent.VAEDecode()
save = nodes.image.SaveImage(filename_prefix="test")

# Add nodes to the workflow
wf.add(ckpt)
wf.add(prompt)
wf.add(negative_prompt)
wf.add(latent)
wf.add(sampler)
wf.add(decode)
wf.add(save)

# Connect nodes
wf.link(ckpt.output("CLIP"), prompt.input("clip"))
wf.link(ckpt.output("CLIP"), negative_prompt.input("clip"))
wf.link(ckpt.output("MODEL"), sampler.input("model"))
wf.link(prompt.output(0), sampler.input("positive"))
wf.link(negative_prompt.output(0), sampler.input("negative"))
wf.link(latent.output(0), sampler.input("latent_image"))
wf.link(sampler.output(0), decode.input("samples"))
wf.link(ckpt.output("VAE"), decode.input("vae"))
wf.link(decode.output(0), save.input("images"))

# Error checking
wf.check()

# Output in dict format, save with json.dump
x = wf.to_dict()
with open("workflow.json", "w") as io:
    json.dump(x, io, indent=4)
```

#### 2. Shorthands

There are several shortcuts available when you find it tedious to call `Workflow.add(node)` and `Workflow.link(src, dst)` repeatedly.

Note that these must be done within a `with Workflow():` block. In this case, `Workflow.check()` is executed within `Workflow.__exit__(...)`, so you don't need to explicitly call `Workflow.check()`.

**1. Directly passing another node's `output(n)`**

Within a `with Workflow()` block, instead of connecting nodes later, you can pass the output of another node directly during node construction.

```python
CheckpointLoaderSimple = nodes.loaders.CheckpointLoaderSimple
CLIPTextEncode = nodes.conditioning.CLIPTextEncode

with nodes.Workflow() as wf:
    ckpt = CheckpointLoaderSimple(CKPT)
    prompt = CLIPTextEncode(PROMPT, ckpt.output("CLIP"))
                                  # ~~~~~~~~~~~~~~~~~~~
```

Also, you can get all outputs with `Node.outputs()`, so you can do the following:

```python
with nodes.Workflow() as wf:
    model, clip, vae = CheckpointLoaderSimple(CKPT).outputs()  # <- add .outputs()
    prompt = CLIPTextEncode(PROMPT, clip)
```

All inputs and outputs are typed, so invalid inputs can be detected by the type checker.

```python
with nodes.Workflow() as wf:
    model, clip, vae = CheckpointLoaderSimple(CKPT).outputs()
    prompt = CLIPTextEncode(PROMPT, model)
    # error:                        ~~~~~
    # error: Type "ComfyOutput[MODEL]" cannot be assigned to type "CLIP | ComfyOutput[CLIP]"
```

**2. Connecting `output(n)` and `input(n)` with `-`**

`ComfyOutput` has `__sub__` defined, allowing you to connect the output and the input with `-`.

```python
with nodes.Workflow() as wf:
    ckpt = CheckpointLoaderSimple(CKPT)
    prompt = CLIPTextEncode(PROMPT)
    ckpt.output("CLIP") - prompt.input("clip")
```

Some type checkers may warn about discarding the value of the expression, so suppress the warning as needed.

**3. Connecting `src_node / n` and `m / dst_node` with `-`**

`n / Node` or `Node.__truediv__(n)` is an alias for `Node.output(n)`.

Similarly, `Node / n` or `Node.__rtruediv__(n)` is an alias for `Node.input(n)`.

```python
with nodes.Workflow() as wf:
    ckpt = CheckpointLoaderSimple(CKPT)
    prompt = CLIPTextEncode(PROMPT)
    ckpt / "CLIP" - "clip" / prompt
```

#### 3. Calling Workflows

In addition to outputting with `Workflow.to_dict()`, created workflows can be sent to a running ComfyUI for processing with `Workflow.call()` or `await Workflow.acall()`.

```python
class Workflow:
    def call(
        self,
        url: str = "http://127.0.0.1:8188",
        timeout: float = 60.0,
    ) -> dict:
        ...

    async def acall(
        self,
        url: str = "http://127.0.0.1:8188",
        timeout: float = 60.0,
    ) -> dict:
        ...
```

The return value is the JSON returned by ComfyUI.

A `TimeoutError` occurs if the number of seconds specified in `timeout` elapses.

Below is an example of generating an image with SDXL:

```python
# Import the stub file
import nodes

# Constants for generation
CKPT = "SDXL/animagine-xl-3.1.safetensors"
PROMPT = "1girl, solo, original, masterpiece, best quality"
NEGATIVE_PROMPT = "bad quality, worst quality, low quality, text, watermark"

# Build workflow
with nodes.Workflow() as wf:
    model, clip, vae = nodes.loaders.CheckpointLoaderSimple(CKPT).outputs()
    cond = nodes.conditioning.CLIPTextEncode(PROMPT, clip).output(0)
    uncond = nodes.conditioning.CLIPTextEncode(NEGATIVE_PROMPT, clip).output(0)
    latent = nodes.latent.EmptyLatentImage(512, 512, 1).output(0)
    samples = nodes.sampling.KSampler(model, 0, 20, 8.0, "euler", "normal", cond, uncond, latent).output(0)
    images = nodes.latent.VAEDecode(samples, vae).output(0)
    save = nodes.image.SaveImage(images, filename_prefix="test")

# Call workflow
wf.call()
```

### `/node-api-schema`

Returns a JSON Schema containing information about the inputs and outputs of all nodes, to provide editor support when writing JSON files for the API by hand.

It has the following format:

*Note: As of 2025/04/15, there is no documentation for ComfyUI's API JSON Schema. Therefore, be aware that the JSON Schema output by this API may become unusable in the future.*

```json
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$ref": "#/definitions/ComfyAPIWorkflowUnofficial",
    "definitions": {
        ...
        "ComfyAPIWorkflowUnofficial": {
            "oneOf": [
                {
                    ...
                },
                {
                    "$ref": "#/definitions/nodeType"
                }
            ]
        },
        "nodeType": {
            "oneOf": [
                {
                    ...
                },
                {
                    // Example of VAEDecode
                    "type": "object",
                    "properties": {
                        "class_type": {
                            "type": "string",
                            "const": "VAEDecode"
                        },
                        "_meta": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string"
                                }
                            },
                            "required": [
                                "title"
                            ]
                        },
                        "inputs": {
                            "type": "object",
                            "properties": {
                                "samples": {
                                    "$ref": "#/definitions/link"
                                },
                                "vae": {
                                    "$ref": "#/definitions/link"
                                }
                            },
                            "required": [
                                "samples",
                                "vae"
                            ]
                        }
                    },
                    "required": [
                        "class_type",
                        "_meta",
                        "inputs"
                    ]
                },
            ]
        }
    }
}
```
