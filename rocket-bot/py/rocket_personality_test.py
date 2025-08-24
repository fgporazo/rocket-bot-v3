import discord
from discord.ext import commands
import asyncio
import random
import json
import os


def load_json_file(file_path, default=None):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default or []


PERSONALITY_TESTS = load_json_file("json/rocket_personality_test.json", [])


class PersonalityTest(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.active_tests = {}  # thread.id -> test state
        self.user_test_history = {}  # user.id -> set of completed test titles
        self.thread_owners = {}  # thread.id -> user.id of participant

    @commands.group(name="pt", invoke_without_command=True)
    async def pt(self, ctx):
        await ctx.send("🚀 Use `.pt start` to begin a personality test!")

    @pt.command(name="start")
    async def pt_start(self, ctx):
        if not PERSONALITY_TESTS:
            await ctx.send("⚠️ No personality tests found!")
            return

        user_id = ctx.author.id
        completed = self.user_test_history.get(user_id, set())
        available_tests = [
            t for t in PERSONALITY_TESTS if t["title"] not in completed
        ]

        if not available_tests:
            # All tests completed, reset history
            completed = set()
            available_tests = PERSONALITY_TESTS.copy()
            await ctx.send(
                "🎉 You’ve completed all personality tests! Starting over..."
            )

        # Pick a random test from remaining
        test = random.choice(available_tests)
        self.user_test_history[user_id] = completed | {test["title"]}

        # Determine the thread to use
        if isinstance(ctx.channel, discord.Thread):
            thread = ctx.channel
            # Check if a test is already active in this thread
            if thread.id in self.active_tests and self.active_tests[thread.id]["active"]:
                await ctx.send("⚠️ A personality test is already running in this thread!")
                return
        else:
            # Check if a test is already running in this channel
            existing = [
                g for g in self.active_tests.values()
                if g["parent_channel_id"] == ctx.channel.id and g["active"]
            ]
            if existing:
                await ctx.send("⚠️ A personality test is already running here!")
                return
            # Create a new thread
            thread = await ctx.channel.create_thread(
                name=f"👤 Personality Test: {test['title']}",
                type=discord.ChannelType.public_thread
            )

        # Remember the owner of the thread/test
        self.thread_owners[thread.id] = user_id

        # Set up test state
        state = {
            "test": test,
            "step_index": 0,
            "points": {},
            "thread": thread,
            "parent_channel_id": ctx.channel.id,
            "active": True,
            "current_message": None,
            "timeout_task": None
        }
        self.active_tests[thread.id] = state

        embed = discord.Embed(
            title=f"🚀 {test['title']}",
            description=test["description"],
            color=discord.Color.purple()
        )
        await thread.send(embed=embed)
        await asyncio.sleep(1)
        await self.run_step(thread.id)

    async def run_step(self, thread_id):
        state = self.active_tests.get(thread_id)
        if not state or not state["active"]:
            return

        test = state["test"]
        thread = state["thread"]
        step_index = state["step_index"]

        if step_index >= len(test["steps"]):
            await self.show_result(thread_id)
            return

        step = test["steps"][step_index]

        # Build embed with choices
        embed = discord.Embed(title=f"Step {step_index+1}",
                              description=step["text"],
                              color=discord.Color.blurple())
        view = discord.ui.View(timeout=60)  # 1 minute inactivity timeout

        user_id = self.thread_owners.get(thread_id)

        # Add buttons for each choice
        for choice in step.get("choices", []):

            async def button_callback(interaction, choice=choice):
                # Only the test participant can click
                if interaction.user.id != user_id:
                    await interaction.response.send_message(
                        "❌ You cannot choose for someone else!", ephemeral=True
                    )
                    return

                # Update points
                for k, v in choice["points"].items():
                    state["points"][k] = state["points"].get(k, 0) + v

                # Cancel timeout task
                if state["timeout_task"]:
                    state["timeout_task"].cancel()
                    state["timeout_task"] = None

                # Disable buttons after click
                if state["current_message"]:
                    await state["current_message"].edit(view=None)

                # Publicly announce choice
                await thread.send(f"✅ {interaction.user.mention} chose: {choice['label']}")

                # Move to next step
                state["step_index"] += 1
                await self.run_step(thread_id)

            btn = discord.ui.Button(label=choice["label"],
                                    style=discord.ButtonStyle.primary)
            btn.callback = button_callback
            view.add_item(btn)

        state["current_message"] = await thread.send(embed=embed, view=view)

        async def timeout_task():
            await asyncio.sleep(60)
            if state["active"]:
                await thread.send("⏱️ Test ended due to inactivity!")
                await self.show_result(thread_id, finished=False)

        state["timeout_task"] = asyncio.create_task(timeout_task())

    async def show_result(self, thread_id, finished=True):
        state = self.active_tests.get(thread_id)
        if not state:
            return

        test = state["test"]
        thread = state["thread"]
        state["active"] = False

        if state["points"]:
            personality = max(state["points"],
                              key=lambda k: state["points"][k])
            description = test["final_result"].get(personality,
                                                   "No result found.")
        else:
            personality = "No Answer"
            description = "You didn’t complete the test."

        embed = discord.Embed(
            title=f"🚀 Personality Test Result: {test['title']}",
            description=f"**{personality}**\n{description}",
            color=discord.Color.green())
        if not finished:
            embed.set_footer(text="Test ended due to inactivity ⏱️")

        await thread.send(embed=embed)

        # Clean up
        if thread.id in self.active_tests:
            del self.active_tests[thread_id]
        if thread.id in self.thread_owners:
            del self.thread_owners[thread_id]


async def setup(bot):
    await bot.add_cog(PersonalityTest(bot))
