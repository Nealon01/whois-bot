FROM python:3.9.1-slim-buster
WORKDIR /app

ENV DISCORD_TOKEN="" \
    DISCORD_GUILD="" \
    DISCORD_ROLE="" \
    DICT_PATH=""

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt && \
    rm requirements.txt

RUN mkdir -p /config/

COPY src/*.py ./
ENTRYPOINT ["python", "./whois_bot.py"]
