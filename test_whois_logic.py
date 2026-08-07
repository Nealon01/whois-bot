"""Tests for the pure logic in whois_bot.py — run without a real discord library.

Usage: python3 test_whois_logic.py
"""
import asyncio
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
        self.sent = []
    async def send(self, *a, **k):
        self.sent.append(a)
        return None

class FakeBrokenChannel(FakeChannel):
    async def send(self, *a, **k):
        raise RuntimeError('boom')

class FakeVoiceChannel:
    def __init__(self, cid, name):
        self.id = cid
        self.name = name
        self.type = 'voice'

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

# fallback also matches emoji-prefixed channel names (e.g. 🔊voice-chat-sharing)
emoji_chan = FakeChannel(9, '🔊voice-chat-sharing')
guild_emoji = FakeGuild(45, 'Emoji Server', [general, emoji_chan])
check('fallback: emoji-prefixed channel auto-detected',
      whois_bot.GuildConfig.get_announcement_channel(guild_emoji) is emoji_chan)

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

# configured channel is a voice channel (no .send) -> falls back
voice_chan = FakeVoiceChannel(3, 'voice-chat')
guild3 = FakeGuild(44, 'Voice Guild', [general, voice, voice_chan])
whois_bot.GuildConfig.save({'44': 3})
check('configured voice channel falls back to text channel',
      whois_bot.GuildConfig.get_announcement_channel(guild3) is voice)

# --- regexes ---
print('command regexes:')
check('$setchannel #chan matches', whois_bot.SET_CHANNEL_COMMAND_RE.match('$setchannel #123') is not None)
check('$setchannel bare matches', whois_bot.SET_CHANNEL_COMMAND_RE.match('$setchannel') is not None)
check('$setchannel captures name', whois_bot.SET_CHANNEL_COMMAND_RE.match('$setchannel voice-chat-sharing').group(1).strip() == 'voice-chat-sharing')
check('$unsetchannel matches', whois_bot.UNSET_CHANNEL_COMMAND_RE.match('$unsetchannel') is not None)
check('$setchannel does not catch $unsetchannel', whois_bot.UNSET_CHANNEL_COMMAND_RE.match('$setchannel x') is None)
check('HELP_TEXT lists setchannel', '$setchannel' in whois_bot.HELP_TEXT)
check('HELP_TEXT lists unsetchannel', '$unsetchannel' in whois_bot.HELP_TEXT)

# --- on_member_update handler-level tests (regression for review findings C1/M1/M2/M4) ---
print('on_member_update handler:')
tracked_role = 'Tracked'
whois_bot.UserCommands.ROLE = tracked_role
users_path = os.path.join(tmpdir, 'users.pkl')
whois_bot.UserCommands.PATH = users_path

class FakeRole:
    def __init__(self, name):
        self.name = name

class FakeMember:
    def __init__(self, name, nick, roles, guild, mention=None):
        self.name = name
        self.nick = nick
        self.roles = roles
        self.guild = guild
        self.mention = mention or f'<@{name}>'

role = FakeRole(tracked_role)
handler_guild = FakeGuild(999, 'Handler Server', [])
alert_channel = FakeChannel(1, 'voice-chat-sharing')
handler_guild.text_channels = [alert_channel]

def run_member_update(before, after):
    asyncio.run(whois_bot.on_member_update(before, after))
    with open(users_path, 'rb') as f:
        return whois_bot.pickle.load(f)

# C1: username change WITHOUT nick change must persist the migration
whois_bot.UserCommands.write_users_to_file({'alice': whois_bot.User(FakeMember('alice', 'AliceNick', [role], handler_guild))})
users = run_member_update(
    FakeMember('alice', 'AliceNick', [role], handler_guild),
    FakeMember('alice_new', 'AliceNick', [role], handler_guild))
check('C1: migration persisted on username change', 'alice_new' in users and 'alice' not in users)
check('M1: migrated record username updated', users['alice_new'].username == 'alice_new')
check('C1: note preserved through migration', users['alice_new'].note == '')
check('C1: no announcement sent for nick-unchanged event', alert_channel.sent == [])

# M4: username collision must NOT destroy the existing record
whois_bot.UserCommands.write_users_to_file({
    'alice': whois_bot.User(FakeMember('alice', None, [role], handler_guild)),
    'bob': whois_bot.User(FakeMember('bob', None, [role], handler_guild))})
m4_users = whois_bot.UserCommands.load_users_from_file()
m4_users['bob'].note = 'BOB NOTE'
whois_bot.UserCommands.write_users_to_file(m4_users)
users = run_member_update(
    FakeMember('alice', None, [role], handler_guild),
    FakeMember('bob', None, [role], handler_guild))
check('M4: collision keeps existing bob record', 'bob' in users and users['bob'].note == 'BOB NOTE')
check('M4: collision keeps alice record too', 'alice' in users)

# M2 + happy path: nick change sends announcement, send failure doesn't crash
whois_bot.UserCommands.write_users_to_file({'carol': whois_bot.User(FakeMember('carol', 'OldN', [role], handler_guild))})
alert_channel.sent = []
users = run_member_update(
    FakeMember('carol', 'OldN', [role], handler_guild),
    FakeMember('carol', 'NewN', [role], handler_guild))
check('announcement sent on nick change', len(alert_channel.sent) == 1)
check('announcement contains new nickname', 'NewN' in alert_channel.sent[0][0])
check('announcement contains command reminder', '$help' in alert_channel.sent[0][0])
check('nick persisted', users['carol'].nickname == 'NewN')

broken_guild = FakeGuild(998, 'Broken Server', [FakeBrokenChannel(7, 'voice-chat-sharing')])
whois_bot.UserCommands.write_users_to_file({'dan': whois_bot.User(FakeMember('dan', 'A', [role], broken_guild))})
try:
    run_member_update(
        FakeMember('dan', 'A', [role], broken_guild),
        FakeMember('dan', 'B', [role], broken_guild))
    check('M2: send failure does not crash handler', True)
except Exception as e:
    check('M2: send failure does not crash handler', False)

# untracked member: no record change, no announcement
whois_bot.UserCommands.write_users_to_file({'erin': whois_bot.User(FakeMember('erin', 'E', [role], handler_guild))})
alert_channel.sent = []
untracked_role = FakeRole('OtherRole')
users = run_member_update(
    FakeMember('frank', 'X', [untracked_role], handler_guild),
    FakeMember('frank', 'Y', [untracked_role], handler_guild))
check('untracked nick change: no announcement', alert_channel.sent == [])
check('untracked nick change: no record added', 'frank' not in users)

print(f'\n{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
