# ComfyUI-Stub

[English ver.](./README.md)

ComfyUI のノード一覧を操作するためのスタブファイル、および各ノードの入出力を記述した JSON Schema を生成します。

APIとして

- `{ComfyUIのURL}/node-api-stub`
- `{ComfyUIのURL}/node-api-schema`

が追加されます。

たとえば以下のようにしてスタブファイルを取得・保存できます。

```python
import requests
res = requests.get('http://127.0.0.1:8188/node-api-stub')
with open('nodes.py', 'w') as io:
    io.write(res.text)
```

# API

## `/node-api-stub`

python 用のスタブファイルを生成します。

生成されるファイルは外部のファイルやライブラリへの依存性が無く、単体で `import` して使用できます。

### スタブファイルの構造

生成されるファイルは以下のような構造になっています。

各ノードの入出力は完全に型付けされています。

```python
class ComfyTypes:
    """ComfyUI で使用される型を集めたクラス（名前空間）"""
    INT: TypeAlias = int
    FLOAT: TypeAlias = float
    ...

    MODEL = type("MODEL", (object,), {})
    CONDITIONING = type("CONDITIONING", (object,), {})
    ...

@dataclass(frozen=True)
class ComfyInput(Generic[_T]):
    """ノードへの入力を表すクラス"""
    ...

@dataclass(frozen=True)
class ComfyOutput(Generic[_T]):
    """ノードからの出力を表すクラス"""
    ...

class Workflow:
    """ワークフローを操作するためのクラス（後述）"""
    ...

class VAEDecode_749363c83c854e23a9bf916eb04fce09(_Node):
    """生成されるノードの例 (VAEDecode)"""
    # 名前の衝突を避けるため、クラス名の末尾に uuid を付与しています
    
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
    """外部から呼び出すときはこちらを使用します"""
    VAEDecode = VAEDecode_749363c83c854e23a9bf916eb04fce09
    VAEEncode = VAEEncode_ce9eb09b4fae44b3a4cb0953c8888e30
    ...
```

### ワークフローの構築

使用例は [test.py](./test.py) にあります。

以下、スタブファイルが `./nodes.py` に保存されているとします。

#### 1. 低レベルな構築方法

`Workflow.add(node)` でワークフローにノードを追加します。ノードの構築時に渡されなかった引数は、後から別ノードの出力をつなぐ必要があります。

各ノードに対して `Node.input(n)` や `Node.output(n)` で n 番目の入出力を取得できます。序数 (`0`, `1`, ...) のほか、名前 (`"clip"`) や型名 (`"CLIP"`) でも取得可能です。

出力を入力につなげるには `Workflow.link(src, dst)` を呼び出します。

すべて追加し終わったら、`Workflow.check()` でエラーチェックを行います。

ワークフローの出力は `Workflow.to_dict()` により行います。

```python
import nodes

# ワークフローの準備
wf = nodes.Workflow()

# 画像生成用の定数
CKPT = "SDXL/animagine-xl-3.1.safetensors"
PROMPT = "1girl, solo, original, masterpiece, best quality"
NEGATIVE_PROMPT = "bad quality, worst quality, low quality, text, watermark"

# ノードの生成
ckpt = nodes.loaders.CheckpointLoaderSimple(CKPT)
prompt = nodes.conditioning.CLIPTextEncode(PROMPT)
negative_prompt = nodes.conditioning.CLIPTextEncode(NEGATIVE_PROMPT)
latent = nodes.latent.EmptyLatentImage(512, 512, 1)
sampler = nodes.sampling.KSampler(sampler_name="euler", scheduler="normal")
decode = nodes.latent.VAEDecode()
save = nodes.image.SaveImage(filename_prefix="test")

# ワークフローにノードを追加する
wf.add(ckpt)
wf.add(prompt)
wf.add(negative_prompt)
wf.add(latent)
wf.add(sampler)
wf.add(decode)
wf.add(save)

# ノード同士をつなぐ
wf.link(ckpt.output("CLIP"), prompt.input("clip"))
wf.link(ckpt.output("CLIP"), negative_prompt.input("clip"))
wf.link(ckpt.output("MODEL"), sampler.input("model"))
wf.link(prompt.output(0), sampler.input("positive"))
wf.link(negative_prompt.output(0), sampler.input("negative"))
wf.link(latent.output(0), sampler.input("latent_image"))
wf.link(sampler.output(0), decode.input("samples"))
wf.link(ckpt.output("VAE"), decode.input("vae"))
wf.link(decode.output(0), save.input("images"))

# エラーチェック
wf.check()

# dict 形式で出力し、json.dump で保存する
x = wf.to_dict()
with open("workflow.json", "w") as io:
    json.dump(x, io, indent=4)
```

#### 2. 糖衣構文

いちいち `Workflow.add(node)` や `Workflow.link(src, dst)` を呼ぶのが面倒なときはいくつかのショートカットが使えます。

いずれも `with Workflow():` の中で行う必要があることに注意してください。この場合、`Workflow.__exit__(...)` の中で `Workflow.check()` を実行しているので、`Workflow.check()` を明示的に呼びだす必要はありません。

**1. 別ノードの `output(n)` を直接渡す**

`with Workflow()` の中では、後からノード同士をつなぐのではなく、ノード構築時に別ノードの出力をそのまま渡すことができます。

```python
CheckpointLoaderSimple = nodes.loaders.CheckpointLoaderSimple
CLIPTextEncode = nodes.conditioning.CLIPTextEncode

with nodes.Workflow() as wf:
    ckpt = CheckpointLoaderSimple(CKPT)
    prompt = CLIPTextEncode(PROMPT, ckpt.output("CLIP"))
                                  # ~~~~~~~~~~~~~~~~~~~
```

また、`Node.outputs()` ですべての出力を取得できるので、以下のようにもできます。

```python
with nodes.Workflow() as wf:
    model, clip, vae = CheckpointLoaderSimple(CKPT).outputs()  # <- .outputs() を追加
    prompt = CLIPTextEncode(PROMPT, clip)
```

入出力はすべて型付けされているため、型チェッカにより不正な入力を検出することができます。

```python
with nodes.Workflow() as wf:
    model, clip, vae = CheckpointLoaderSimple(CKPT).outputs()
    prompt = CLIPTextEncode(PROMPT, model)
    # error:                        ~~~~~
    # error: 型 "ComfyOutput[MODEL]" は型 "CLIP | ComfyOutput[CLIP]" に割り当てできません
```

**2. `output(n)` と `input(n)` を `-` でつなぐ**

`ComfyOutput` には `__sub__` が定義されており、`-` で出力 - 入力をつなぐことができます。

```python
with nodes.Workflow() as wf:
    ckpt = CheckpointLoaderSimple(CKPT)
    prompt = CLIPTextEncode(PROMPT)
    ckpt.output("CLIP") - prompt.input("clip")
```

型チェッカによっては式の値を捨てているという警告が出るので、必要に応じて警告の抑制を行ってください。

**3. `src_node / n` と `m / dst_node` を `-` でつなぐ**

`n / Node` すなわち `Node.__truediv__(n)` は `Node.output(n)` のエイリアスです。

同じく、`Node / n` すなわち `Node.__rtruediv__(n)` は `Node.input(n)` のエイリアスです。

```python
with nodes.Workflow() as wf:
    ckpt = CheckpointLoaderSimple(CKPT)
    prompt = CLIPTextEncode(PROMPT)
    ckpt / "CLIP" - "clip" / prompt
```

#### 3. ワークフローの呼び出し

作成したワークフローは、`Workflow.to_dict()` で出力するほか、`Workflow.call()` もしくは `await Workflow.acall()` により起動済みの ComfyUI に処理を投げることができます。

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

戻り値は ComfyUI が返す JSON です。

`timeout` に指定した秒数が経過すると `TimeoutError` が発生します。

SDXLによる画像生成を行う例を以下に示します。

```python
# スタブファイルの import
import nodes

# 生成用の定数
CKPT = "SDXL/animagine-xl-3.1.safetensors"
PROMPT = "1girl, solo, original, masterpiece, best quality"
NEGATIVE_PROMPT = "bad quality, worst quality, low quality, text, watermark"

# ワークフローの構築
with nodes.Workflow() as wf:
    model, clip, vae = nodes.loaders.CheckpointLoaderSimple(CKPT).outputs()
    cond = nodes.conditioning.CLIPTextEncode(PROMPT, clip).output(0)
    uncond = nodes.conditioning.CLIPTextEncode(NEGATIVE_PROMPT, clip).output(0)
    latent = nodes.latent.EmptyLatentImage(512, 512, 1).output(0)
    samples = nodes.sampling.KSampler(model, 0, 20, 8.0, "euler", "normal", cond, uncond, latent).output(0)
    images = nodes.latent.VAEDecode(samples, vae).output(0)
    save = nodes.image.SaveImage(images, filename_prefix="test")

# ワークフローの呼び出し
wf.call()
```

### `/node-api-schema`

API 用の JSON ファイルを手書きするときにエディタの支援が得られるよう、全ノードの入出力の情報を持った JSON Schema を返します。

以下の形式になっています。

※ComfyUI の API 用の JSON Schema については 2025/04/15 現在でドキュメント化されていません。したがって、この API で出力される JSON Schema はそのうち使えなくなる可能性があることに留意してください。

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
                    // VAEDecode の例
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
