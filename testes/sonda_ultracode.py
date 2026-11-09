# Sonda: abre uma sessao com ultracode contra a API falsa e mostra o que o
# Claude Code embutido anuncia (ferramentas, ultracode) - sem gastar cota.
import asyncio, json, sys
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, SystemMessage

async def main(tools):
    op = ClaudeAgentOptions(model="opus", tools=tools, setting_sources=[],
                            settings=json.dumps({"ultracode": True}),
                            env={"CLAUDE_CODE_WORKFLOWS": "1"}, cwd="/tmp")
    async with ClaudeSDKClient(options=op) as c:
        await c.query("oi")
        async for m in c.receive_response():
            if isinstance(m, SystemMessage) and m.subtype == "init":
                d = m.data
                print("TOOLS:", d.get("tools"))
                print("CHAVES:", sorted(k for k in d if "ultra" in k.lower() or "effort" in k.lower() or "workflow" in k.lower()),
                      {k: d[k] for k in d if "ultra" in k.lower() or "effort" in k.lower()})

asyncio.run(main(json.loads(sys.argv[1])))
