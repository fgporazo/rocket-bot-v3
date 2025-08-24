import discord
from discord.ext import commands
import datetime
import json
import os
import random
import asyncio

MAX_CAMPERS = 2
CONFESS_TIMEOUT = 300  # 5 minutes


def load_json_file(filename, default=None):
    if not os.path.exists(filename):
        return default if default is not None else {}
    with open(filename, "r") as f:
        return json.load(f)


def save_json_file(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


def get_today():
    return datetime.datetime.utcnow().date().isoformat()


class RocketCampfire(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.file = "json/rocket_campfire.json"
        self.timeouts = {}  # guild_id -> asyncio.Task
        self.active_threads = {}  # guild_id -> thread_id

    def get_campfire(self, guild_id: str):
        data = load_json_file(self.file, {})
        return data.get(guild_id)

    def save_campfire(self, guild_id: str, record: dict):
        data = load_json_file(self.file, {})
        data[guild_id] = record
        save_json_file(self.file, data)

    # ── Base command
    @commands.group(name="cc", invoke_without_command=True)
    async def cc(self, ctx):
        await ctx.send(
            "🔥 Campfire commands:\n"
            "`.cc lit` — Light the campfire\n"
            "`.cc join` — Join campfire\n"
            "`.cc confess <yes/no> <message>` — Confess if chosen (DM only)\n"
            "`.cc history` — See today's confession\n"
            "`.cc reset` — Reset campfire for today")

    # ── .cc lit ──
    @cc.command(name="lit")
    async def cc_lit(self, ctx):
        guild_id = str(ctx.guild.id)
        today = get_today()

        data = load_json_file(self.file, {})
        record = data.get(guild_id)

        if record:
            last_reset = record.get("last_reset")
            if last_reset == today:
                if record.get("active"):
                    await ctx.send("❌ Campfire already active today! Cannot lit again.")
                    return
                if record.get("campers") and record.get("confession_message"):
                    await ctx.send("❌ Today's campfire already ended. Wait until tomorrow!")
                    return

        record = {
            "campers": [],
            "starter_camper": str(ctx.author.id),
            "chosen_camper": None,
            "confession_message": None,
            "active": True,
            "reactions": [],
            "isPublic": None,
            "thread_id": None,
            "starter_camper_channel_id": ctx.channel.id,
            "last_reset": today,
            "confession_msg_id": None
        }
        self.save_campfire(guild_id, record)

        try:
            file = discord.File("assets/campfire.gif", filename="campfire.gif")
            embed = discord.Embed(
                description=f"🔥 {ctx.author.display_name} lit the campfire! Waiting for campers to join... (max {MAX_CAMPERS})",
                color=discord.Color.orange())
            embed.set_image(url="attachment://campfire.gif")
            main_msg = await ctx.send(embed=embed, file=file)
        except:
            embed = discord.Embed(
                description=f"🔥 {ctx.author.display_name} lit the campfire! Waiting for campers to join... (max {MAX_CAMPERS})",
                color=discord.Color.orange())
            main_msg = await ctx.send(embed=embed)

        # ── Only create a thread if NOT already inside a thread ──
        if ctx.channel.type not in (discord.ChannelType.public_thread, discord.ChannelType.private_thread):
            thread_name = f"Campfire {today}"
            try:
                thread = await main_msg.create_thread(
                    name=thread_name,
                    auto_archive_duration=60,
                    reason="Campfire thread for today")
                record["thread_id"] = thread.id
                self.save_campfire(guild_id, record)
                await thread.send(
                    f"🔥 {ctx.author.display_name} lit the campfire! Join using `.cc join` to participate."
                )
            except Exception as e:
                await ctx.send(f"⚠️ Could not create campfire thread: {e}")
        else:
            # Already inside a thread
            record["thread_id"] = ctx.channel.id
            self.save_campfire(guild_id, record)
            await ctx.send(
                f"🔥 {ctx.author.display_name} lit the campfire inside this thread! Join using `.cc join` to participate."
            )

    # ── .cc join ──
    @cc.command(name="join")
    async def cc_join(self, ctx):
        guild_id = str(ctx.guild.id)
        record = self.get_campfire(guild_id)

        if not record or not record.get("active"):
            await ctx.send("❌ No active campfire. Use `.cc lit` to start one.")
            return

        campers = record.get("campers", [])
        user_id = str(ctx.author.id)

        if user_id in campers:
            await ctx.send("❌ You already joined this campfire.")
            return

        if len(campers) >= MAX_CAMPERS:
            await ctx.send("⚠️ Campfire is full. Cannot join.")
            return

        campers.append(user_id)
        record["campers"] = campers
        self.save_campfire(guild_id, record)
        await ctx.send(f"✅ {ctx.author.display_name} joined the campfire! ({len(campers)}/{MAX_CAMPERS})")

        if len(campers) == MAX_CAMPERS and not record.get("chosen_camper"):
            chosen = random.choice(campers)
            record["chosen_camper"] = chosen
            self.save_campfire(guild_id, record)
            member = ctx.guild.get_member(int(chosen))
            if member:
                try:
                    await member.send(
                        "💌 You have been chosen to confess! Use `.cc confess <yes/no> <message>` via DM within 5 minutes.\n"
                        "<yes> = announce your name publicly in the campfire thread\n"
                        "<no> = announce anonymously in the campfire thread")
                except:
                    pass

            # Start timeout
            async def timeout_task():
                await asyncio.sleep(CONFESS_TIMEOUT)
                r = self.get_campfire(guild_id)
                if r.get("active") and r.get("chosen_camper"):
                    r["active"] = False
                    r["chosen_camper"] = None
                    self.save_campfire(guild_id, r)
                    thread = ctx.guild.get_channel(record.get("thread_id")) or ctx.channel
                    await thread.send("⏰ Chosen camper did not confess in time. Campfire ended due to inactivity.")

            self.timeouts[guild_id] = self.bot.loop.create_task(timeout_task())

    # ── .cc confess ──
    @cc.command(name="confess")
    async def cc_confess(self, ctx, anon: str = None, *, message: str = None):
        if not anon or anon.lower() not in ("yes", "no") or not message:
            await ctx.send("Usage: `.cc confess <yes/no> <message>`")
            return

        if ctx.guild is not None:
            await ctx.send("❌ The `confess` command can only be used in DMs.")
            return

        user_id = str(ctx.author.id)

        # Find active campfire
        data = load_json_file(self.file, {})
        guild_id, record = None, None
        for g_id, r in data.items():
            if r.get("active") and r.get("chosen_camper") == user_id:
                guild_id = g_id
                record = r
                break

        if not record:
            await ctx.author.send("❌ You are not the chosen camper in any active campfire.")
            return

        guild = self.bot.get_guild(int(guild_id))
        thread = None

        # Prioritize active thread
        thread_id = record.get("thread_id")
        if thread_id:
            try:
                thread = await self.bot.fetch_channel(thread_id)
                if getattr(thread, "archived", False):
                    thread = None
            except:
                thread = None

        # Fallback to starter channel
        if not thread:
            starter_channel_id = record.get("starter_camper_channel_id")
            thread = guild.get_channel(starter_channel_id)

        if not thread:
            await ctx.author.send("❌ Could not find a channel to post confession.")
            return

        sender_text = ctx.author.display_name if anon.lower() == "yes" else "Anonymous"
        confess_msg = await thread.send(
            f"💌 {sender_text} confessed!\n"
            f"💬 {message}\n"
            "Whoa, campers! React to this shocking confession 😳🔥 Hit it with your emoji vibes 💥💌"
        )

        record["confession_message"] = message
        record["active"] = False
        record["chosen_camper"] = None
        record["isPublic"] = "yes" if anon.lower() == "yes" else "no"
        record["confession_msg_id"] = confess_msg.id
        record["reactions"] = []
        self.save_campfire(guild_id, record)

        await ctx.author.send(
            f"💌 Your confession has been announced in the campfire thread!\n"
            f"You chose {'public' if anon.lower()=='yes' else 'anonymous'}.\n"
            f"Confession: {message}"
        )

        async def wait_for_reactions():
            try:
                def check(reaction, user):
                    return (user.id != self.bot.user.id
                            and str(user.id) in record["campers"]
                            and reaction.message.id == confess_msg.id)

                while True:
                    reaction, user = await self.bot.wait_for("reaction_add", timeout=CONFESS_TIMEOUT, check=check)
                    if not any(r["user_id"] == str(user.id) for r in record["reactions"]):
                        record["reactions"].append({
                            "user_id": str(user.id),
                            "emoji": str(reaction.emoji)
                        })
                        self.save_campfire(guild_id, record)

                    if len(record["reactions"]) >= len(record.get("campers", [])):
                        await self.post_summary(guild_id, record)
                        break
            except asyncio.TimeoutError:
                await self.post_summary(guild_id, record)

        self.bot.loop.create_task(wait_for_reactions())

    # ── Post summary ──
    async def post_summary(self, guild_id, record):
        guild = self.bot.get_guild(int(guild_id))
        thread = None
        if record.get("thread_id"):
            try:
                thread = await self.bot.fetch_channel(record["thread_id"])
            except:
                pass
        if not thread:
            thread = guild.get_channel(record.get("starter_camper_channel_id"))

        campers_display = []
        for c_id in record.get("campers", []):
            member = guild.get_member(int(c_id))
            campers_display.append(member.display_name if member else f"<@{c_id}>")

        sender_display = "Anonymous"
        if record.get("isPublic") == "yes" and record.get("starter_camper"):
            member = guild.get_member(int(record.get("starter_camper")))
            sender_display = member.display_name if member else "Unknown"

        reactions = record.get("reactions", [])
        if reactions:
            reaction_text = ", ".join(
                f"{guild.get_member(int(r['user_id'])).display_name if guild.get_member(int(r['user_id'])) else r['user_id']} {r['emoji']}"
                for r in reactions)
        else:
            reaction_text = "No reactions yet."

        embed = discord.Embed(title="🔥 Campfire Ended! Summary 🔥",
                              color=discord.Color.gold())
        embed.add_field(name="Date", value=record.get("last_reset"), inline=False)
        embed.add_field(name="Campers", value=", ".join(campers_display), inline=False)
        embed.add_field(name="Confession Sender", value=sender_display, inline=False)
        embed.add_field(name="Confession Message", value=record.get("confession_message"), inline=False)
        embed.add_field(name="Reactions", value=reaction_text, inline=False)
        embed.set_footer(text="Next campfire available tomorrow!")

        await thread.send(embed=embed)

    # ── .cc history ──
    @cc.command(name="history")
    async def cc_history(self, ctx):
        guild_id = str(ctx.guild.id)
        record = self.get_campfire(guild_id)
        if not record or not record.get("confession_message"):
            await ctx.send("📖 No confessions today yet.")
            return

        guild = ctx.guild
        campers_display = []
        for c_id in record.get("campers", []):
            member = guild.get_member(int(c_id))
            campers_display.append(member.display_name if member else f"<@{c_id}>")

        sender_display = "Anonymous"
        if record.get("isPublic") == "yes" and record.get("starter_camper"):
            member = guild.get_member(int(record.get("starter_camper")))
            sender_display = member.display_name if member else "Unknown"

        reactions = record.get("reactions", [])
        if reactions:
            reaction_text = ", ".join(
                f"{guild.get_member(int(r['user_id'])).display_name if guild.get_member(int(r['user_id'])) else r['user_id']} {r['emoji']}"
                for r in reactions)
        else:
            reaction_text = "No reactions yet."

        embed = discord.Embed(title="📖 Today's Campfire Confession",
                              color=discord.Color.orange())
        embed.add_field(name="Campers", value=", ".join(campers_display), inline=False)
        embed.add_field(name="Confession Sender", value=sender_display, inline=False)
        embed.add_field(name="Confession Message", value=record.get("confession_message"), inline=False)
        embed.add_field(name="Reactions", value=reaction_text, inline=False)
        await ctx.send(embed=embed)

    # ── .cc reset ──
    @cc.command(name="reset")
    async def cc_reset(self, ctx):
        guild_id = str(ctx.guild.id)
        today = get_today()
        new_record = {
            "campers": [],
            "starter_camper": None,
            "chosen_camper": None,
            "confession_message": None,
            "active": True,
            "reactions": [],
            "isPublic": None,
            "thread_id": None,
            "starter_camper_channel_id": ctx.channel.id,
            "last_reset": today
        }
        self.save_campfire(guild_id, new_record)
        await ctx.send("♻️ Campfire has been reset for today. Ready for new confessions!")


async def setup(bot):
    await bot.add_cog(RocketCampfire(bot))
