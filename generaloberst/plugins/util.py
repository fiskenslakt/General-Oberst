# -*- coding: utf-8 -*-

import calendar
import requests
import sqlite3
import time
import uuid
import json
import pendulum
import dateutil

from datetime import datetime, timedelta
from random import choice

from disco.bot import Plugin
from disco.bot.command import CommandLevels
from disco.util import snowflake
from disco.types.message import MessageEmbed


class UtilitiesPlugin(Plugin):
    tags_to_remove = {}

    secret_staff = [
        420366680859082752,     # ara's alt
        230085461220130816,     # a literal
        142757391799287808,     # fredits
        257723194331496448,     # gang
        302598805826830346,     # HP
        296438750588829699,     # tomato
    ]

    @Plugin.command('joined', '<server:str> [user:str]')
    def joined_command(self, event, server, user=None):
        """= joined =
        Displays date and time user joined discord or guild in EST
        You can convert the result to your timezone with the !timezone command
        usage    :: !joined <guild | discord> [user]
        aliases  :: None
        category :: Utilities
        == Examples
        !joined discord `No user supplied, defaults to you'
        !joined discord linux
        !joined guild   `No user supplied, defaults to you'
        !joined guild linux
        """
        if user is None:
            user = event.guild.members[event.msg.author.id]
        else:
            for member in event.guild.members.values():
                if user == member.name:
                    user = member
                    break
            else:
                event.msg.reply('No such user')
                return

        if server == 'guild':
            joined = user.joined_at
            joined = pendulum.datetime(joined.year, joined.month, joined.day, joined.hour, joined.minute, joined.second, tz='America/New_York')
        elif server == 'discord':
            joined = pendulum.from_timestamp(snowflake.to_unix(user.user.id), tz='America/New_York')
        else:
            return

        event.msg.reply(joined.format('[{} joined {}] dddd MMMM Do YYYY [at] h:mmA zz'.format(user.name, server)))

    @Plugin.command('strawpoll', aliases=['poll', 'sp'], parser=True)
    @Plugin.add_argument('title', nargs='+')
    @Plugin.add_argument('--options', '-o', nargs='+', required=True)
    def strawpoll_command(self, event, args):
        new_poll_url = 'https://www.strawpoll.me/api/v2/polls'
        get_poll_url = 'https://www.strawpoll.me/api/v2/polls/{}'

        title = ' '.join(args.title)
        options = [option.strip() for option in ' '.join(args.options).split('\\')]

        payload = {
            'title': title,
            'options': options,
            'captcha': True
        }

        poll = requests.post(new_poll_url, json=payload)
        new_poll_ID = poll.json()['id']
        poll_url = 'https://www.strawpoll.me/{}'.format(new_poll_ID)

        poll_data = requests.get(get_poll_url.format(new_poll_ID)).json()
        vote_data = zip(poll_data['options'], poll_data['votes'])
        display_votes = '\n'.join(['{}: {}'.format(option, vote) for option, vote in vote_data])

        event.msg.reply('{}\n\n```{}\n\n{}```'.format(poll_url, title, display_votes))

    @Plugin.command('ping')
    def ping_command(self, event):
        """= ping =
        Latency of bot and discord (not very accurate)
        usage    :: !ping
        aliases  :: None
        category :: Utilities
        """
        user_ping = event.msg.timestamp
        bot = event.msg.reply('Pong!')
        bot_ping = bot.timestamp

        user_bot_latency = (bot_ping - user_ping).total_seconds() * 1000.0

        bot.edit('Latency of you to bot: ~{:.2f}ms'.format(user_bot_latency))

    @Plugin.command('choose', aliases=['pick'], parser=True)
    @Plugin.add_argument('options', nargs='+')
    def choose_command(self, event, args):
        """= choose =
        Chooses an option from a list of options given by the user
        usage    :: !choose <options ...>
        aliases  :: pick
        category :: Utilities
        == Note
        Must have at least 2 options
        Options are separated with backslashes
        == Examples
        !choose option1 \ option2 \ option3
        !choose linux is the best admin \ ara is the best admin \ riku is the best admin \ noob is the best admin
        """
        options = [option.strip() for option in ' '.join(args.options).split('\\')]
        if len(options) <= 1 or not all(options): # if not at least two options and no options are empty strings
            return

        chosen = choice(options)
        event.msg.reply('I choose: {}'.format(chosen))

    def add_tag(self, event, args, conn, user_level):
        self.log.info('Adding tag {} with value {}'.format(args.name, args.value))
        if args.server and user_level < CommandLevels.MOD:
            r = event.msg.reply('Only privileged users can add server-wide tags')
            time.sleep(5)
            r.delete()
            return

        if not all((args.name, args.value)):
            self.log.error('Missing arguments')
            return

        name = ' '.join(args.name)
        value = ' '.join(args.value)

        c = conn.cursor()
        c.execute('select count(*) from tags where user_id is NULL and name = ?', (name,))
        if c.fetchone()[0] > 0:
            self.log.error('Server-wide tag by the name {} already exists'.format(name))
            r = event.msg.reply('A server-wide tag already has the name: {}'.format(name))
            time.sleep(5)
            r.delete()
            return

        c.execute('select count(*) from tags where user_id = ? and name = ?', (event.author.id, name))
        if c.fetchone()[0] > 0:
            self.log.error('User {} already has tag under the name: {}'.format(event.author, name))
            r = event.msg.reply('You already have a tag under the name: {}'.format(name))
            time.sleep(5)
            r.delete()
            return

        if args.server:
            c.execute('select count(*) from tags where name = ?', (name,))
            tags_count = c.fetchone()[0]
            if tags_count > 0:
                dm = event.author.open_dm()
                dm.send_message('{} user(s) already have a tag with the name: {}\n\
                You must either delete all of them before adding this tag server-wide, or use a different name\n\
                You can do `!tag -i {}` to see all tags with this name and their ID\'s for deletion'.format(name).replace('\t', ''))
                return
            c.execute("insert into tags (username, name, value)\
            values (?, ?, ?)", (str(event.author), name, value))
        else:
            c.execute("insert into tags (user_id, username, name, value)\
            values (?, ?, ?, ?)", (event.author.id, str(event.author), name, value))

        conn.commit()
        r = event.msg.reply('Successfully added tag')
        time.sleep(5)
        r.delete()

    def delete_tag(self, event, args, conn, user_level):
        REMOVE = False

        if not args.key:
            self.log.error('{} tried using -d flag without a key'.format(event.author))
            event.msg.reply('You must provide the ID of the tag')
            return

        key = args.key[0]
        unique_id = key         # save unique_id for when key is overwritten with tag ID

        if self.tags_to_remove.get(key):
            key = self.tags_to_remove[key]
            REMOVE = True

        user_level = self.bot.get_level(event.author)
        c = conn.cursor()
        if not c.execute('select exists(select 1 from tags where ID = ?)', (key,)).fetchone()[0]:
            self.log.error('{} tried deleting non-existent tag'.format(event.author))
            event.msg.reply('No tag with the ID `{}` exists'.format(key))
            return

        c.execute('select user_id from tags where ID = ?', (key,))
        user_id = c.fetchone()[0]
        if user_id is None and user_level < CommandLevels.MOD:
            self.log.error('{} tried deleting a server-wide tag'.format(event.author))
            event.msg.reply('Only staff can delete server-wide tags')
            return

        if user_id is not None and user_id != event.author.id and user_level < CommandLevels.MOD:
            self.log.error("{} tried deleting someone else's tag")
            event.msg.reply("You can't delete another user's tag")
            return

        if REMOVE:
            self.log.info('REMOVE=True, deleting tag {}, requested by user {}'.format(key, event.author))
            c.execute('delete from tags where ID = ?', (key,))
            conn.commit()
            self.log.info('deleted tag {}'.format(key))
            r = event.msg.reply('Successfully deleted tag')
            time.sleep(5)
            r.delete()
            del self.tags_to_remove[unique_id]
            self.log.info('Removed tag {} with unique ID {} from self.tags_to_remove'.format(key, unique_id))
        else:                   # not marked for deletion yet so ask for confirmation
            self.log.info('{} marking tag {} for deletion'.format(event.author, key))
            name, value = c.execute('select name, value from tags where ID = ?', (key,)).fetchone()
            unique_id = uuid.uuid4().hex
            self.tags_to_remove[unique_id] = key
            self.log.info('Created unique ID {} for tag {}'.format(unique_id, key))
            dm = event.author.open_dm()
            from inspect import cleandoc
            dm.send_message(cleandoc(
                u'''Please confirm you want to delete this tag:
                ID: {}
                Name: {}
                Value: {}{}

                To confirm and delete **permanently**, please run the following command in the server you executed the first delete command:
                `{}`

                Your confirmation code will **expire** in 1 minute.
                '''.format(key, name, value if len(value) <= 30 else value[:30], '' if len(value) <= 30 else '... (Truncated to fit in message)',
                           '`!tag -dk {}`'.format(unique_id))
            ))
            time.sleep(60)
            try:
                del self.tags_to_remove[unique_id]
                self.log.info('Tag {} with unique ID {} expired from self.tags_to_remove'.format(key, unique_id))
            except KeyError:
                self.log.info('Tag {} with unique ID {} was removed before it could expire'.format(key, unique_id))

    def update_tag(self, event, args, conn, user_level):
        if not (args.name or args.value):
            self.log.error('{} tried using -u flag without a name or value'.format(event.author))
            event.msg.reply('You must provide the ID of the tag')
            return

        name = ' '.join(args.name) if args.name else None
        value = ' '.join(args.value) if args.value else None

        if not args.key:
            self.log.error('{} tried using -u flag without a key'.format(event.author))
            return

        key = args.key[0]

        user_level = self.bot.get_level(event.author)
        c = conn.cursor()
        if not c.execute('select exists(select 1 from tags where ID = ?)', (key,)).fetchone()[0]:
            self.log.error('{} tried updating non-existent tag'.format(event.author))
            event.msg.reply('No tag with the ID `{}` exists'.format(key))
            return

        c.execute('select user_id from tags where ID = ?', (key,))
        user_id = c.fetchone()[0]
        if user_id is None and user_level < CommandLevels.MOD:
            self.log.error('{} tried updating a server-wide tag'.format(event.author))
            event.msg.reply('Only staff can update server-wide tags')
            return

        if user_id is not None and user_id != event.author.id:
            self.log.error("{} tried updating another user's tag".format(event.author))
            event.msg.reply("You can't update another user's tag")
            return

        if name and value:
            query = ('update tags set username = ?, name = ?, value = ? where ID = ?',
                     (str(event.author), name, value, key))
        elif name:
            query = ('update tags set username = ?, name = ? where ID = ?',
                     (str(event.author), name, key))
        elif value:
            query = ('update tags set username = ?, value = ? where ID = ?',
                     (str(event.author), value, key))

        c.execute(*query)
        conn.commit()
        self.log.info('{} updated tag with ID: {}'.format(event.author, key))
        r = event.msg.reply('Successfully updated tag ID {}'.format(key))
        time.sleep(5)
        r.delete()

    def list_tags(self, event, args, conn, user_level):
        if args.name or args.value:
            self.log.error('{} tried using -l flag with too many args:\n{}'.format(event.author, args))
            return

        dm = event.author.open_dm()
        c = conn.cursor()
        c.execute('select count(*) from tags')
        if c.fetchone()[0] == 0:
            dm.send_message('No tags have been added yet')
            return

        c.execute('select max(length(name)) from tags where user_id is NULL or user_id = ?', (event.author.id,))
        width = c.fetchone()[0]

        msg = u'```asciidoc\n== Server-wide Tags ==\n'
        c.execute('select name, value from tags where user_id is NULL')
        for name, value in c:
            msg += u'{:<{width}} :: {}\n'.format(name, value, width=width)

        if not args.server:
            msg += '\n== Your Tags ==\n'
            c.execute('select name, value from tags where user_id = ?', (event.author.id,))
            for name, value in c:
                msg += u'{:<{width}} :: {}\n'.format(name, value, width=width)

        msg += u'```'

        dm.send_message(msg)

    def list_all_tags(self, event, args, conn, user_level):
        if user_level < CommandLevels.MOD:
            self.log.warning('Unprivileged user "{}" tried executing --list-all flag'.format(event.author))
            r = event.msg.reply('Only privileged users can use this command')
            time.sleep(5)
            r.delete()
            return

        if args.name or args.value:
            self.log.error('{} tried using -L flag with too many args:\n{}'.format(event.author, args))
            return

        dm = event.author.open_dm()
        c = conn.cursor()
        c.execute('select count(*) from tags')
        if c.fetchone()[0] == 0:
            dm.send_message('No tags have been added yet')
            return

        c.execute('select max(length(name)) from tags')
        width = c.fetchone()[0]

        msg = u'```asciidoc\n== Server-wide Tags ==\n'
        c.execute('select name, value from tags where user_id is NULL')
        for name, value in c:
            msg += u'{:<{width}} :: {}\n'.format(name, value, width=width)

        c.execute('select distinct user_id from tags where user_id is not NULL')
        users = {user_id[0] for user_id in c}
        for user in users:
            msg += '\n== {} ==\n'.format(event.guild.members.get(user).name)
            c.execute('select name, value from tags where user_id = ?', (user,))
            for name, value in c:
                msg += u'{:<{width}} :: {}\n'.format(name, value, width=width)

        msg += '```'

        if len(msg) < 2000:
            dm.send_message(msg)
        else:
            url = 'https://api.paste.ee/v1/pastes'
            header = {'X-Auth-Token': 'aePM1mOrLrbtdgLkGpINjOjJxr9TAtUz4fKYfnLXW'}
            payload = {'sections': [{'contents': msg.strip('```').strip('asciidoc')}]}
            r = requests.post(url, headers=header, json=payload)
            dm.send_message('Pasting to `https://paste.ee` because output is too long: {}'.format(r.json()['link']))

    def info_tag(self, event, args, conn, user_level):
        if args.value:
            self.log.error('{} included value in info lookup'.format(event.author))
            return

        dm = event.author.open_dm()
        search = ' '.join(args.name)
        self.log.info('Fetching tag info on name: {}'.format(search))
        c = conn.cursor()
        if args.server:
            query = ('select ID, username, name from tags where user_id is NULL and name like ?', ('%'+search+'%',))
        elif user_level >= CommandLevels.MOD:
            query = ('select ID, username, name from tags where name like ?', ('%'+search+'%',))
        else:
            query = ('select ID, username, name from tags where user_id = ? and name like ?', (event.author.id, '%'+search+'%'))

        c.execute('select max(length(name)) from tags where name like ?', ('%'+search+'%',))
        width = c.fetchone()[0]
        if width is None:
            self.log.error("{}'s search '{}' had no results".format(event.author, search))
            return
        msg = u'```asciidoc\n== Tags similar to {}\n'.format(search)
        c.execute(*query)
        msg += u'{:<10}{:<{width}}{}\n'.format('*ID*', '*Name*', '*Created by*', width=width+5)
        for ID, username, name in c:
            msg += u' {:<10}{:<{width}}{}\n'.format(ID, name, username, width=width+5)

        msg += u'```'

        if len(msg) < 2000:
            dm.send_message(msg)
        else:
            url = 'https://api.paste.ee/v1/pastes'
            header = {'X-Auth-Token': 'aePM1mOrLrbtdgLkGpINjOjJxr9TAtUz4fKYfnLXW'}
            payload = {'sections': [{'contents': msg.strip('```').strip('asciidoc')}]}
            r = requests.post(url, headers=header, json=payload)
            dm.send_message('Pasting to `https://paste.ee` because output is too long: {}'.format(r.json()['link']))

    def get_tag(self, event, args, conn, user_level):
        self.log.info('Getting tag {}'.format(args.name))
        if not args.name or args.value:
            return

        name = ' '.join(args.name)

        c = conn.cursor()
        c.execute('select value from tags where user_id is NULL and name = ?', (name,))
        value = c.fetchone()
        if value:
            event.msg.reply(value[0])
            return

        c.execute('select value from tags where user_id = ? and name = ?', (event.author.id, name))
        value = c.fetchone()
        if value:
            event.msg.reply(value[0])
            return
        else:
            self.log.info('No such tag exists named {}'.format(name))
            r = event.msg.reply('No such tag exists')
            time.sleep(5)
            r.delete()

    def count_tags(self, event, args, conn):
        c = conn.cursor()
        c.execute('select count(*) from tags')
        count = c.fetchone()[0]
        c.execute('select count(*) from tags where user_id is NULL')
        server_count = c.fetchone()[0]
        c.execute('select count(*) from tags where user_id is not NULL')
        user_count = c.fetchone()[0]
        c.execute('select count(distinct user_id) from tags where user_id is not NULL')
        users_withtags = c.fetchone()[0]

        if count == 0:
            event.msg.reply('There aren\'t any tags yet')
        else:
            event.msg.reply('There {} currently {} {}. (Server-wide: {} / User Tags: {})\n{} {} {} tags'.format(
                'is' if count ==1 else 'are',
                count,
                'tag' if count == 1 else 'tags',
                server_count,
                user_count,
                users_withtags,
                'user' if users_withtags == 1 else 'users',
                'has' if users_withtags == 1 else 'have'
            ))

    @Plugin.command('tag', parser=True)
    @Plugin.add_argument('-a', '--add', action='store_true')
    @Plugin.add_argument('-d', '--delete', action='store_true')
    @Plugin.add_argument('-u', '--update', action='store_true')
    @Plugin.add_argument('-l', '--list', action='store_true')
    @Plugin.add_argument('-L', '--list-all', action='store_true')
    @Plugin.add_argument('-s', '--server', action='store_true')
    @Plugin.add_argument('-i', '--info', action='store_true')
    @Plugin.add_argument('-k', '--key', nargs=1)
    @Plugin.add_argument('name', nargs='*')
    @Plugin.add_argument('-v', '--value', nargs='*')
    def tag_command(self, event, args):
        """= tag =
        Create your own custom commands
        usage    :: !tag [-a] [-d] [-u] [-l] [-L] [-s] [-i] [-k] [name] [-v] [value]
        aliases  :: None
        category :: Utilities
        == Flags
        -a/--add      :: Add new tag
        -d/--delete   :: Delete tag based on tag ID
        -u/--update   :: Update tag with new value based on tag ID
        -l/--list     :: List all personal and server-wide tags
        -L/--list-all :: List every tag in the database (STAFF ONLY)
        -s/--server   :: Apply action to only server-wide tags
        -i/--info     :: Get info on tags that are similar to <tagname> (user who created it, ID of tag, etc)
        -k/--key      :: Denote following text will be ID of tag
        -v/--value    :: Denote following text to be value of tag
        == Constraints
        name  :: Must be <= 30 characters
        value :: Must be <= 1992 characters
        == Note
        Staff are allowed to delete any tags that might be inappropriate or offensive in some way
        == Add Examples
        !tag -a foo -v bar `Add tag named foo with value bar'
        !tag -a -s foo -v bar `Add server-wide tag named foo with value bar (STAFF ONLY)'
        !tag -as foo -v bar `equivalent to example above'
        == List Examples
        !tag -l `List all your personal tags and server-wide tags'
        !tag -ls `List only server-wide tags'
        !tag -L `Lists every tag in the database (STAFF ONLY)'
        == Info Examples
        !tag -i o `Search all personal and server-wide tags with o in its name and return info'
        !tag -si o `Search all server-wide tags with o in its name and return info'
        == Update Examples (Be careful with these!)
        !tag -u foo -v bar -k 42 `Updates name and value of tag with ID=42 to foo and bar respectively'
        !tag -uk 42 foo -v bar `Equivalent to previous example'
        !tag -u foo -k 42 `Only changes tag 42 name to foo (leaves value alone)'
        !tag -u -v bar -k 42 `Only changes tag 42 value to bar (leaves name alone)'
        == Delete Examples (Asks for confirmation first)
        !tag -dk 42 `Marks tag 42 for deletion (You will be messaged a unique id to delete this tag)'
        !tag -dk <unique id> `Deletes tag mapped to <unique id>'
        """
        if event.channel.is_dm:
            event.msg.reply('This command only works in a server :/')
            return

        self.log.info('!tag command triggered with args: {}'.format(args))

        server_id = event.guild.id
        user_level = self.bot.get_level(event.author)

        # key should be int in every case except when passing
        # unique hex code to --delete
        try:
            args.key = [int(args.key[0])]
        except:
            pass

        if args.name:
            name_len = sum(map(len, args.name))
            if name_len > 30:
                self.log.error('{} tried to create tag with name len: {}'.format(event.author, name_len))
                return
        if args.value:
            value_len = sum(map(len, args.value))
            if value_len > 1992:
                self.log.error('{} tried to create tag with value len: {}'.format(event.author, value_len))
                return

        try:
            conn = sqlite3.connect('db/{}.db'.format(server_id), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)

            if not any(v for k,v in vars(args).iteritems()):
                self.log.info('No args, responding with tag count')
                self.count_tags(event, args, conn)
                return

            if sum((args.add, args.delete, args.update, args.list, args.info, args.list_all)) > 1:
                return

            if any((args.add, args.delete, args.update, args.list, args.info, args.list_all)):
                event.msg.delete()

            if args.add:
                self.add_tag(event, args, conn, user_level)
            elif args.delete:
                self.delete_tag(event, args, conn, user_level)
            elif args.update:
                self.update_tag(event, args, conn, user_level)
            elif args.list:
                self.list_tags(event, args, conn, user_level)
            elif args.list_all:
                self.list_all_tags(event, args, conn, user_level)
            elif args.info:
                self.info_tag(event, args, conn, user_level)
            else:
                self.get_tag(event, args, conn, user_level)

        except sqlite3.OperationalError:
            self.log.info('First time running `!{}` command, creating new table in database'.format(event.name))
            event.msg.reply('[INFO] - First time running `!{}` command, creating new table in database'.format(event.name))
            c = conn.cursor()
            c.execute('create table tags (ID integer primary key, user_id integer, username text, name text, value text)')
            conn.commit()
            event.msg.reply('[INFO] - Table created. Please run your command again.')

        finally:
            conn.close()

    @Plugin.schedule(3600, init=False)      # sync exchange rates every hour
    def exchange_rate_sync(self):
        """Get latest exchange rates from fixer.io and save to json file."""
        self.log.info('Syncing latest exchange rates on fixer.io')

        with open('json/fixer_key.json') as f:
            fixer_key = json.load(f)

        url = 'http://data.fixer.io/api/latest?access_key={}'.format(fixer_key)
        r = requests.get(url)

        if not r.json()['success']:
            self.log.error('exchange_rate_sync ERROR: {}, code: {}\nDescription: {}'.format(r.json()['error']['type'], r.json()['error']['code'], r.json()['error']['info']))
            return

        with open('json/exch_rates.json', 'w') as f:
            json.dump(r.json(), f)

        return True

    @Plugin.command('exchange', aliases=['ex'], parser=True)
    @Plugin.add_argument('amount', type=float, nargs='?')
    @Plugin.add_argument('base', nargs='?')
    @Plugin.add_argument('target', nargs='?')
    def exchange_command(self, event, args):
        """= exchange =
        Convert currency with current exchange rates (Exchange rates updated hourly)
        usage    :: !exchange AMOUNT FROM TO
        aliases  :: ex
        category :: Utilities
        == Arguments
        AMOUNT :: The amount of money to convert
        FROM   :: The currency to convert *from*
        TO     :: The currency to convert *to*
        == Constraints
        AMOUNT :: Must be a positive number
        == Examples
        !exchange 1.50 USD JPY `Converts from freedom units to glorious nippon 円'
        !exchange 10 EUR GBP `Converts Euros to British Pounds'
        !exchange 3.50 usd aud `Lowercase works too (btw that is dollars to dollary-doos)'
        == Supported Currencies
        Run !exchange with no arguments to get a list
        of all available currencies
        """
        try:
            with open('json/exch_rates.json') as f:
                rates = json.load(f)
        except IOError:
            if self.exchange_rate_sync('json/exch_rates.json'):
                with open('json/exch_rates.json') as f:
                    rates = json.load(f)
            else:
                return

        if not any(arg for arg in vars(args).values()):
            event.msg.reply('Available currencies: ```{}```'.format(', '.join(sorted(rates['rates'].keys()))))
            return
        elif all(arg for arg in vars(args).values()):
            pass
        else:
            self.log.error('{} ran !exchange with only partial arguments'.format(event.author))
            return

        if args.amount <= 0:
            self.log.error('{} tried converting currency with non positive number: {}'.format(event.author, args.amount))
            return

        args.base, args.target = args.base.upper(), args.target.upper()

        try:
            eur_to_target = rates['rates'][args.target]
            eur_to_base = rates['rates'][args.base]
            result = eur_to_target/eur_to_base * args.amount
        except KeyError:
            if args.base == 'EUR':
                result = rates['rates'][args.target] * args.amount
            elif args.target == 'EUR':
                result = (1.0/rates['rates'][args.base]) * args.amount
            else:
                self.log.error('{} used invalid currency. Args: {}'.format(event.author, args))
                event.msg.reply('Invalid or unsupported currency')
                return

        if args.base not in rates['rates']:
            self.log.error('{} used invalid `from` currency: {}'.format(event.author, args.base))
            return

        if args.target not in rates['rates']:
            self.log.error('{} used invalid `to` currency: {}'.format(event.author, args.target))
            return

        event.msg.reply('{} {} = {:.2f} {}'.format(args.amount, args.base, result, args.target))

    @Plugin.command('timezone', aliases=['tz', 'time'], parser=True)
    @Plugin.add_argument('dt', nargs='*')
    @Plugin.add_argument('-tz', '--timezone')
    def timezone_command(self, event, args):
        """= timezone =
        Get current time of server or convert server time to a different timezone
        usage    :: !timezone [DATETIME] [-tz TIMEZONE]
        aliases  :: tz
        category :: Utilities
        == Datetime Syntax
        Datetimes are pretty flexible, anything sane should work
        You can see some examples below
        == Examples
        !timezone `Gets current Arabella time'
        !timezone 8pm -tz Europe/London `Convert 8pm Arabella time to london timezone'
        !timezone april 20th 1984 -tz UTC `Returns datetime in UTC timezone'
        """
        now = pendulum.now().in_tz('America/New_York')
        if not args.dt and not args.timezone:
            event.msg.reply('It is currently: {}'.format(now.format('LLLL zz')))
            return

        if not all(arg for arg in vars(args).values()):
            self.log.error('{} used !timezone with partial args: {}'.format(event.author, args))
            return

        dt = dateutil.parser.parse(' '.join(args.dt))
        dt = pendulum.instance(dt, 'America/New_York')
        try:
            new_dt = dt.in_tz(args.timezone)
            event.msg.reply(new_dt.format('LLLL zz'))
        except (pendulum.tz.zoneinfo.exceptions.InvalidTimezone, Exception), e:
            self.log.error('{} got error using !timezone\n{}'.format(event.author, e))
            self.log.info('Args for error above: {}'.format(args))

    @Plugin.command('weather', aliases=['wg'], parser=True)
    @Plugin.add_argument('state', nargs=1)
    @Plugin.add_argument('city', nargs='+')
    def weather_command(self, event, args):
        """= weather =
        Get current weather from somewhere
        usage    :: !weather STATE CITY
        aliases  :: wg
        category :: Utilities
        == Examples
        !weather ny new york `Get current weather in New York City'
        !weather ca los angeles `Get current weather in LA'
        !weather japan tokyo `Get current weather in 東京'
        """
        self.log.info('{} executed !weather with args: {}'.format(event.author, args))
        state = args.state[0]
        city = ' '.join(args.city)

        with open('json/wunderground_key.json') as f:
            key = json.load(f)
            
        base_url = 'http://api.wunderground.com/api/{key}/conditions/q/{state}/{city}.json' # state can also be a country
        self.log.info('weather request to {}'.format(base_url.format(state=state, city=city, key=key)))
        r = requests.get(base_url.format(state=state, city=city, key=key))

        try:
            weather = r.json()['current_observation']
            display_state = weather['display_location']['state_name']
            display_city = weather['display_location']['city']
            forecast_url = weather['forecast_url']
            icon_url = weather['icon_url']
            precip = weather['precip_today_string']
            temp_c = weather['temp_c']
            temp_f = weather['temp_f']
            condition = weather['weather']
            wind_dir = weather['wind_dir']
            wind_mph = weather['wind_mph']
            wind_kph = weather['wind_kph']
        except KeyError, e:
            self.log.error('Invalid query')
            return

        embed = MessageEmbed()
        embed.set_author(name='Wunderground', url='http://www.wunderground.com', icon_url='http://icons.wxug.com/graphics/wu2/logo_130x80.png')
        embed.title = '{}, {}'.format(display_state, display_city)
        embed.url = forecast_url
        embed.description = condition
        embed.add_field(name='Temperature', value='{}° F ({}° C)'.format(temp_f, temp_c), inline=True)
        embed.add_field(name='Precipitation', value=precip, inline=True)
        embed.add_field(name='Wind', value='From the {} at {}mph ({}kph)'.format(wind_dir, wind_mph, wind_kph), inline=True)
        embed.timestamp = pendulum.now().in_tz('America/New_York').isoformat()
        embed.set_thumbnail(url=icon_url)
        embed.set_footer(text='Powered by Weather Underground')
        embed.color = '2189209' # dark blue (hex: #216799)

        event.msg.reply(embed=embed)

    @Plugin.listen('GuildMemberAdd')
    def on_guild_join(self, guild_member):
        if guild_member.guild_id != 414960415018057738:
            return

        self.log.info(u'{} joined {}'.format(guild_member.name, guild_member.guild.name))

        if guild_member.id in self.secret_staff:
            self.log.info('Adding to secret staff')
            role_obj = guild_member.guild.roles.get(441703257107202050) # secret staff player role
        else:
            role_obj = guild_member.guild.roles.get(441659643408678932) # normal player role

        guild_member.add_role(role_obj)
        self.log.info(u'Added {} to {} role'.format(guild_member.name, role_obj.name))
