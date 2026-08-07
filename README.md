# WhoIs Bot

## Overview

This repository contains source for WhoIS Bot, a Discord bot written in Python that provides server wide notes for users, to allow easier tracking of who a user is beyond changing nicknames/cryptic usernames.

## Running the Bot

The bot can be run in any Python environment, but this repository includes a Dockerfile to run the bot in a Docker container.

The Docker image is publish on [DockerHub](https://hub.docker.com/r/nealon/whois-bot).

If running locally, you must install the dependencies from `requirements.txt`, ideally in a virtual environment.

```shell
$ python -m venv env
$ source env/bin/activate
$ pip install -r requirements.txt
```

The bot requires the following environment variables to function. These are required in both the local and Docker environments.

| Variable                    | Description                                                     |
|-----------------------------|-----------------------------------------------------------------|
| DISCORD_TOKEN           | The token used by the Discord bot to authenticate with Discord. |
| DISCORD_GUILD           | The name of the discord server you want to monitor |
| DISCORD_ROLE           | The name of the role to use for users to monitor (allows skipping bots/other) |
| DICT_PATH           | The path to store the pickled dictionary for persistent notes. |
| CONFIG_PATH           | *(optional)* Path to the JSON file with per-server settings (defaults to `guild_config.json` next to `DICT_PATH`). |

## Using the Bot

The following commands are available.

| Command | Description                                                       |
|---------|-------------------------------------------------------------------|
| $help   | Shows a list of available commands                                |
| $list   | list all nicknames/notes                                          |
| $user "{nickname/username}"  | Shows the record for a specific user.        |
| $note "{nickname/username}" "{note}"   | Sets the note for the given user   |
| $setchannel #channel   | *(admins)* Sets the channel where nickname changes are announced. |
| $unsetchannel   | *(admins)* Disables nickname change announcements for this server. |

## Nickname Change Announcements

Whenever a tracked user (with `DISCORD_ROLE`) changes their nickname, the bot posts a message to the server's announcement channel, including a short reminder of the basic commands.

Which channel receives announcements, in priority order:

1. The channel set per-server with `$setchannel #channel` (requires *Manage Server* permission).
2. A text channel literally named `voice-chat-sharing` (case-insensitive) — this gives you sensible default behavior with zero configuration.
3. No channel → announcements stay disabled and the bot logs a hint to run `$setchannel`.

Per-server settings live in the JSON file at `CONFIG_PATH` (defaults to `guild_config.json` next to `DICT_PATH`).
