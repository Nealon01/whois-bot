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
| DISCORD_BOT_TOKEN           | The token used by the Discord bot to authenticate with Discord. |


## Using the Bot

The following commands are available.

| Command | Description                                                         |
|---------|---------------------------------------------------------------------|
| !help   | Shows a list of available commands                                  |
