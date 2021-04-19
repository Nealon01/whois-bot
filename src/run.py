#!/usr/bin/env python
import os
import discord
from discord.ext import commands

from whois_bot import UserCommands

DISCORD_TOKEN = 'DISCORD_TOKEN'
DISCORD_GUILD = 'DISCORD_GUILD'
DICT_PATH = 'DICT_PATH'


def main():
    """The main entry point for the whois bot program."""
    discord_token = get_env_or_error(DISCORD_TOKEN)
    discord_guild = get_env_or_error(DISCORD_GUILD)
    dict_path = get_env_or_error(DICT_PATH)

    UserCommands.initialize(DISCORD_GUILD, DICT_PATH)

    intents = discord.Intents.default()
    intents.members = True

    bot = commands.Bot(command_prefix='$', intents=intents)
    bot.run(discord_bot_token)


def get_env_or_error(env_var):
    """
    Retrieves an environment variable and returns it, or exits the application if it is not found.

    Parameters
    ----------

    env_var:
        The name of the environment variable to get.
    """
    var = os.environ.get(env_var)
    if var is None or var == '':
        print(f'Missing required environment variable: {env_var}')
        exit(1)
    else:
        print(f'Environment variable {env_var} = {var}')
    return var


if __name__ == '__main__':
    main()
