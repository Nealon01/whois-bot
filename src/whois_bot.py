import datetime
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
HELP_TEXT = '\n'.join([
    'Available commands:',
    '$help - Shows this list of commands',
    '$list - list all nicknames/notes',
    '$user "{nickname/username}" - list specific user\'s nickname/note',
    '$note "{nickname/username}" "{note}" - Update user note by nickname',
    '$note_name "{username}" "{note}" - Update user note by username',
])

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
        tmp = '`'
        max_len = 0
        for user in users.values():
            nick = user.nickname if user.nickname is not None else user.username
            if len(nick) > max_len:
                max_len = len(nick) + 2

        for user in sorted(users.values()):
            nick = user.nickname if user.nickname is not None else user.username
            tmp += nick.ljust(max_len) + '<-> ' + user.note + '\n'

        return tmp + '`'

    @staticmethod
    def create_user_record(users, username):
        user = users[username]
        nick = user.nickname if user.nickname is not None else user.username
        return 'Nickname:\t' + nick + '\t- Note:\t' + user.note + '\n'

    @staticmethod
    def log(message):
        """ Logs a message. """
        print(f'[WhoIs Bot] [{datetime.datetime.now()}]: {message}')


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
    """Called when a member has been updates (nickname change)"""
    users = UserCommands.load_users_from_file()
    UserCommands.log("before: '" + before.name + "'. After: " + after.name)
    # if user has tracked role
    if any(x.name == UserCommands.ROLE for x in after.roles):
        if after.name in users:
            if after.nick == before.nick:
                pass # unimportant change to already tracked user
            else:
                # new nickname on existing user
                UserCommands.log("User '" + before.name + "' updated nickname to '" + before.nick + "'")
                users[after.name].nickname = after.nick
                UserCommands.write_users_to_file(users)
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
        text = UserCommands.create_nickname_list(UserCommands.load_users_from_file())
        await message.channel.send(text)
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
            UserCommands.log('Updating note for \'' + args[0] + '\' to \'' + args[1] + '\'')
            users[args[0]].note = args[1]
            UserCommands.write_users_to_file(users)


UserCommands.initialize(os.getenv('DISCORD_GUILD'), os.getenv('DICT_PATH'), os.getenv('DISCORD_ROLE'))
bot.run(os.getenv('DISCORD_TOKEN'))
