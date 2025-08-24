# helpers.py

import os
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps
from typing import Dict, List, Set, Tuple

import discord
from discord import ButtonStyle
from discord.ext import commands

# === Logger ===
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("TeamRocketBot")

# === Admin & Limits ===
PROTECTED_IDS: Set[int] = {688898170276675624, 409049845240692736, 416645930889117696}
ADMIN_IDS: Set[int] = PROTECTED_IDS.copy()
DATE_LIMIT_PER_DAY = 5
ADMIN_DATE_LIMIT_PER_DAY = 10

# === Files ===
CONTESTANTS_FILE = "json/rocket_contestants.json"
DATE_REQUESTS_FILE = "json/rocket_date_requests.json"
LEADERBOARD_FILE = "json/rocket_leaderboard.json"
HISTORY_FILE = "json/rocket_history.json"

# === Shared Data ===
registered_users: Dict[str, Dict[str, Dict[str, str]]] = {}
date_requests: Dict[str, Dict[str, List[Tuple[str, str]]]] = defaultdict(lambda: defaultdict(list))
leaderboard: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
history: Dict[str, Dict[str, List[Tuple[int, bool, str]]]] = defaultdict(lambda: defaultdict(list))

# === File Handling ===
def is_admin(user_or_id) -> bool:
    user_id = getattr(user_or_id, "id", user_or_id)
    return user_id in ADMIN_IDS


def load_json_file(filename: str, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json_file(filename: str, data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_data():
    global registered_users, date_requests, leaderboard, history

    # Load registered users
    registered_users_data = load_json_file(CONTESTANTS_FILE, {})
    registered_users.clear()
    registered_users.update({
        user_id: {
            "name": info.get("name", ""),
            "gender": info.get("gender", "?"),
            "registered_at": info.get("registered_at", str(get_today()))
        }
        for user_id, info in registered_users_data.items()
    })

    # Load date requests
    date_requests_data = load_json_file(DATE_REQUESTS_FILE, {})
    date_requests.clear()
    for guild_id, senders in date_requests_data.items():
        date_requests[guild_id] = defaultdict(list)
        for sender_id, requests in senders.items():
            date_requests[guild_id][sender_id] = requests

    # Load leaderboard
    leaderboard_data = load_json_file(LEADERBOARD_FILE, {})
    leaderboard.clear()
    for guild_id, scores in leaderboard_data.items():
        guild_board = leaderboard.setdefault(guild_id, defaultdict(int))
        guild_board.update({k: int(v) for k, v in scores.items()})

    # Load history
    history_data = load_json_file(HISTORY_FILE, {})
    history.clear()
    for guild_id, users in history_data.items():
        history[guild_id] = defaultdict(list)
        for user_id, recs in users.items():
            parsed: List[Tuple[int, bool, str]] = []
            for entry in recs:
                uid, matched, *rest = entry
                reason = str(rest[0]) if rest else ""
                parsed.append((int(uid), bool(matched), reason))
            history[guild_id][user_id] = parsed

    logger.info("Data loaded from JSON files.")


def save_all_data():
    today_str = str(get_today())
    registered_users_structured = {
        user_id: {
            "name": info.get("name", ""),
            "gender": info.get("gender", "?"),
            "registered_at": info.get("registered_at", today_str)
        }
        for user_id, info in registered_users.items()
    }
    save_json_file(CONTESTANTS_FILE, registered_users_structured)
    save_json_file(DATE_REQUESTS_FILE, date_requests)
    save_json_file(LEADERBOARD_FILE, leaderboard)

    history_serializable = {
        guild: {
            user: [
                [uid, matched, reason] if reason else [uid, matched]
                for uid, matched, reason in recs
            ]
            for user, recs in users.items()
        }
        for guild, users in history.items()
    }
    save_json_file(HISTORY_FILE, history_serializable)
    logger.info("Data saved to JSON files.")


# === Utility ===
def setup_prefix_error_handler(bot: commands.Bot | commands.Group):
    if isinstance(bot, commands.Bot):
        @bot.event
        async def on_command_error(ctx, error):
            if isinstance(error, commands.MemberNotFound):
                await ctx.send(
                    "⚠️ I couldn’t find that member. Maybe they left, or you tagged a role by mistake."
                )
            else:
                raise error


async def _send(
    source,
    content: str | None = None,
    embed: discord.Embed | None = None,
    view: discord.ui.View | None = None,
    ephemeral: bool = False,
):
    try:
        kwargs = {"content": content, "embed": embed, "view": view, "ephemeral": ephemeral}
        if isinstance(source, discord.Interaction):
            if source.response.is_done():
                await source.followup.send(**kwargs)
            else:
                await source.response.send_message(**kwargs)
        else:
            await source.send(content=content, embed=embed, view=view)
    except discord.Forbidden:
        fallback = content or "⚠️ I can't send messages here."
        try:
            if isinstance(source, discord.Interaction):
                if source.response.is_done():
                    await source.followup.send(content=fallback, ephemeral=True)
                else:
                    await source.response.send_message(content=fallback, ephemeral=True)
            else:
                await source.send(content=fallback)
        except Exception as e:
            logger.error(f"Failed fallback send: {e}")


def get_today():
    return datetime.now(timezone.utc).date()


def get_display_name_fast(user: discord.abc.User | discord.Member, guild: discord.Guild) -> str:
    member = guild.get_member(user.id)
    return member.display_name if member else user.name


def ensure_registered(func):
    @wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        if str(interaction.user.id) not in registered_users:
            await interaction.response.send_message(
                "🚀 You must `/rocket-register` before using this command!",
                ephemeral=True
            )
            return
        return await func(interaction, *args, **kwargs)
    return wrapper


def get_author_and_guild(source):
    if isinstance(source, discord.Interaction):
        return source.user, source.guild
    return source.author, source.guild


# === UI ===
class PaginatedEmbed(discord.ui.View):

    def __init__(self, pages: List[discord.Embed]):
        super().__init__(timeout=None)
        self.pages = pages
        self.index = 0

        self.prev_button = discord.ui.Button(label="◀️", style=ButtonStyle.secondary)
        self.next_button = discord.ui.Button(label="▶️", style=ButtonStyle.secondary)
        self.prev_button.callback = self.go_previous
        self.next_button.callback = self.go_next
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

    async def go_previous(self, interaction: discord.Interaction):
        self.index = (self.index - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    async def go_next(self, interaction: discord.Interaction):
        self.index = (self.index + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)
