import datetime
import json
import os
import re
import pickle

import discord
from discord.ext import commands

from dotenv import load_dotenv

load_dotenv()

HELP_COMMAND_RE = re.compile(r'^\s*\$help\s*$')
LIST_COMMAND_RE = re.compile(r'^\s*\$list\s*$')
USER_COMMAND_RE = re.compile(r'^\s*\$user\s.*$')
NOTE_COMMAND_RE = re.compile(r'^\s*\$note\s.*$')
NOTE_NAME_COMMAND_RE = re.compile(r'^\s*\$note_name\s.*$')
SET_CHANNEL_COMMAND_RE = re.compile(r'^\s*\$setchannel\b(.*)$', re.IGNORECASE)
UNSET_CHANNEL_COMMAND_RE = re.compile(r'^\s*\$unsetchannel\b(.*)$', re.IGNORECASE)
HELP_TEXT = '\n'.join([
    'Available commands:',
    '$help - Shows this list of commands',
    '$list - list all nicknames/notes',
    '$user "{nickname/username}" - list specific user\'s nickname/note',
    '$note "{nickname/username}" "{note}" - Update user note by nickname',
    '$note_name "{username}" "{note}" - Update user note by username',
    '$setchannel #channel - Set the channel where nickname changes are announced (admins)',
    '$unsetchannel - Disable nickname change announcements (admins)',
])
# Shown as a footer on every nickname-change announcement.
COMMAND_REMINDER = 'Commands: `$help` `$list` `$user "nick"` `$note "nick" "note"`'
# Default announcement channel name used when a server hasn't run $setchannel yet.
DEFAULT_ALERT_CHANNEL = 'voice-chat-sharing'

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='$', intents=intents)


class User:
    def __init__(self, member):
        self.username = member.name
        self.nickname = member.nick
        self.note = ''

    def __gt__(self, user2):
        nick_1 = self.nickname if self.nickname is not None else self.username
        nick_2 = user2.nickname if user2.nickname is not None else user2.username
        return nick_1.lower() > nick_2.lower()


class UserCommands:
    GUILD = ''
    PATH = ''
    ROLE = ''
    @staticmethod
    def initialize(guild, path, role):
        UserCommands.GUILD = guild
        UserCommands.PATH = path
        UserCommands.ROLE = role

    @staticmethod
    def load_users_from_file():
        f = open(UserCommands.PATH, 'rb')
        tmp = pickle.load(f)
        f.close()
        return tmp

    @staticmethod
    def write_users_to_file(users):
        f = open(UserCommands.PATH, 'wb')
        pickle.dump(users, f)
        f.close()
        UserCommands.log('Users Updated: ' + UserCommands.PATH)

    @staticmethod
    def load_users_from_server():
        guild = discord.utils.get(bot.guilds, name=UserCommands.GUILD)
        tmp = {}
        for member in guild.members:
            if any(x.name == UserCommands.ROLE for x in member.roles):
                tmp[member.name] = User(member)

        if not os.path.exists(UserCommands.PATH):
            UserCommands.write_users_to_file(tmp)

        return tmp

    @staticmethod
    def update_nicknames_from_server():
        server_users = UserCommands.load_users_from_server()
        file_users = UserCommands.load_users_from_file()

        for user in server_users.values():
            if user.username in file_users:
                file_users[user.username].nickname = server_users[user.username].nickname
            else:
                file_users[user.username] = user

        # prune records for users no longer in the tracked role/server.
        # Guarded: if the server lookup came back empty (transient failure),
        # don't wipe the store.
        if server_users:
            stale = [k for k in file_users if k not in server_users]
            for k in stale:
                UserCommands.log("User '" + k + "' removed from tracking (no longer in role)")
                del file_users[k]

        f = open(UserCommands.PATH, 'wb')
        pickle.dump(file_users, f)
        f.close()
        UserCommands.log('Users Nicknames Updated: ' + UserCommands.PATH)

    @staticmethod
    def get_username_from_nickname(users, nickname):
        if nickname in users:
            return nickname
        else:
            for user in users.values():
                if user.nickname == nickname:
                    return user.username
            return ''

    @staticmethod
    def print_users_list(users):
        for user in users.values():
            name = user.username if user.username is not None else ''
            nick = user.nickname if user.nickname is not None else ''
            UserCommands.log('Name:\t' + name + '\t- Nickname:\t' + nick + '\t- Note:\t' + user.note)

    @staticmethod
    def create_nickname_list(users):
        """Builds the nickname/note listing.

        Returns a LIST of strings, each under the Discord 2000-char message
        limit (chunked on line boundaries) so large rosters don't fail to send.
        """
        max_len = 0
        displays = {}
        for user in users.values():
            if user.nickname is not None:
                display = f"{user.nickname} ({user.username})"
            else:
                display = user.username
            displays[id(user)] = display
            if len(display) > max_len:
                max_len = len(display) + 2

        lines = []
        for user in sorted(users.values()):
            lines.append(displays[id(user)].ljust(max_len) + '<-> ' + user.note)

        chunks = []
        current = '`'
        for line in lines:
            candidate = current + line + '\n'
            if len(candidate) + 1 > 1900:  # +1 for the closing backtick
                chunks.append(current + '`')
                current = '`' + line + '\n'
            else:
                current = candidate
        chunks.append(current + '`')
        return chunks

    @staticmethod
    def create_user_record(users, username):
        user = users[username]
        nick = user.nickname if user.nickname is not None else '(none)'
        return 'Username:\t' + user.username + '\nNickname:\t' + nick + '\nNote:\t' + user.note + '\n'

    @staticmethod
    def log(message):
        """ Logs a message. """
        print(f'[WhoIs Bot] [{datetime.datetime.now()}]: {message}')


def build_nickname_update_text(before_nick, after_nick, username, mention):
    """ Builds the announcement text for a nickname change. Pure function, testable. """
    old_disp = before_nick if before_nick is not None else username
    new_disp = after_nick if after_nick is not None else username
    if before_nick is None:
        action = 'set their nickname to'
    elif after_nick is None:
        action = 'removed their nickname'
    else:
        action = 'changed their nickname'
    return (
        f'🔔 **{mention}** {action}\n'
        f'`{old_disp}` → `{new_disp}`\n'
        f'📋 {COMMAND_REMINDER}'
    )


class GuildConfig:
    """ Per-guild settings (currently: the nickname-change announcement channel), stored in JSON. """
    CONFIG_PATH = ''

    @staticmethod
    def initialize(path):
        GuildConfig.CONFIG_PATH = path

    @staticmethod
    def load():
        if not GuildConfig.CONFIG_PATH or not os.path.exists(GuildConfig.CONFIG_PATH):
            return {}
        try:
            with open(GuildConfig.CONFIG_PATH, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            UserCommands.log('Failed to read config ' + GuildConfig.CONFIG_PATH + ': ' + str(e))
            return {}

    @staticmethod
    def save(config):
        try:
            # atomic-ish write: temp file + replace, so a crash can't corrupt the config
            tmp_path = GuildConfig.CONFIG_PATH + '.tmp'
            with open(tmp_path, 'w') as f:
                json.dump(config, f, indent=2)
            os.replace(tmp_path, GuildConfig.CONFIG_PATH)
            UserCommands.log('Config saved: ' + GuildConfig.CONFIG_PATH)
            return True
        except OSError as e:
            UserCommands.log('Failed to write config ' + GuildConfig.CONFIG_PATH + ': ' + str(e))
            return False

    @staticmethod
    def get_announcement_channel(guild):
        """ Resolves the channel to announce nickname changes in.

        Priority: 1) channel set via $setchannel for this guild, 2) a channel named
        DEFAULT_ALERT_CHANNEL (case-insensitive), 3) None (announcements disabled).
        """
        config = GuildConfig.load()
        channel_id = config.get(str(guild.id))
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel is not None and hasattr(channel, 'send'):
                return channel
            UserCommands.log(f"Configured channel {channel_id} not found/usable in guild '{guild.name}', falling back.")
        for channel in guild.text_channels:
            if DEFAULT_ALERT_CHANNEL in channel.name.lower():
                UserCommands.log(f"Auto-detected '{channel.name}' for guild '{guild.name}' (run $setchannel to change it).")
                return channel
        UserCommands.log(f"No announcement channel for guild '{guild.name}' — run $setchannel #channel to enable alerts.")
        return None


@bot.event
async def on_ready():
    """Called when the bot is first readied."""
    UserCommands.log("READY")
    activity = discord.Activity(
        name='you',
        type=discord.ActivityType.watching)
    await bot.change_presence(activity=activity)
    UserCommands.update_nicknames_from_server()


@bot.event
async def on_member_update(before, after):
    """Called when a member has been updated (nickname or role change)"""
    users = UserCommands.load_users_from_file()
    UserCommands.log("before: '" + before.name + "'. After: " + after.name)
    # if user has tracked role
    if any(x.name == UserCommands.ROLE for x in after.roles):
        if before.name != after.name and before.name in users:
            # global username changed: migrate the stored record to the new key
            if after.name in users:
                # collision — another record already owns the new username; don't destroy it
                UserCommands.log("Username change '" + before.name + "' -> '" + after.name
                                 + "' collides with an existing record; keeping existing.")
            else:
                users[after.name] = users.pop(before.name)
                users[after.name].username = after.name
                UserCommands.log("Username changed: '" + before.name + "' -> '" + after.name + "' (record migrated)")
                UserCommands.write_users_to_file(users)

        if after.name in users:
            if after.nick == before.nick:
                pass # unimportant change to already tracked user
            else:
                # new nickname on existing user
                UserCommands.log("User '" + before.name + "' updated nickname to '" + str(after.nick) + "'")
                users[after.name].nickname = after.nick
                UserCommands.write_users_to_file(users)
                # announce the change to the server's configured channel
                channel = GuildConfig.get_announcement_channel(after.guild)
                if channel is not None:
                    try:
                        await channel.send(build_nickname_update_text(
                            before.nick, after.nick, after.name, after.mention))
                    except Exception as e:
                        # never let a send failure (Forbidden, HTTP, etc.) crash the handler
                        UserCommands.log('Failed to announce nickname change: ' + str(e))
        else:
            # new user added
            UserCommands.log("User '" + after.name + "' added to tracking")
            users[after.name] = User(after)
            UserCommands.write_users_to_file(users)
    else:
        if after.name in users:
            # existing user removed
            del users[after.name]
            UserCommands.log("User '" + after.name + "' removed from tracking")
            UserCommands.write_users_to_file(users)
        else:
            pass # change to untracked user.


@bot.event
async def on_message(message):
    """Called when a new message is sent in the Discord."""
    if message.author == bot.user:
        return
    if HELP_COMMAND_RE.match(message.content) is not None:
        UserCommands.log(f'Got help request from {message.author.name}')
        await message.channel.send(HELP_TEXT)
    if LIST_COMMAND_RE.match(message.content) is not None:
        UserCommands.log(f'Got list request from {message.author.name}')
        for chunk in UserCommands.create_nickname_list(UserCommands.load_users_from_file()):
            await message.channel.send(chunk)
    if USER_COMMAND_RE.match(message.content) is not None:
        UserCommands.log(f'Got user request from {message.author.name}')
        UserCommands.log(message.content)
        args = re.findall('"([^"]*)"', message.content)
        if len(args) != 1:
            await message.channel.send("Must be 1 arg - 'NICKNAME'")
            UserCommands.log("Misformatted request.")
        else:
            users = UserCommands.load_users_from_file()
            username = UserCommands.get_username_from_nickname(users, args[0])
            if username != '':
                await message.channel.send(UserCommands.create_user_record(users, username))
            else:
                await message.channel.send("Cannot find username/nickname '" + args[0] + "'")
    elif NOTE_COMMAND_RE.match(message.content) is not None:
        UserCommands.log(f'Got note request from {message.author.name}')
        UserCommands.log(message.content)
        args = re.findall('"([^"]*)"', message.content)
        if len(args) != 2:
            await message.channel.send("Must be 2 args")
            UserCommands.log("Misformatted request.")
        else:
            users = UserCommands.load_users_from_file()
            username = UserCommands.get_username_from_nickname(users, args[0])

            if username != '':
                UserCommands.log('Updating note for \'' + args[0] + '\' to \'' + args[1] + '\'')
                users[username].note = args[1]
                UserCommands.write_users_to_file(users)
                await message.channel.send(UserCommands.create_user_record(users, username))
            else:
                await message.channel.send("Cannot find username/nickname '" + args[0] + "'")

    elif NOTE_NAME_COMMAND_RE.match(message.content) is not None:
        UserCommands.log(f'Got note request from {message.author.name}')
        UserCommands.log(message.content)
        args = re.findall('"([^"]*)"', message.content)
        if len(args) != 2:
            await message.channel.send("Must be 2 args")
        else:
            users = UserCommands.load_users_from_file()
            if args[0] in users:
                UserCommands.log('Updating note for \'' + args[0] + '\' to \'' + args[1] + '\'')
                users[args[0]].note = args[1]
                UserCommands.write_users_to_file(users)
                await message.channel.send(UserCommands.create_user_record(users, args[0]))
            else:
                await message.channel.send("Cannot find username '" + args[0] + "'")

    elif SET_CHANNEL_COMMAND_RE.match(message.content) is not None:
        UserCommands.log(f'Got setchannel request from {message.author.name}')
        if message.guild is None:
            return  # DM — nothing to configure
        if not (message.author.guild_permissions.manage_guild
                or message.author.guild_permissions.administrator):
            await message.channel.send("You need 'Manage Server' permission to change the alert channel.")
        else:
            set_channel_match = SET_CHANNEL_COMMAND_RE.match(message.content)
            target = set_channel_match.group(1).strip() if set_channel_match else ''
            if not target:
                await message.channel.send('Usage: `$setchannel #channel` (or `$setchannel channel-name`)')
            else:
                channel = None
                match = re.search(r'<#(\d+)>', target)
                if match:
                    channel = message.guild.get_channel(int(match.group(1)))
                if channel is None:
                    # exact name match first, then substring (handles emoji-prefixed names)
                    for c in message.guild.text_channels:
                        if c.name.lower() == target.lower():
                            channel = c
                            break
                if channel is None:
                    for c in message.guild.text_channels:
                        if target.lower() in c.name.lower():
                            channel = c
                            break
                if channel is None or not hasattr(channel, 'send'):
                    await message.channel.send("Couldn't find a text channel named `" + target + "`")
                else:
                    config = GuildConfig.load()
                    config[str(message.guild.id)] = channel.id
                    if GuildConfig.save(config):
                        await message.channel.send('✅ Nickname change alerts will be posted to #' + channel.name)
                    else:
                        await message.channel.send("❌ Couldn't save the config file — alert channel NOT changed.")
    elif UNSET_CHANNEL_COMMAND_RE.match(message.content) is not None:
        UserCommands.log(f'Got unsetchannel request from {message.author.name}')
        if message.guild is None:
            return  # DM — nothing to configure
        unset_channel_match = UNSET_CHANNEL_COMMAND_RE.match(message.content)
        if unset_channel_match and unset_channel_match.group(1).strip():
            await message.channel.send('Usage: `$unsetchannel` (takes no arguments)')
            return
        if not (message.author.guild_permissions.manage_guild
                or message.author.guild_permissions.administrator):
            await message.channel.send("You need 'Manage Server' permission to change the alert channel.")
        else:
            config = GuildConfig.load()
            if config.pop(str(message.guild.id), None) is not None:
                if GuildConfig.save(config):
                    await message.channel.send('Nickname change alerts disabled for this server.')
                else:
                    await message.channel.send("❌ Couldn't save the config file — alerts NOT disabled.")
            else:
                await message.channel.send('No alert channel was configured for this server.')


if __name__ == '__main__':
    UserCommands.initialize(os.getenv('DISCORD_GUILD'), os.getenv('DICT_PATH'), os.getenv('DISCORD_ROLE'))
    config_path = os.getenv('CONFIG_PATH') or os.path.join(
        os.path.dirname(os.getenv('DICT_PATH') or '.'), 'guild_config.json')
    GuildConfig.initialize(config_path)
    bot.run(os.getenv('DISCORD_TOKEN'))
