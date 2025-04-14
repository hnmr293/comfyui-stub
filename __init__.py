from aiohttp import web
from server import PromptServer

from .src.defn import collect_defns
from .src.make_json import create_schema_for_api
from .src.gen_stub import generate_stub


@PromptServer.instance.routes.get("/node-api-schema")
async def get_node_schema(request):
    defns = list(collect_defns().values())
    schema = create_schema_for_api(defns)
    return web.json_response(schema)


@PromptServer.instance.routes.get("/node-api-stub")
async def get_node_stubs(request):
    defns = list(collect_defns().values())
    stub = generate_stub(defns)
    return web.Response(
        text=stub,
        content_type="text/plain",
        charset="utf-8",
    )
