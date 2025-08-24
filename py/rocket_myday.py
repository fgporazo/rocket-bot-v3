import discord
from discord.ext import commands
import json
import os
import random
from datetime import datetime

MYDAY_FILE = "json/rocket_myday.json"
CONTESTANTS_FILE = "json/rocket_contestants.json"


def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)


def get_today():
    return datetime.now().strftime("%Y-%m-%d")


class MyDay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="myday", invoke_without_command=True)
    async def myday(self, ctx, *, message: str = None):
        if message is None:
            await ctx.send(
                "⚡ **MyDay Commands:**\n"
                "`.myday start` → Randomly pick 3 contestants for today.\n"
                "`.myday reset` → Reset today’s MyDay session.\n"
                "`.myday history` → View today’s MyDay activity.\n"
                "DM the bot with `.myday <message> public/private` if you are chosen."
            )

    @myday.command(name="start")
    async def myday_start(self, ctx):
        guild_id = str(ctx.guild.id)
        data = load_json(MYDAY_FILE)
        contestants = load_json(CONTESTANTS_FILE)

        today = get_today()

        if guild_id not in data:
            data[guild_id] = {}

        if today in data[guild_id]:
            await ctx.send("⚠️ MyDay has already been started today. Use `.myday reset` if needed.")
            return

        # get contestant list for this guild
        guild_contestants = contestants.get(guild_id, [])
        if len(guild_contestants) < 3:
            await ctx.send("❌ Not enough contestants to start MyDay (need at least 3).")
            return

        chosen = random.sample(guild_contestants, 3)
        data[guild_id][today] = {
            "chosen": chosen,
            "entries": {}
        }
        save_json(MYDAY_FILE, data)

        await ctx.send(f"🌞 MyDay started! 3 contestants have been chosen for **{today}**.")

        # DM each chosen contestant
        for user_id in chosen:
            user = self.bot.get_user(int(user_id))
            if user:
                try:
                    await user.send(
                        "🚀 Team Rocket chose you for **MyDay** today!\n"
                        "Reply with `.myday <message> public` to share publicly in the server\n"
                        "or `.myday <message> private` to keep it secret."
                    )
                except discord.Forbidden:
                    pass

    @myday.command(name="reset")
    async def myday_reset(self, ctx):
        guild_id = str(ctx.guild.id)
        data = load_json(MYDAY_FILE)
        today = get_today()

        if guild_id in data and today in data[guild_id]:
            del data[guild_id][today]
            save_json(MYDAY_FILE, data)
            await ctx.send("♻️ MyDay has been reset for today.")
        else:
            await ctx.send("⚠️ No MyDay session to reset today.")

    @myday.command(name="history")
    async def myday_history(self, ctx):
        guild_id = str(ctx.guild.id)
        data = load_json(MYDAY_FILE)
        today = get_today()

        if guild_id not in data or today not in data[guild_id]:
            await ctx.send("📭 No MyDay has started today.")
            return

        chosen = data[guild_id][today]["chosen"]
        entries = data[guild_id][today]["entries"]

        lines = []
        for uid in chosen:
            user = self.bot.get_user(int(uid))
            name = user.name if user else uid
            if uid in entries:
                msg = entries[uid]["message"]
                privacy = entries[uid]["privacy"]
                if privacy == "public":
                    lines.append(f"🌟 **{name}** — {msg}")
                else:
                    lines.append(f"🙈 {name} kept their entry private.")
            else:
                lines.append(f"⏳ {name} has not submitted yet.")

        embed = discord.Embed(
            title=f"MyDay — {today}",
            description="\n".join(lines),
            color=discord.Color.purple()
        )
        await ctx.send(embed=embed)

    # DM handler for chosen users
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not isinstance(message.channel, discord.DMChannel):
            return

        if not message.content.startswith(".myday "):
            return

        user_id = str(message.author.id)
        data = load_json(MYDAY_FILE)
        today = get_today()

        # find guild where this user was chosen today
        for guild_id, sessions in data.items():
            if today in sessions and user_id in sessions[today]["chosen"]:
                entry_text = message.content[7:].strip()

                # check privacy
                privacy = "public"
                if entry_text.lower().endswith(" private"):
                    privacy = "private"
                    entry_text = entry_text[:-7].strip()
                elif entry_text.lower().endswith(" public"):
                    privacy = "public"
                    entry_text = entry_text[:-6].strip()

                sessions[today]["entries"][user_id] = {
                    "message": entry_text,
                    "privacy": privacy
                }
                save_json(MYDAY_FILE, data)

                # confirm to user
                await message.channel.send(f"✅ Your MyDay entry for {today} has been saved as **{privacy}**.")

                # announce in guild if public
                if privacy == "public":
                    guild = self.bot.get_guild(int(guild_id))
                    if guild:
                        channel = guild.system_channel or guild.text_channels[0]
                        await channel.send(f"🌟 MyDay from **{message.author.display_name}**: {entry_text}")

                return


async def setup(bot):
    await bot.add_cog(MyDay(bot))
