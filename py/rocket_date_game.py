# rocket_date_game.py
import json
import discord
from discord.ext import commands
import random
from typing import Optional, Dict, Any, List, Tuple
from helpers import (
    PROTECTED_IDS,
    ADMIN_IDS,
    DATE_LIMIT_PER_DAY,
    ADMIN_DATE_LIMIT_PER_DAY,
    registered_users,
    date_requests,
    leaderboard,
    history,
    load_data,
    save_all_data,
    load_json_file,
    save_json_file,
    is_admin,
    get_today,
    get_display_name_fast,
    ensure_registered,
    get_author_and_guild,
    PaginatedEmbed,
    _send,
)


class RocketDate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Load fun text lines
        self.HELP_DATA = load_json_file("json/help_text.json", {"title": "Help", "description": []})
        self.roast_lines = load_json_file("json/roast_lines.json", [])
        self.scream_lines = load_json_file("json/scream_lines.json", [])
        self.drama_lines = load_json_file("json/drama_lines.json", [])
        self.thunderbolt_lines = load_json_file("json/thunderbolt_lines.json", [])
        self.thunderbolt_protected_lines = load_json_file("json/thunderbolt_protected_replies.json", [])

        # Queues to prevent repeats
        self.roast_queue = self.roast_lines.copy()
        random.shuffle(self.roast_queue)

        self.scream_queue = self.scream_lines.copy()
        random.shuffle(self.scream_queue)
        self.last_scream_template = None

        self.drama_queue = self.drama_lines.copy()
        random.shuffle(self.drama_queue)
        self.last_drama_template = None

        self.thunderbolt_queue = self.thunderbolt_lines.copy()
        random.shuffle(self.thunderbolt_queue)

    # ---------------- Core E-Date Handlers ----------------
    async def handle_rocket_date(self, source, sender, receiver):
        if not receiver:
            await _send(source, "❌ You must mention a user to date!")
            return

        sender_id = str(sender.id)
        receiver_id = str(receiver.id)
        guild_id = str(source.guild.id)

        guild_users = registered_users.setdefault(guild_id, {})
        guild_requests = date_requests.setdefault(guild_id, {})

        if sender_id == receiver_id and not is_admin(sender):
            await _send(source, "🙃 You can’t e-date yourself!")
            return

        if sender_id not in guild_users:
            await _send(source, "🚨 You must register first using `/rocket-register` or `.tr reg`!")
            return

        if receiver_id not in guild_users:
            await _send(source, "🚫 That user isn’t a registered contestant yet.")
            return

        # Already requested today?
        today = str(get_today())
        existing_requests = [r for r, d in guild_requests.get(sender_id, []) if d == today and r == receiver_id]
        if existing_requests:
            await _send(source, "🛑 You already sent a date request to that user today.")
            return

        # Rate limit
        daily_requests = [r for r, date_str in guild_requests.get(sender_id, []) if date_str == today]
        limit = ADMIN_DATE_LIMIT_PER_DAY if is_admin(sender) else DATE_LIMIT_PER_DAY
        if len(daily_requests) >= limit:
            await _send(source, f"💥 You’ve already sent {limit} date request(s) today!")
            return

        # Store request
        guild_requests.setdefault(sender_id, []).append((receiver_id, today))
        save_all_data()

        await _send(
            source,
            f"💘 {sender.mention} asked {receiver.mention} out! Reply with `.tr dateyes @user` or `.tr dateno @user <reason>`."
        )

    async def handle_rocket_date_yes(self, source, sender, target):
        if not target:
            await _send(source, "❌ You must mention a user to accept a date!")
            return

        sender_id = str(sender.id)
        target_id = str(target.id)
        guild_id = str(source.guild.id)

        guild_requests = date_requests.setdefault(guild_id, {})
        guild_leaderboard = leaderboard.setdefault(guild_id, {})
        guild_history = history.setdefault(guild_id, {})

        valid_requests = guild_requests.get(target_id, [])
        if not any(rid == sender_id for rid, _ in valid_requests):
            await _send(source, f"❌ No e-date request found from {target.display_name}.")
            return

        # Remove accepted request
        guild_requests[target_id] = [(rid, ts) for rid, ts in valid_requests if rid != sender_id]

        # Update leaderboard & history
        guild_leaderboard[sender_id] = guild_leaderboard.get(sender_id, 0) + 1
        guild_leaderboard[target_id] = guild_leaderboard.get(target_id, 0) + 1

        guild_history.setdefault(sender_id, []).append((int(target_id), True, None))
        guild_history.setdefault(target_id, []).append((int(sender_id), True, None))

        save_all_data()
        await _send(source, f"💘 {sender.display_name} said YES to {target.display_name}! It's a match! 🧨", ephemeral=True)

    async def handle_date_reject(self, source, guild, receiver, sender, reason):
        guild_id = str(guild.id)
        sender_id = str(sender.id)
        receiver_id = str(receiver.id)

        guild_requests = date_requests.setdefault(guild_id, {})
        guild_leaderboard = leaderboard.setdefault(guild_id, {})
        guild_history = history.setdefault(guild_id, {})

        valid_requests = guild_requests.get(sender_id, [])
        if not any(tid == receiver_id for tid, _ in valid_requests):
            await _send(source, f"❌ No e-date request from {sender.display_name} to reject!")
            return

        # Remove rejected request
        guild_requests[sender_id] = [(tid, ts) for tid, ts in valid_requests if tid != receiver_id]

        # Update leaderboard & history
        guild_leaderboard[receiver_id] = guild_leaderboard.get(receiver_id, 0) + 1
        guild_history.setdefault(receiver_id, []).append((int(sender_id), False, reason))
        guild_history.setdefault(sender_id, []).append((int(receiver_id), False, f"Rejected by {receiver.display_name}: {reason}"))

        save_all_data()
        await _send(source, f"✅ Rejection recorded for {sender.display_name} 💔")

    async def handle_history_display(self, source, guild: discord.Guild, target: discord.Member):
        guild_id = str(guild.id)
        target_id = str(target.id)
        name = target.display_name

        guild_history = history.setdefault(guild_id, {})
        records = guild_history.get(target_id, [])

        if not records:
            embed = discord.Embed(title="📜 E-Date History",
                                  description=f"No e-date history found for {name}. 🕵️‍♀️",
                                  color=0xFFFACD)
            await _send(source, embed=embed)
            return

        heart = "💖"
        heartbreak = "💔"
        lines = []
        for uid, matched, reason in records:
            try:
                u = await self.bot.fetch_user(uid)
                uname = u.display_name
            except (discord.NotFound, discord.HTTPException):
                uname = f"<Unknown User {uid}>"

            if matched:
                lines.append(f"{heart} {uname}")
            else:
                lines.append(f"{heartbreak} {uname} — *{reason or 'No reason given'}*")


        # Paginate
        per_page = 10
        pages = []
        for i in range(0, len(lines), per_page):
            embed = discord.Embed(title=f"📜 E-Date History: {name}",
                                  description="\n".join(lines[i:i+per_page]),
                                  color=0xFFAACC)
            embed.set_footer(text=f"Total Records: {len(lines)}")
            pages.append(embed)

        paginator = PaginatedEmbed(pages)
        await _send(source, embed=pages[0], view=paginator)

    async def handle_leaderboard_display(self, source, guild: discord.Guild):
        guild_id = str(guild.id)
        guild_leaderboard = leaderboard.setdefault(guild_id, {})

        if not guild_leaderboard:
            embed = discord.Embed(
                title="📉 No leaderboard data yet!",
                description="🚀 Team Rocket’s E-Date is still *blasting off…* eventually.",
                color=0x87CEEB
            )
            await _send(source, embed=embed)
            return

        sorted_users = sorted(guild_leaderboard.items(), key=lambda item: item[1], reverse=True)
        guild_users = registered_users.setdefault(guild_id, {})
        lines = []

        for idx, (user_id, score) in enumerate(sorted_users, start=1):
            rank_tag = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
            member = guild.get_member(int(user_id)) or await self.bot.fetch_user(int(user_id))
            name = guild_users.get(user_id, {}).get("name") or get_display_name_fast(member, guild) if member else f"<User {user_id}>"
            lines.append(f"{rank_tag} {name}: **{score}** points")

        per_page = 10
        pages = []
        for i in range(0, len(lines), per_page):
            embed = discord.Embed(
                title=f"🏆 Rocket E-Date Leaderboard — {guild.name}",
                description="\n".join(lines[i:i+per_page]),
                color=0x87CEEB
            )
            embed.set_footer(text=f"Showing {i+1}-{min(i+per_page,len(lines))} of {len(lines)} contestants")
            pages.append(embed)

        paginator = PaginatedEmbed(pages)
        await _send(source, embed=pages[0], view=paginator)

    # ---------------- Commands ----------------
    @commands.group(name="tr", invoke_without_command=True)
    async def tr(self, ctx):
        await ctx.send("❌ Unknown subcommand. Try `.tr help` or `.tr date @user`.")

    @tr.command(name="reg")
    async def tr_reg(self, ctx: commands.Context):
        guild_id: str = str(ctx.guild.id)
        user_id: str = str(ctx.author.id)

        # Ensure we have a dictionary for this guild
        guild_users: Dict[str, Dict[str, str]] = registered_users.setdefault(guild_id, {})

        if user_id in guild_users:
            await ctx.send("🚫 Already registered in this server.")
            return

        # Add the user safely
        guild_users[user_id] = {
            "name": ctx.author.display_name,
            "gender": "?",
            "registered_at": str(get_today())
        }

        save_all_data()
        guild_name = "DMs" if ctx.guild is None else ctx.guild.name
        await ctx.send(f"✅ {ctx.author.mention} registered for Team Rocket E-Date in **{guild_name}**!")


    @tr.command(name="list")
    async def tr_list(self, ctx: commands.Context):
        guild_id: str = str(ctx.guild.id)
        guild_users: Dict[str, Dict[str, str]] = registered_users.get(guild_id, {})
        ids: List[str] = sorted(guild_users.keys(), key=int)
        thinking_msg = await ctx.send("⏳ Calculating contestants...")

        if not ids:
            embed = discord.Embed(title="🧨 No contestants yet!", color=0xFF66CC)
            await thinking_msg.edit(content=None, embed=embed)
            return

        per_page: int = 10
        pages: List[discord.Embed] = []

        for i in range(0, len(ids), per_page):
            chunk: List[str] = ids[i:i+per_page]
            lines: List[str] = []

            for idx, uid_str in enumerate(chunk):
                uid: int = int(uid_str)
                member: Optional[discord.Member] = ctx.guild.get_member(uid) if ctx.guild else None
                display_name: str = member.display_name if member else guild_users[uid_str]["name"]
                lines.append(f"`{i+idx+1}.` {display_name}")

            embed = discord.Embed(title="🚀 Contestants", description="\n".join(lines), color=0xFF66CC)
            pages.append(embed)

        view = PaginatedEmbed(pages)
        await thinking_msg.edit(content=None, embed=pages[0], view=view)
    

    @tr.command(name="date")
    async def tr_date(self, ctx, member: Optional[discord.Member] = None):
        await self.handle_rocket_date(ctx, ctx.author, member)

    @tr.command(name="dateyes")
    async def tr_date_yes(self, ctx, member: Optional[discord.Member] = None):
        await self.handle_rocket_date_yes(ctx, ctx.author, member)

    @tr.command(name="dateno")
    async def tr_date_no(self, ctx, member: Optional[discord.Member] = None, *, reason: str = "No reason provided"):
        if member is None:
            await ctx.send("❌ You must mention a user to reject a date request!")
            return
        await self.handle_date_reject(ctx, ctx.guild, ctx.author, member, reason)

    @tr.command(name="leaderboard")
    async def tr_leaderboard(self, ctx):
        await self.handle_leaderboard_display(ctx, ctx.guild)

    @tr.command(name="history")
    async def tr_history(self, ctx, member: Optional[discord.Member] = None):
        target = member or ctx.author
        await self.handle_history_display(ctx, ctx.guild, target)

    # ---------------- ROAST ----------------
    @tr.command(name="roast")
    async def roast(self, ctx, member: Optional[discord.Member] = None):
        if member is None:
            await ctx.send("🔥 Who’s the victim? Use .tr roast @someone to roast them Team Rocket style!")
            return
        if not self.roast_queue:
            self.roast_queue = self.roast_lines.copy()
            random.shuffle(self.roast_queue)
        template = self.roast_queue.pop()
        await ctx.send(template.format(author=ctx.author.mention, target=member.mention))

    # ---------------- SCREAM ----------------
    @tr.command(name="scream")
    async def scream(self, ctx, member: Optional[discord.Member] = None):
        if member is None:
            await ctx.send("📢 Who’s screaming? Tag the chaos! Usage: .tr scream @user")
            return
        available_templates = [line for line in self.scream_queue if line != self.last_scream_template]
        if not available_templates:
            self.scream_queue = self.scream_lines.copy()
            random.shuffle(self.scream_queue)
            available_templates = self.scream_queue.copy()
        chosen_template = random.choice(available_templates)
        self.last_scream_template = chosen_template
        self.scream_queue.remove(chosen_template)
        await ctx.send(chosen_template.format(author=ctx.author.mention, target=member.mention))

    # ---------------- DRAMA ----------------
    @tr.command(name="drama")
    async def drama(self, ctx, member: Optional[discord.Member] = None):
        if member is None:
            await ctx.send("🎭 Who’s stirring the drama? Tag someone! Usage: .tr drama @user")
            return
        available = [line for line in self.drama_queue if line != self.last_drama_template]
        if not available:
            self.drama_queue = self.drama_lines.copy()
            random.shuffle(self.drama_queue)
            available = self.drama_queue.copy()
        chosen = random.choice(available)
        self.last_drama_template = chosen
        self.drama_queue.remove(chosen)
        await ctx.send(chosen.format(author=ctx.author.mention, target=member.mention))

    # ---------------- THUNDERBOLT ----------------
    @tr.command(name="thunderbolt")
    async def tr_thunderbolt(self, ctx, member: Optional[discord.Member] = None):
        if member is None:
            await ctx.send("⚡ Who are we zapping? Mention someone! Example: .tr thunderbolt @user")
            return
        if member.id in PROTECTED_IDS:
            await ctx.send(random.choice(self.thunderbolt_protected_lines).format(
                target=member.mention, name=ctx.author.mention
            ))
            return
        if not self.thunderbolt_queue:
            self.thunderbolt_queue = self.thunderbolt_lines.copy()
            random.shuffle(self.thunderbolt_queue)
        template = self.thunderbolt_queue.pop()
        await ctx.send(template.format(author=ctx.author.mention, target=member.mention))

    # ---------------- SHOUTING SPRING ----------------
    @tr.command(name="ss")
    async def tr_shouting_spring(self, ctx: commands.Context, *, message: str = ""):
        if not message:
            await ctx.send("Meowth says: 'You need to shout something!' 😼")
            return

        meowth_quotes = ["Aww. M here for u 😿", "Cheer up! 😼", "Stay strong! <:emoji_2:1390365231175176344>"]
        jessie_quotes = ["Shine on ✨", "You got this 💪", "Don't quit <:emoji_8:1390365873717645393>"]
        james_quotes = ["Together strong 🚀", "No worries 🌈", "Keep going 💥"]

        # Count consecutive last characters
        last_char = message[-1]
        count = sum(1 for c in reversed(message) if c == last_char)
        height = count

        # Build the fountain lines
        fountain_lines = []
        for i in range(1, height + 1):
            line = "💦\u200B" * i
            if 2 <= i <= 3:
                line += f" — Meowth: {random.choice(meowth_quotes)}"
            elif 4 <= i <= 8:
                line += f" — Jessie: {random.choice(jessie_quotes)}"
            elif 9 <= i <= 12:
                line += f" — James: {random.choice(james_quotes)}"
            fountain_lines.append(line)

        # Send the start, fountain, and end messages
        start_msg = f"🚀 Team Rocket Shouting Spring 💦 activated! 🎶\nYou shouted {message}!"
        end_msg = '💫 Team Rocket says: "We hope this Shouting Spring 💦 lifts your spirits and mends your day!"'

        await ctx.send(start_msg)
        for line in fountain_lines:
            await ctx.send(line)
        await ctx.send(end_msg)

    # ---------------- FEEDBACK ----------------
    @tr.command(name="feedback")
    async def tr_feedback(self, ctx, *, message: str):
        # Only allow DMs
        if ctx.guild is not None:
            await ctx.send(
                "❌ The feedback command can only be used in private messages (DMs) with RocketBot."
            )
            try:
                await ctx.message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            return

        
        await ctx.send(f"📝 Thanks {ctx.author.mention}, your feedback has been sent to Team Rocket HQ!")

        for admin_id in ADMIN_IDS:
            admin = ctx.bot.get_user(admin_id)
            if admin:
                try:
                    await admin.send(
                        f"📩 **New Feedback Received!**\n"
                        f"👤 From: {ctx.author} ({ctx.author.id})\n"
                        f"💬 Message: {message}"
                    )
                except Exception as e:
                    print(f"Could not send feedback to {admin_id}: {e}")

    @tr.command(name="help", description="❓ Show Team Rocket Fun & Games Guide")
    async def rocket_help(self, ctx: commands.Context):
        help_data = load_json_file("json/help_text.json", {"title": "Help", "description": []})
        help_text = "\n".join(help_data.get("description", []))

        embed = discord.Embed(
            title=help_data.get("title", "Help"),
            description=help_text,
            color=0xFF99FF,
        )
        await ctx.send(embed=embed)



# ---------------- Setup Cog ----------------
async def setup(bot: commands.Bot):
    await bot.add_cog(RocketDate(bot))
