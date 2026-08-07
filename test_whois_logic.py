"""Tests for the pure logic in whois_bot.py — run without a real discord library.

Usage: python3 test_whois_logic.py
"""
import json
import os
import sys
import tempfile
import types

# --- Stub discord modules so whois_bot.py can be imported without discord.py ---
dotenv = types.ModuleType('dotenv')
dotenv.load_dotenv = lambda *a, **k: None
sys.modules['dotenv'] = dotenv

discord = types.ModuleType('discord')
discord_ext = types.ModuleType('discord.ext')
discord_ext_commands = types.ModuleType('discord.ext.commands')

class _FakeIntents:
    def __init__(self):
        self.members = False
    @staticmethod
    def default():
        return _FakeIntents()

class _FakeBot:
    def __init__(self, *args, **kwargs):
        self.guilds = []
    def change_presence(self, activity=None):
        pass
    def run(self, token):
        raise AssertionError('bot.run should never be called during import')
    def event(self, coro=None):
        def decorator(fn):
            return fn
        return decorator(coro) if coro else decorator

class _FakeActivity:
    def __init__(self, name=None, type=None):
        self.name = name
        self.type = type

discord.Intents = _FakeIntents
discord.Activity = _FakeActivity
discord.ActivityType = types.SimpleNamespace(watching='watching')
discord.ext = discord_ext
discord.ext.commands = discord_ext_commands
discord_ext_commands.Bot = _FakeBot

sys.modules['discord'] = discord
sys.modules['discord.ext'] = discord_ext
sys.modules['discord.ext.commands'] = discord_ext_commands

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
import whois_bot

passed = 0
failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f'  PASS  {name}')
    else:
        failed += 1
        print(f'  FAIL  {name}')

# --- build_nickname_update_text ---
print('build_nickname_update_text:')
t = whois_bot.build_nickname_update_text('OldNick', 'NewNick', 'user1', '<@123>')
check('changed: has mention', '<@123>' in t)
check('changed: old -> new', '`OldNick` → `NewNick`' in t)
check('changed: command reminder present', '$help' in t and '$note "nick" "note"' in t)
check('changed: action text', 'changed their nickname' in t)

t = whois_bot.build_nickname_update_text(None, 'FreshNick', 'user1', '<@123>')
check('set: action text', 'set their nickname to' in t)
check('set: falls back to username for old', '`user1` → `FreshNick`' in t)

t = whois_bot.build_nickname_update_text('OldNick', None, 'user1', '<@123>')
check('removed: action text', 'removed their nickname' in t)
check('removed: falls back to username for new', '`OldNick` → `user1`' in t)

# --- GuildConfig load/save ---
print('GuildConfig load/save:')
tmpdir = tempfile.mkdtemp(prefix='whois_test_')
config_path = os.path.join(tmpdir, 'guild_config.json')
whois_bot.GuildConfig.initialize(config_path)
check('load missing file returns {}', whois_bot.GuildConfig.load() == {})

whois_bot.GuildConfig.save({'111': 222})
with open(config_path) as f:
    raw = json.load(f)
check('save writes JSON', raw == {'111': 222})
check('load round-trip', whois_bot.GuildConfig.load() == {'111': 222})

# corrupt file handled gracefully
with open(config_path, 'w') as f:
    f.write('{not json')
check('corrupt config -> {}', whois_bot.GuildConfig.load() == {})

# --- get_announcement_channel resolution ---
print('get_announcement_channel:')
class FakeChannel:
    def __init__(self, cid, name):
        self.id = cid
        self.name = name
        self.type = 'text'

class FakeGuild:
    def __init__(self, gid, name, channels):
        self.id = gid
        self.name = name
        self.text_channels = channels
    def get_channel(self, cid):
        for c in self.text_channels:
            if c.id == cid:
                return c
        return None

voice = FakeChannel(1, 'voice-chat-sharing')
general = FakeChannel(2, 'general')
guild = FakeGuild(42, 'Test Server', [general, voice])

# no config -> fallback to voice-chat-sharing
whois_bot.GuildConfig.initialize(os.path.join(tmpdir, 'empty.json'))
check('fallback: voice-chat-sharing auto-detected', whois_bot.GuildConfig.get_announcement_channel(guild) is voice)

# no voice-chat-sharing channel at all -> None
guild2 = FakeGuild(43, 'Other Server', [general])
check('no match -> None', whois_bot.GuildConfig.get_announcement_channel(guild2) is None)

# configured channel wins over fallback
whois_bot.GuildConfig.initialize(config_path)
whois_bot.GuildConfig.save({'42': 2})
check('configured channel wins', whois_bot.GuildConfig.get_announcement_channel(guild) is general)

# configured channel missing -> falls back
whois_bot.GuildConfig.save({'42': 999})
check('stale configured channel falls back to voice-chat-sharing',
      whois_bot.GuildConfig.get_announcement_channel(guild) is voice)

# --- regexes ---
print('command regexes:')
check('$setchannel #chan matches', whois_bot.SET_CHANNEL_COMMAND_RE.match('$setchannel #123') is not None)
check('$setchannel bare matches', whois_bot.SET_CHANNEL_COMMAND_RE.match('$setchannel') is not None)
check('$setchannel captures name', whois_bot.SET_CHANNEL_COMMAND_RE.match('$setchannel voice-chat-sharing').group(1).strip() == 'voice-chat-sharing')
check('$unsetchannel matches', whois_bot.UNSET_CHANNEL_COMMAND_RE.match('$unsetchannel') is not None)
check('$setchannel does not catch $unsetchannel', whois_bot.UNSET_CHANNEL_COMMAND_RE.match('$setchannel x') is None)
check('HELP_TEXT lists setchannel', '$setchannel' in whois_bot.HELP_TEXT)
check('HELP_TEXT lists unsetchannel', '$unsetchannel' in whois_bot.HELP_TEXT)

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
