# rocket_pokemon_game.py
import discord
from discord.ext import commands
import asyncio
import random
from helpers import load_json_file, save_json_file


class RocketPokemon(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.POKEMON_LIST = load_json_file("json/rocket_pokemon_list.json", [])
        self.OWNERS_FILE = "json/rocket_pokemon_owners.json"

    def load_owners(self):
        return load_json_file(self.OWNERS_FILE, {})

    def save_owners(self, data):
        save_json_file(self.OWNERS_FILE, data)

    @commands.group(name="poke", invoke_without_command=True)
    async def poke(self, ctx):
        await ctx.send("❌ Unknown subcommand. Try `.poke help` or `.poke catch`.")

    # ---------------- Commands ----------------
    @poke.command(name="catch")
    async def tr_catch(self, ctx):
        owners = self.load_owners()
        user_id = str(ctx.author.id)

        if user_id in owners:
            await ctx.send(f"{ctx.author.mention}, you already have a Pokémon! ❌")
            return

        if not self.POKEMON_LIST:
            await ctx.send("⚠️ No Pokémon are available to catch. Try again later.")
            return

        searching_msgs = [
            "🚀 Rocketbot is looking for a Pokémon in the forest... 🌳",
            "🚀 Rocketbot is searching the cave for a Pokémon... 🪨",
            "🚀 Rocketbot is sneaking in the tall grass... 🌿"
        ]
        await ctx.send(random.choice(searching_msgs))
        await asyncio.sleep(2)

        chosen = random.choice(self.POKEMON_LIST)
        owners[user_id] = {
            "rocket_pokemon": chosen["id"],
            "name": "UNKNOWN",
            "level": 1,
            "walks": 0,
            "feeds": 0,
            "battle": {"win": 0, "loss": 0},
            "asset": chosen["asset"]["main"],
            "evolution_asset": chosen["asset"]["evolution"]
        }
        self.save_owners(owners)

        file = discord.File(chosen["asset"]["main"], filename="pokemon.gif")
        await ctx.send(
            f"🎉 {ctx.author.mention}, you found **{chosen['name']}**!\nType `.poke name <nickname>` to give your Pokémon a name.",
            file=file
        )

    @poke.command(name="name")
    async def tr_name(self, ctx, *, nickname: str = None):
        owners = self.load_owners()
        user_id = str(ctx.author.id)

        if user_id not in owners:
            await ctx.send("❌ You don’t have a Pokémon yet! Use `.poke catch` first.")
            return
        if not nickname:
            await ctx.send("❌ You need to provide a nickname!")
            return

        owners[user_id]["name"] = nickname
        self.save_owners(owners)
        await ctx.send(f"✅ Your Pokémon is now named **{nickname}**!")

    @poke.command(name="show")
    async def tr_show(self, ctx):
        owners = self.load_owners()
        user_id = str(ctx.author.id)

        if user_id not in owners:
            await ctx.send("❌ You don’t have a Pokémon yet! Use `.poke catch` first.")
            return

        p = owners[user_id]
        pokemon = next(
            (pkm for pkm in self.POKEMON_LIST if pkm["id"] == p["rocket_pokemon"]),
            None
        )
        if not pokemon:
            await ctx.send("⚠️ Pokémon data missing.")
            return

        name_display = p["name"] if p["name"] != "UNKNOWN" else "UNKNOWN ❓ (your Pokémon wants a name!)"

        # Compute average completion for level
        walk_pct = min(p.get("walks", 0), 5) / 5
        feed_pct = min(p.get("feeds", 0), 5) / 5
        battle_pct = min(p.get("battle", {}).get("win", 0), 5) / 5
        avg_pct = (walk_pct + feed_pct + battle_pct) / 3
        level = max(1, min(5, round(avg_pct * 5)))
        p["level"] = level
        self.save_owners(owners)

        # Use evolution asset if level 5
        asset_file = p["evolution_asset"] if level == 5 else p["asset"]
        file_name = "evo.gif" if level == 5 else "pokemon.gif"
        file = discord.File(asset_file, filename=file_name)

        await ctx.send(
            f"**{name_display}**\n"
            f"📈 Level: {level}\n"
            f"🚶 Walks: {p.get('walks',0)}/5\n"
            f"🍓 Feeds: {p.get('feeds',0)}/5\n"
            f"⚔️ Wins: {p.get('battle', {}).get('win',0)}/5 | ❌ Loss: {p.get('battle', {}).get('loss',0)}",
            file=file
        )

    @poke.command(name="walk")
    async def tr_walk(self, ctx):
        owners = self.load_owners()
        user_id = str(ctx.author.id)

        if user_id not in owners:
            await ctx.send("❌ You don’t have a Pokémon yet! Use `.poke catch` first.")
            return

        p = owners[user_id]
        pokemon = next(
            (pkm for pkm in self.POKEMON_LIST if pkm["id"] == p["rocket_pokemon"]),
            None
        )
        if not pokemon:
            await ctx.send("⚠️ Pokémon data missing.")
            return

        p["walks"] = p.get("walks", 0) + 1
        self.save_owners(owners)

        display_name = p["name"] if p["name"] != "UNKNOWN" else pokemon["name"]

        embed = discord.Embed(title=f"🚶 Walking with {display_name}", description="", color=discord.Color.green())
        file = discord.File(pokemon["asset"]["walking"], filename="walk.gif")
        embed.set_image(url="attachment://walk.gif")

        msg = await ctx.send(file=file, embed=embed)

        # Slowly add footsteps
        for _ in range(3):
            await asyncio.sleep(1.5)
            embed.description += "👣\n"
            await msg.edit(embed=embed)

        await asyncio.sleep(1.5)
        embed.description += f"\nWalks: **{p['walks']}/5**"
        await msg.edit(embed=embed)

    @poke.command(name="battle")
    async def tr_battle(self, ctx):
        owners = self.load_owners()
        user_id = str(ctx.author.id)

        if user_id not in owners:
            await ctx.send("❌ You don’t have a Pokémon yet! Use `.poke catch` first.")
            return

        p = owners[user_id]
        pokemon = next(
            (pkm for pkm in self.POKEMON_LIST if pkm["id"] == p["rocket_pokemon"]),
            None
        )
        if not pokemon:
            await ctx.send("⚠️ Pokémon data missing.")
            return

        result = random.choice(["win", "loss"])
        p["battle"][result] = p["battle"].get(result, 0) + 1
        self.save_owners(owners)

        display_name = p["name"] if p["name"] != "UNKNOWN" else pokemon["name"]

        embed = discord.Embed(title=f"⚔️ {display_name} enters battle!", description="battling.....\n💥", color=discord.Color.red())
        file = discord.File(pokemon["asset"]["battling"], filename="battle.gif")
        embed.set_image(url="attachment://battle.gif")

        message = await ctx.send(file=file, embed=embed)
        await asyncio.sleep(2)
        embed.description = "battling.....\n💥\n💥 boom!"
        await message.edit(embed=embed)

        await asyncio.sleep(2)
        outcome_text = "🏆 Congrats! You won!" if result == "win" else "💀 Oh no! You lost!"
        embed.description = f"battling.....\n💥\n💥 boom!\n💥 boggsh!!\n{outcome_text}\n\nWins: **{p['battle']['win']}/5** | Losses: **{p['battle']['loss']}**"
        await message.edit(embed=embed)

    @poke.command(name="feed")
    async def tr_feed(self, ctx):
        owners = self.load_owners()
        user_id = str(ctx.author.id)

        if user_id not in owners:
            await ctx.send("❌ You don’t have a Pokémon yet! Use `.poke catch` first.")
            return

        p = owners[user_id]
        pokemon = next(
            (pkm for pkm in self.POKEMON_LIST if pkm["id"] == p["rocket_pokemon"]),
            None
        )
        if not pokemon:
            await ctx.send("⚠️ Pokémon data missing.")
            return

        p["feeds"] = p.get("feeds", 0) + 1
        self.save_owners(owners)

        display_name = p["name"] if p["name"] != "UNKNOWN" else pokemon["name"]

        embed = discord.Embed(
            title="🍴 Feeding Time!",
            description=f"You are feeding your Pokémon pet **{display_name}** 💙",
            color=discord.Color.blue()
        )
        file = discord.File(pokemon["asset"]["feeding"], filename="feed.gif")
        embed.set_image(url="attachment://feed.gif")

        msg = await ctx.send(file=file, embed=embed)
        for _ in range(3):
            await asyncio.sleep(1.5)
            embed.description += f"\nnom..."
            await msg.edit(embed=embed)

        await asyncio.sleep(1.5)
        embed.description += f"\n{display_name} is now full 💤\nFeed: **{p['feeds']}/5**"
        await msg.edit(embed=embed)


# ---------------- Setup Cog ----------------
async def setup(bot):
    await bot.add_cog(RocketPokemon(bot))
