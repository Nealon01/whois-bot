# 3.12 (not 3.9.1): discord.py 2.x hits a typing bug on 3.9.0/3.9.1
FROM python:3.12-slim
WORKDIR /app

ENV DISCORD_TOKEN="" \
    DISCORD_GUILD="" \
    DISCORD_ROLE="" \
    DICT_PATH="" \
    CONFIG_PATH=""

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt && \
    rm requirements.txt

RUN mkdir -p /config/

COPY src/*.py ./
# -u: unbuffered stdout so docker logs shows output immediately
ENTRYPOINT ["python", "-u", "./whois_bot.py"]
