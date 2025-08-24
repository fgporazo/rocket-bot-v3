# py/rocket_thread_restriction.py
import json
import os

JSON_PATH = "json/rocket_thread_restriction.json"

def load_restrictions():
    """Load thread restriction data from JSON."""
    if not os.path.exists(JSON_PATH):
        return {}
    with open(JSON_PATH, "r") as f:
        return json.load(f)

def save_restrictions(data):
    """Save thread restriction data to JSON."""
    with open(JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)

def global_thread_check(message):
    """
    Block any command not in the allowed prefixes for this thread.
    Returns a tuple: (allowed: bool, allowed_prefixes: list[str])
    """
    if not message.content.startswith("."):
        return True, []  # Not a command, allow

    channel_id = str(message.channel.id)
    data = load_restrictions()
    allowed_prefixes = data.get(channel_id, [])

    # No restrictions for this thread
    if not allowed_prefixes:
        return True, []

    # Extract first word after the dot
    invoked = message.content.split()[0][1:].lower()

    # Allow exact match or subcommand of allowed prefixes
    for prefix in allowed_prefixes:
        prefix_lower = prefix.lower()
        if invoked == prefix_lower or invoked.startswith(f"{prefix_lower} "):
            return True, allowed_prefixes

    return False, allowed_prefixes
