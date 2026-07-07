import asyncio
import os
os.environ.setdefault("DISCORD_TOKEN", "dummy")

from apps.discord_bot.main import ElevenBossBot

async def main():
    bot = ElevenBossBot()
    await bot.setup_hook()
    cmds = []
    for c in bot.tree.get_commands():
        if hasattr(c, "commands"):
            for sc in c.commands:
                cmds.append(f"/{c.name} {sc.name}")
        else:
            cmds.append(f"/{c.name}")
    print("REGISTERED IN TREE:", len(cmds))
    for name in sorted(cmds):
        print(" ", name)

asyncio.run(main())
