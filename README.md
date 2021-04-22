# WhoIs Bot

## Overview

This repository contains source for WhoIS Bot, a Discord bot written in Python that provides server wide notes for users, to allow easier tracking of who a user is beyond changing nicknames/cryptic usernames.

## Running the Bot

The bot can be run in any Python environment ~, but this repository includes a Dockerfile to run the bot in a Docker container.~

~The Docker image is publish on [DockerHub](https://hub.docker.com/r/nealon/whois-bot).~

~If running locally, you must install the dependencies from `requirements.txt`, ideally in a virtual environment.~

The docker portion is not working.  If you have tips on how to dockerize this bot, I'm all ears.

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

## Using the Bot

The following commands are available.

| Command | Description                                                       |
|---------|-------------------------------------------------------------------|
| $help   | Shows a list of available commands                                |
| $list   | list all nicknames/notes                                          |
| $user "{nickname/username}"  | Shows the record for a specific user.        |
| $note "{nickname/username}" "{note}"   | Sets the note for the given user   |
