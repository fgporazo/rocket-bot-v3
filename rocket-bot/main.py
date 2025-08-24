# main.py
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from keep_alive import keep_alive  # optional
from py.rocket_thread_restriction import global_thread_check, load_restrictions

# ─── Load environment ─────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ DISCORD_TOKEN not set in .env")
    exit(1)

# ─── Bot setup ─────────────────────────────
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=".", intents=intents)
# ─── Landing message when joining a server ─────────────
@bot.event
async def on_guild_join(guild):
    channel = discord.utils.get(guild.text_channels, name="rocketbot")
    message = (
        "🚀 **Hey Rocket Players!**\n"
        "Thanks for letting me land—I promise I won’t crash your channel… at least not on purpose! 😎\n"
        "Type `.tr help` to unleash commands, boosts, and a little controlled **chaos**. Bwahahahaha! Let’s blast off! 🚀"
    )
    if channel and channel.permissions_for(guild.me).send_messages:
        await channel.send(message)
    else:
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                await ch.send(message)
                break
# ─── Load all extensions ─────────────────────────────
async def load_extensions():
    extensions = [
        "py.rocket_slash_commands",
        "py.rocket_date_game",
        "py.rocket_pokemon_game",
        "py.rocket_campfire",
        "py.rocket_myday",
        "py.rocket_personality_test",
        "py.rocket_drawing_date",
    ]
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"✅ {ext} loaded")
        except Exception as e:
            print(f"❌ Failed to load {ext}: {e}")

# ─── Bot ready event ─────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        await bot.tree.sync()
        print("✅ Slash commands synced globally")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

# ─── Start bot ─────────────────────────────
async def main():
    await load_extensions()
    keep_alive()  # optional for hosting
    await bot.start(TOKEN)

asyncio.run(main())
