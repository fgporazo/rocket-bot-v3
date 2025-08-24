import discord
from discord.ext import commands
import random
import os
import asyncio
from helpers import load_json_file

# Admin IDs
ADMIN_IDS = [688898170276675624, 409049845240692736, 416645930889117696]

# Track ongoing dates per guild
ongoing_dates = {}  # {guild_id: [user_id, ...]}


class DateView(discord.ui.View):
    def __init__(self,
                 author: discord.Member,
                 date: discord.Member,
                 compliments: list,
                 timeout: int = 60):
        super().__init__(timeout=timeout)
        self.author = author
        self.date = date
        self.active = True
        self.current_turn = "first"  # "first" or "last"
        self.compliments = compliments
        self.turn_images = []

        # folders
        self.whiteboard_folder = "assets/drawing/whiteboard"
        self.gender_folders = {
            "male": "assets/drawing/male",
            "female": "assets/drawing/female"
        }

        # message reference
        self.message: discord.Message | None = None

        # Initialize buttons for first turn only
        self.clear_items()
        self.add_item(self.FirstDoneButton(self))

    async def on_timeout(self):
        if not self.active:
            return
        self.active = False
        self.clear_items()
        if self.message:
            await self.message.edit(
                content="⌛ The date ended due to inactivity!", view=self)

        guild_id = self.message.guild.id if self.message else None
        if guild_id and guild_id in ongoing_dates:
            for user_id in [self.author.id, self.date.id]:
                if user_id in ongoing_dates[guild_id]:
                    ongoing_dates[guild_id].remove(user_id)

    async def show_whiteboard(self, member: discord.Member, target: discord.Member):
        whiteboards = [
            f for f in os.listdir(self.whiteboard_folder)
            if f.lower().endswith((".gif", ".png"))
        ]
        if not whiteboards:
            if self.message:
                await self.message.channel.send("❌ No whiteboard assets found!")
            return
        chosen = random.choice(whiteboards)
        path = os.path.join(self.whiteboard_folder, chosen)

        embed = discord.Embed(
            title=f"🎨 {member.display_name} is drawing {target.display_name}...",
            description="Click the button when you finish your drawing!",
            color=discord.Color.purple())
        embed.set_image(url=f"attachment://{chosen}")
        file = discord.File(path, filename=chosen)
        if self.message:
            await self.message.edit(embed=embed, attachments=[file])

    async def show_result_image(self, member: discord.Member, turn: str):
        folder = self.gender_folders["male"] if turn == "first" else self.gender_folders["female"]
        images = [
            f for f in os.listdir(folder)
            if f.lower().endswith(("webp", ".jpg", ".png", ".gif", ".jpeg", ".avif"))
        ]
        if not images:
            if self.message:
                await self.message.channel.send(f"❌ No images found in {folder}")
            self.turn_images.append((member.display_name, None, folder))
            return

        chosen = random.choice(images)
        self.turn_images.append((member.display_name, chosen, folder))
        path = os.path.join(folder, chosen)

        embed = discord.Embed(
            title=f"🎨 {member.display_name}'s drawing result!",
            color=discord.Color.green())
        embed.set_image(url=f"attachment://{chosen}")
        file = discord.File(path, filename=chosen)
        if self.message:
            await self.message.edit(embed=embed, attachments=[file])

    async def show_final_result(self):
        embed = discord.Embed(
            title="💖 Team Rocket Drawing Date Result!",
            description="The results are in! Check out your amazing drawings below:",
            color=discord.Color.gold())
        files = []
        for name, fname, folder in self.turn_images:
            if fname is None:
                continue
            compliment = random.choice(
                self.compliments) if self.compliments else "You look amazing together! 💖"
            embed.add_field(name=f"{name}'s Drawing",
                            value=compliment,
                            inline=True)
            files.append(discord.File(os.path.join(folder, fname), filename=fname))

        if self.message:
            await self.message.edit(embed=embed, attachments=files)

        # Remove players from ongoing_dates
        guild_id = self.message.guild.id if self.message else None
        if guild_id and guild_id in ongoing_dates:
            for user_id in [self.author.id, self.date.id]:
                if user_id in ongoing_dates[guild_id]:
                    ongoing_dates[guild_id].remove(user_id)
        self.active = False
        self.stop()

    # ------------------ BUTTONS ------------------
    class FirstDoneButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(label="I'm done ❤️", style=discord.ButtonStyle.success)
            self.parent_view = view

        async def callback(self, interaction: discord.Interaction):
            view = self.parent_view
            if not view.active or view.current_turn != "first":
                await interaction.response.send_message(
                    "❌ It's not your turn or the game ended!", ephemeral=True)
                return
            if interaction.user != view.author:
                await interaction.response.send_message(
                    "❌ Only the first player can click this!", ephemeral=True)
                return

            self.disabled = True
            await interaction.response.defer()
            if view.message:
                await view.message.edit(view=view)

            await view.show_result_image(view.author, "first")

            view.current_turn = "last"
            await asyncio.sleep(1)
            await view.show_whiteboard(view.date, view.author)

            view.clear_items()
            view.add_item(view.LastDoneButton(view))
            if view.message:
                await view.message.edit(view=view)

    class LastDoneButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(label="I'm done too 💖", style=discord.ButtonStyle.success)
            self.parent_view = view

        async def callback(self, interaction: discord.Interaction):
            view = self.parent_view
            if not view.active or view.current_turn != "last":
                await interaction.response.send_message(
                    "❌ It's not your turn or the game ended!", ephemeral=True)
                return
            if interaction.user != view.date:
                await interaction.response.send_message(
                    "❌ Only the second player can click this!", ephemeral=True)
                return

            self.disabled = True
            await interaction.response.defer()
            if view.message:
                await view.message.edit(view=view)

            await view.show_result_image(view.date, "last")
            await asyncio.sleep(3)
            await view.show_final_result()


class RocketDrawingDate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.compliments = load_json_file("json/rocket_drawing_compliments.json", {})
        if "compliments" not in self.compliments:
            self.compliments["compliments"] = []

    @commands.command(name="dd")
    async def dd(self, ctx, *, member_arg: str = None):
        author = ctx.author
        guild = ctx.guild
        guild_id = guild.id

        # Resolve member if provided
        member = None
        if member_arg:
            try:
                member = await commands.MemberConverter().convert(ctx, member_arg)
            except commands.MemberNotFound:
                # Friendly message
                return await ctx.send(
                    "❌ Please mention who you want to go on a drawing date with! Example: `.dd @username`"
                )

        # If no member provided
        if member is None:
            return await ctx.send(
                "❌ Please mention who you want to go on a drawing date with! Example: `.dd @username`"
            )

        # Prevent self-dating for non-admins
        if author.id not in ADMIN_IDS and member.id == author.id:
            return await ctx.send("❌ You cannot date yourself!")

        # Check ongoing dates
        ongoing = ongoing_dates.get(guild_id, [])
        if author.id in ongoing or member.id in ongoing:
            return await ctx.send(
                "❌ One of you already has an ongoing drawing date! Finish it before starting a new one."
            )

        # Mark both users as in an ongoing date
        ongoing_dates.setdefault(guild_id, []).extend([author.id, member.id])

        embed = discord.Embed(
            title="🎨 Team Rocket Drawing Date",
            description=(f"{author.mention} started a drawing date with {member.mention}!\n\n"
                         f"It's {author.mention}'s turn!"),
            color=discord.Color.pink()
        )

        view = DateView(author, member, self.compliments.get("compliments", []), timeout=60)
        message = await ctx.send(embed=embed, view=view)
        view.message = message

        # Show first turn whiteboard
        await view.show_whiteboard(author, member)


async def setup(bot):
    await bot.add_cog(RocketDrawingDate(bot))
