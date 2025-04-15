import json
from test import node_types as nodes


def main():
    wf = nodes.Workflow()

    CKPT = "SDXL\\animagine-xl-3.1.safetensors"
    PROMPT = "1girl, solo, original, masterpiece, best quality"
    NEGATIVE_PROMPT = "bad quality, worst quality, low quality, text, watermark"

    ckpt = nodes.loaders.CheckpointLoaderSimple(CKPT)
    prompt = nodes.conditioning.CLIPTextEncode(PROMPT)
    negative_prompt = nodes.conditioning.CLIPTextEncode(NEGATIVE_PROMPT)
    latent = nodes.latent.EmptyLatentImage(512, 512, 1)
    sampler = nodes.sampling.KSampler(sampler_name="euler", scheduler="normal")
    decode = nodes.latent.VAEDecode()
    save = nodes.image.SaveImage(filename_prefix="test")

    wf.add(ckpt)
    wf.add(prompt)
    wf.add(negative_prompt)
    wf.add(latent)
    wf.add(sampler)
    wf.add(decode)
    wf.add(save)

    wf.link(ckpt.output("CLIP"), prompt.input("clip"))
    wf.link(ckpt.output("CLIP"), negative_prompt.input("clip"))
    wf.link(ckpt.output("MODEL"), sampler.input("model"))
    wf.link(prompt.output(0), sampler.input("positive"))
    wf.link(negative_prompt.output(0), sampler.input("negative"))
    wf.link(latent.output(0), sampler.input("latent_image"))
    wf.link(sampler.output(0), decode.input("samples"))
    wf.link(ckpt.output("VAE"), decode.input("vae"))
    wf.link(decode.output(0), save.input("images"))

    wf.check()

    x = wf.to_dict()
    with open("workflow.json", "w") as io:
        json.dump(x, io, indent=4)


def main2():
    wf = nodes.Workflow()

    CKPT = "SDXL\\animagine-xl-3.1.safetensors"
    PROMPT = "1girl, solo, original, masterpiece, best quality"
    NEGATIVE_PROMPT = "bad quality, worst quality, low quality, text, watermark"

    with wf:
        ckpt = nodes.loaders.CheckpointLoaderSimple(CKPT)
        prompt = nodes.conditioning.CLIPTextEncode(PROMPT, ckpt.output("CLIP"))
        negative_prompt = nodes.conditioning.CLIPTextEncode(NEGATIVE_PROMPT, ckpt.output("CLIP"))
        latent = nodes.latent.EmptyLatentImage(512, 512, 1)
        sampler = nodes.sampling.KSampler(
            ckpt.output("MODEL"),
            positive=prompt.output(0),
            negative=negative_prompt.output(0),
            sampler_name="euler",
            scheduler="normal",
            latent_image=latent.output(0),
        )
        decode = nodes.latent.VAEDecode(sampler.output(0), ckpt.output("VAE"))
        save = nodes.image.SaveImage(decode.output(0), filename_prefix="test")

    x = wf.to_dict()
    with open("workflow.json", "w") as io:
        json.dump(x, io, indent=4)


def main3():
    CKPT = "SDXL\\animagine-xl-3.1.safetensors"
    PROMPT = "1girl, solo, original, masterpiece, best quality"
    NEGATIVE_PROMPT = "bad quality, worst quality, low quality, text, watermark"
    WIDTH = 512
    HEIGHT = 512
    BATCH_SIZE = 1

    ckpt = nodes.loaders.CheckpointLoaderSimple(CKPT)
    prompt = nodes.conditioning.CLIPTextEncode(PROMPT)
    negative_prompt = nodes.conditioning.CLIPTextEncode(NEGATIVE_PROMPT)
    latent = nodes.latent.EmptyLatentImage(WIDTH, HEIGHT, BATCH_SIZE)
    sampler = nodes.sampling.KSampler(sampler_name="euler", scheduler="normal")
    decode = nodes.latent.VAEDecode()
    save = nodes.image.SaveImage(filename_prefix="test")

    with nodes.Workflow() as wf:
        ckpt.output("CLIP") - prompt.input("clip")
        ckpt.output("CLIP") - negative_prompt.input("clip")
        ckpt.output("MODEL") - sampler.input("model")
        prompt.output(0) - sampler.input("positive")
        negative_prompt.output(0) - sampler.input("negative")
        latent.output(0) - sampler.input("latent_image")
        sampler.output(0) - decode.input("samples")
        ckpt.output("VAE") - decode.input("vae")
        decode.output(0) - save.input("images")

    x = wf.to_dict()
    with open("workflow.json", "w") as io:
        json.dump(x, io, indent=4)


def main4():
    CKPT = "SDXL\\animagine-xl-3.1.safetensors"
    PROMPT = "1girl, solo, original, masterpiece, best quality"
    NEGATIVE_PROMPT = "bad quality, worst quality, low quality, text, watermark"

    ckpt = nodes.loaders.CheckpointLoaderSimple(CKPT)
    prompt = nodes.conditioning.CLIPTextEncode(PROMPT)
    negative_prompt = nodes.conditioning.CLIPTextEncode(NEGATIVE_PROMPT)
    latent = nodes.latent.EmptyLatentImage(512, 512, 1)
    sampler = nodes.sampling.KSampler(sampler_name="euler", scheduler="normal")
    decode = nodes.latent.VAEDecode()
    save = nodes.image.SaveImage(filename_prefix="test")

    with nodes.Workflow() as wf:
        ckpt / "CLIP" - "clip" / prompt
        ckpt / "CLIP" - "clip" / negative_prompt
        ckpt / "MODEL" - "model" / sampler
        prompt / 0 - "positive" / sampler
        negative_prompt / 0 - "negative" / sampler
        latent / 0 - "latent_image" / sampler
        sampler / 0 - "samples" / decode
        ckpt / "VAE" - "vae" / decode
        decode / 0 - "images" / save

    x = wf.to_dict()
    with open("workflow.json", "w") as io:
        json.dump(x, io, indent=4)


def main5():
    import struct
    import random
    from multiprocessing import shared_memory as sm
    from io import BytesIO
    from PIL import Image

    CKPT = "SDXL\\animagine-xl-3.1.safetensors"
    PROMPT = "1girl, solo, original, masterpiece, best quality"
    NEGATIVE_PROMPT = "bad quality, worst quality, low quality, text, watermark"
    WIDTH = 512
    HEIGHT = 512
    BATCH_SIZE = 1
    MEMORY_TAG = "test123"

    ckpt = nodes.loaders.CheckpointLoaderSimple(CKPT)
    prompt = nodes.conditioning.CLIPTextEncode(PROMPT)
    negative_prompt = nodes.conditioning.CLIPTextEncode(NEGATIVE_PROMPT)
    latent = nodes.latent.EmptyLatentImage(WIDTH, HEIGHT, BATCH_SIZE)
    sampler = nodes.sampling.KSampler(sampler_name="euler", scheduler="normal")
    decode = nodes.latent.VAEDecode()
    save = nodes.hnmr.image.SaveImagesMemory(MEMORY_TAG, dummy_input=random.randint(0, 9999))  # enforce rerun

    with nodes.Workflow() as wf:
        ckpt.output("CLIP") - prompt.input("clip")
        ckpt.output("CLIP") - negative_prompt.input("clip")
        ckpt.output("MODEL") - sampler.input("model")
        prompt.output(0) - sampler.input("positive")
        negative_prompt.output(0) - sampler.input("negative")
        latent.output(0) - sampler.input("latent_image")
        sampler.output(0) - decode.input("samples")
        ckpt.output("VAE") - decode.input("vae")
        decode.output(0) - save.input("images")

    header_fmt = f"=I{BATCH_SIZE}I"
    header_size = struct.calcsize(header_fmt)
    mem_size = WIDTH * HEIGHT * 4 * BATCH_SIZE + header_size

    shim = None
    result_images = None
    try:
        # breakpoint()
        shim = sm.SharedMemory(name=MEMORY_TAG, create=True, size=mem_size)
        shim.buf[:4] = b"\x00\x00\x00\x00"

        data = wf.call()

        if shim.buf[:4] != b"\x00\x00\x00\x00":
            # ok
            n, *lens = struct.unpack(header_fmt, shim.buf[:header_size])
            result_images = []
            offset = header_size
            for nbytes in lens:
                with BytesIO(shim.buf[offset : offset + nbytes]) as io:
                    img = Image.open(io).convert("RGB")
                    result_images.append(img)
                offset += nbytes
    finally:
        if shim is not None:
            shim.close()
            shim.unlink()

    if result_images is None or len(result_images) != BATCH_SIZE:
        raise RuntimeError("No data received")

    for i, img in enumerate(result_images):
        img.save(f"test-{i}.png")


if __name__ == "__main__":
    main5()
