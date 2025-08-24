import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from helpers import load_json_file, is_admin

# Map JSON style strings to Discord ButtonStyle
STYLE_MAP = {
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
    "primary": discord.ButtonStyle.primary
}


class CommandButton(Button):
    def __init__(self, label: str, command: str, style: discord.ButtonStyle, thread_id: str = None, channel_id: str = None):
        super().__init__(label=label, style=style, custom_id=f"btn_{label}")
        self.command = command
        self.thread_id = thread_id
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        bot = self.view._bot

        # Special case: DM Rocket Bot
        if self.command.lower() == "dm_bot":
            try:
                await interaction.user.send("🚀 Team Rocket says Hi! Send us your thoughts by typing **.tr feedback <message>** right here.")
                await interaction.response.send_message("✅ Check your DMs!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ I couldn't DM you. Please enable DMs.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Determine target channel/thread
        target_channel = None
        thread_jump_url = None

        try:
            if self.thread_id:
                target_channel = await bot.fetch_channel(int(self.thread_id))
                thread_jump_url = target_channel.jump_url
            elif self.channel_id:
                target_channel = await bot.fetch_channel(int(self.channel_id))
            else:
                target_channel = interaction.channel
        except Exception:
            target_channel = interaction.channel

        # Create temporary message to build context for invocation
        fake_msg = await target_channel.send(f"🚀 Executing `{self.command}` for {interaction.user.display_name}...")
        ctx = await bot.get_context(fake_msg)
        ctx.author = interaction.user
        ctx.message.author = interaction.user
        ctx.command = bot.get_command(self.command.lstrip("."))

        if ctx.command is None:
            await fake_msg.delete()
            await interaction.followup.send(f"❌ Command `{self.command}` not found.", ephemeral=True)
            return

        # Invoke command
        await bot.invoke(ctx)

        # Delete temporary message
        await fake_msg.delete()

        # Notify user
        msg_info = "✅ Go to"
        if thread_jump_url and target_channel and not isinstance(target_channel, discord.DMChannel):
            msg_info += f" [**{target_channel.name}**]({thread_jump_url})"
        await interaction.followup.send(msg_info, ephemeral=True)



class RocketListView(View):
    def __init__(self, bot: commands.Bot, section: dict):
        super().__init__(timeout=None)
        self._bot = bot

        style_str = section.get("button_style", "success").lower()
        if style_str == "secondary" or style_str not in STYLE_MAP:
            style_str = "success"
        style = STYLE_MAP[style_str]

        for button in section.get("buttons", []):
            label = button.get("label", "Unnamed")
            command = button.get("command", "")
            thread_id = button.get("thread_id")
            channel_id = button.get("channel_id")
            self.add_item(CommandButton(label, command, style=style, thread_id=thread_id, channel_id=channel_id))


class RocketSlash(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        base_dir = os.path.dirname(os.path.abspath(__file__))
        help_file = os.path.join(base_dir, "json", "help_text.json")
        self.HELP_DATA = load_json_file(help_file, {"title": "Help", "description": []})

    @app_commands.command(name="rocket-list", description="Show Rocket Bot menu (Admins only).")
    async def rocket_list(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)

        data = load_json_file("json/rocket_bot.json", default={})
        sections = data.get("sections", [])
        if not sections:
            sections = [{"title": "🚀 Rocket Bot", "description": "Welcome to Rocket Bot!", "buttons": []}]

        # First section
        first_section = sections[0]
        embed = discord.Embed(
            title=first_section.get("title", "🚀 Rocket Bot"),
            description=first_section.get("description", "Welcome to Rocket Bot!"),
            color=discord.Color.blurple()
        )
        view = RocketListView(self.bot, first_section)
        await interaction.response.send_message(embed=embed, view=view)

        # Remaining sections
        for section in sections[1:]:
            embed = discord.Embed(
                title=section.get("title", "🚀 Rocket Bot"),
                description=section.get("description", "Welcome to Rocket Bot!"),
                color=discord.Color.blurple()
            )
            view = RocketListView(self.bot, section)
            await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="rocket-members", description="👥 View Team Rocket Admin")
    async def rocket_members(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Team Rocket Admin",
            description="Meet the chaos crew behind the scenes! 💥",
            color=0xFFFACD,
        )
        embed.add_field(name="1️⃣ Jessie (Cin)", value="💄 Queen of Chaotic Capers", inline=False)
        embed.add_field(name="2️⃣ James (Layli)", value="🌻 Chaos Catalyst of Digital", inline=False)
        embed.add_field(name="3️⃣ Meowth (Joa)", value="😼 Official Translator & Mischief Manager", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rocket-help", description="❓ Show Team Rocket Fun & Games Guide")
    async def rocket_help(self, interaction: discord.Interaction):
        help_data = load_json_file("json/help_text.json", {"title": "Help", "description": []})
        help_text = "\n".join(help_data.get("description", []))
        embed = discord.Embed(
            title=help_data.get("title", "Help"),
            description=help_text,
            color=0xFF99FF,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RocketSlash(bot))
