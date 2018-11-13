# -*- coding: utf-8 -*-

import string
import requests
import sqlite3
import time
import re
import json
import pendulum
import qrcode

from itertools import islice
from random import choice
from datetime import datetime
from cStringIO import StringIO

from disco.bot import Plugin
from disco.bot.command import CommandLevels
from disco.types.message import MessageEmbed
from disco.util import snowflake

from wand.image import Image
from wand.font import Font
from PIL import Image as pil_Image


class FunPlugin(Plugin):
    font = Font('Impact')

    @Plugin.command('convert', '<a:str> <b:str> <value:str...>')
    def convert_command(self, event, a, b, value):
        """= convert =
        Converts something to something else
        usage    :: !convert <from> <to> <thing to convert>
        aliases  :: None
        category :: Fun
        == Examples
        !convert text binary some example text
        !convert binary text 01100010 01101111 01110100
        !convert decimal binary 42
        !convert binary decimal 101010
        """
        if a == 'text' and b == 'binary':
            text = map(ord, value)
            binary = ' '.join([format(int(bin(n)[2:]),'08') for n in text])
            event.msg.reply(binary)

        elif a == 'binary' and b == 'text':
            binary = value.split()

            if len(binary) == 1:
                binary = binary[0]
                binary = [binary[byte:byte+8] for byte in range(0, len(binary), 8)]

            decimal = [int(n,2) for n in binary]
            text = ''.join(map(chr, decimal))
            event.msg.reply(text)

        elif a == 'binary' and b == 'decimal':
            binary = value.split()
            decimal = ' '.join([str(int(n,2)) for n in binary])
            event.msg.reply(decimal)

        elif a == 'decimal' and b == 'binary':
            decimal = map(int, value.split())
            binary = ' '.join([bin(n)[2:] for n in decimal])
            event.msg.reply(binary)

    @Plugin.command('caesar', '<rot:int> <msg:str...>')
    def caesar_command(self, event, rot, msg):
        """= caesar =
        Performs a simple caesar cipher
        usage    :: !caesar <rotation> <message>
        aliases  :: None
        category :: Fun
        == Constraints
        rotation :: Must be a number between -25 and +25
        == Examples
        !caesar 1 abc `=> bcd'
        !caesar -1 bcd `=> abc'
        !caesar 5 foo bar `=> ktt gfw'
        """
        event.msg.delete()

        if rot > 25 or rot < -25:
            return

        alpha = string.ascii_lowercase
        table = string.maketrans(alpha, alpha[rot:] + alpha[:rot])
        cipher = string.translate(str(msg).lower(), table)
        event.msg.reply('{} says: ```{}```'.format(event.member, cipher))

    @Plugin.command('foo')
    def foo_command(self, event):
        dm = event.author.open_dm()
        dm.send_message('foo')

    @Plugin.command('someone')
    def someone_command(self, event):
        members = event.guild.members.copy()

        # Don't mention self or user who triggered command
        del members[435938181750456322] # bot id
        del members[event.msg.author.id] # id of user who triggered command
        
        someone = choice(members.values()).user.mention
        event.msg.reply(someone)

    @Plugin.command('mock', parser=True)
    @Plugin.add_argument('--scroll', '-s', type=int)
    @Plugin.add_argument('--text', '-t', nargs='+')
    def mock_command(self, event, args):
        """= mock =
        Uses spongemock meme to mock someone's message or creates custom one
        usage    :: !mock [--scroll/-s <N> | --text/-t <custom text>]
        aliases  :: None
        category :: Fun
        == Defaults
        scroll :: 1
        == Constraints
        scroll :: Must be a number >=1 and <=100
        == Examples
        !mock `Will mock previous message, equivalent to !mock --scroll 1'
        !mock --scroll 2 ``Mock's 2nd to last message in channel''
        !mock -s2 `Equivalent to previous example'
        !mock -s 2 `Equivalent to previous example'
        !mock --text some example text `Creates custom mock'
        !mock -t some example text `Equivalent to previous example'
        """
        if args.text is None:
            if args.scroll is None:
                args.scroll = 1
                msg = next(islice(event.channel.messages_iter(direction='DOWN', before=event.msg.id), args.scroll-1, args.scroll))
                args.text = msg.content
            elif args.scroll < 1:
                return
            
            msg = next(islice(event.channel.messages_iter(direction='DOWN', before=event.msg.id), args.scroll-1, args.scroll))
            args.text = msg.content

        if isinstance(args.text, list):
            args.text = ' '.join(args.text)

        args.text = ''.join([choice([char, char.upper()]) for char in args.text.lower()])

        with Image(filename='images/mock.jpg') as original:
            img = original.clone()

        img.caption(text=args.text, top=810, left=10, width=1150, height=200, font=self.font, gravity='center')
        img.save(filename='images/last_mock.jpg')

        with open('images/last_mock.jpg', 'rb') as f:
            event.channel.send_message(attachments=[('last_mock.jpg', f)])

    @Plugin.command('coliru', aliases=['code', 'run'], parser=True)
    @Plugin.add_argument('lang', nargs='+') # This is a hack because the regex isn't matching the way I need it to
    def coliru_command(self, event, args):
        """= coliru =
        Executes and displays the output of code in a user's message using [http://coliru.stacked-crooked.com]
        usage    :: !coliru <py | python | c | cpp | haskell>
                 :: <code>
        aliases  :: code, run
        category :: Fun
        == Example
        !coliru python

        `​`​`py
        for i in range(3):
            print 'foobar'
        `​`​`
        == Notes
        Supported Languages: C++, C, Python, Haskell
        Anything else isn't supported
        The python support is only Python 2.7 (sorry python3 users)
        == More Info
        For more information on discord markdown syntax, go here:
        [https://support.discordapp.com/hc/en-us/articles/210298617-Markdown-Text-101-Chat-Formatting-Bold-Italic-Underline-]
        """
        lang = args.lang[0]     # args parses the entire message because I have to, so I grab just the first element
        output_msg = event.msg.reply('`Compiling...`')

        cmds = {
            'cpp': 'g++ -std=c++1z -O2 -Wall -Wextra -pedantic -pthread main.cpp -lstdc++fs && ./a.out',
            'c': 'mv main.cpp main.c && gcc -std=c11 -O2 -Wall -Wextra -pedantic main.c && ./a.out',
            'py': 'python main.cpp', # coliru has no python3
            'python': 'python main.cpp',
            'haskell': 'runhaskell main.cpp'
        }
        payload = {
            'cmd': cmds.get(lang),
            'src': '\n'.join(event.codeblock.splitlines()[1:])
        }
        if payload['cmd'] is None:
            msg = output_msg.edit('[ERROR] - Invalid language "{}"'.format(lang))
            time.sleep(15)
            msg.delete()
            return

        r = requests.post('http://coliru.stacked-crooked.com/compile', json=payload)
        if r.status_code != 200:
            output_msg.edit('Coliru did not respond in time')
            return

        output = r.text
        if len(output) < 1992 and len(output.splitlines()) <= 30:
            output_msg.edit(u'```\n{}\n```'.format(output))
        else:
            url = 'https://api.paste.ee/v1/pastes'

            with open('json/paste_ee.json') as f:
                header = json.load(f) # Auth Token

            payload = {'sections': [{'contents': output}]}
            r = requests.post(url, headers=header, json=payload)
            output_msg.edit('Pasting to `https://paste.ee` because output is too long: {}'.format(r.json()['link']))

    @Plugin.command('test')
    def test_command(self, event):
        self.client.api.channels_typing(event.channel.id)
        time.sleep(5)
        event.msg.reply('test typing')

    @Plugin.command('jpeg', aliases=['morejpeg', 'jpg', 'morejpg'], parser=True)
    @Plugin.add_argument('--scroll', '-s', type=int, default=1)
    @Plugin.add_argument('--quality', '-q', type=int, default=1)
    def jpeg_command(self, event, args):
        """= jpeg =
        Adds more jpeg to an image
        usage    :: !jpeg [--scroll/-s] [--quality/-q]
        aliases  :: morejpeg, jpg, morejpg
        category :: Fun
        == Defaults
        scroll  :: 1
        quality :: 1
        == Constraints
        scroll  :: Must be a number >=1 and <=100
        quality :: Must be a number >=1 and <=95
        == Examples
        !jpeg `Performs action on last message in channel with quality set to 1'
        !jpeg --scroll 2 `Performs action on 2nd to last message with quality set to 1'
        !jpeg -s 2 `Equivalent to previous example'
        !jpeg -s2 `Equivalent to previous example'
        !jpeg --quality 5 `Sets quality to 5'
        !jpeg -q5 `Equivalent to previous example'
        !jpeg -s2 -q5 `Performs action on 2nd to last message with quality as 5'
        """
        qt = args.quality

        if args.scroll < 1:
            return

        msg = next(islice(event.channel.messages_iter(direction='DOWN', before=event.msg.id), args.scroll-1, args.scroll))

        for attachment in msg.attachments.values():
            url = attachment.url

        r = requests.get(url)
        f = StringIO(r.content)

        with pil_Image.open(f) as img:
            img.load()

            try:
                background = pil_Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                background.save('images/last_jpeg.jpg', quality=qt)
            except IndexError:
                img.save('images/last_jpeg.jpg', 'JPEG', quality=qt)

        with open('images/last_jpeg.jpg', 'rb') as f:
            event.channel.send_message(attachments=[('last_jpeg.jpg', f)])

    @Plugin.command('drama', aliases=['nonsense'], parser=True)
    @Plugin.add_argument('action', nargs='?', choices=['alert', 'record', 'archive'])
    def drama_command(self, event, args):
        """= drama =
        Keeps track of the last time there was drama on the server
        usage    :: !drama [alert | record | archive]
        aliases  :: nonsense
        category :: Fun
        == Examples
        !drama `Will display when the last occurrence of drama happened'
        !drama record `Will display the record of most days without drama'
        !drama archive `Will display all recorded incidents of drama'
        !drama alert `Will declare that drama has just happened (STAFF ONLY)'
        """
        if event.channel.is_dm:
            event.msg.reply('This command only works in a server :/')
            return

        action = args.action
        server_id = event.guild.id
        # Use pendulum for timezone information
        today = pendulum.now(tz='America/New_York')
        # Convert to standard datetime so sqlite doesn't complain
        today = datetime(today.year, today.month, today.day, today.hour, today.minute, today.second)

        try:
            conn = sqlite3.connect('db/{}.db'.format(server_id), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            c = conn.cursor()

            if action is None:
                c.execute('select last_drama from drama')
                last_drama = c.fetchone()

                if last_drama is None:
                    event.msg.reply('There has never been any {}'.format(event.name))
                else:
                    last_drama = last_drama[0]
                    days_ago = (today.date() - last_drama.date()).days
                    event.msg.reply('Last time there was {} was {} {} ago on {:%x at %I:%M%p EST}'.format(event.name, days_ago, 'day' if days_ago == 1 else 'days', last_drama))

            elif action == 'record':
                if c.execute('select count(*) from drama').fetchone()[0] == 0:
                    event.msg.reply('There has never been any {}'.format(event.name))
                else:
                    c.execute('select * from drama')
                    record, last_drama = c.fetchone()
                    cur_record = (today.date() - last_drama.date()).days

                    record = max(record, cur_record)

                    event.msg.reply('{} {} {}'.format(
                        record,
                        'day' if record == 1 else 'days',
                        ':unamused:' if record <= 1 else ''
                    ))

            elif action == 'alert':
                user_level = self.bot.get_level(event.author)
                if user_level < CommandLevels.MOD:
                    event.msg.reply("You're not qualified to declare drama")
                    return

                if c.execute('select count(*) from drama').fetchone()[0] == 0: # First run in a server
                    if event.guild.id == 414960415018057738: # Retro
                        retro_opening = pendulum.datetime(2018, 6, 22, tz='America/New_York') # Retro opening day
                        start_date = datetime(retro_opening.year, retro_opening.month, retro_opening.day)
                        self.log.info('Detected drama in retro, using custom date instead of server creation')
                    else:
                        server_creation = pendulum.from_timestamp(snowflake.to_unix(event.guild.id), tz='America/New_York')
                        start_date = datetime(server_creation.year, server_creation.month, server_creation.day)

                    record = (today.date() - start_date.date()).days
                    c.execute('insert into drama values (?,?)', (record, start_date))
                    conn.commit()

                c.execute('select * from drama')
                record, last_drama = c.fetchone()
                cur_record = (today.date() - last_drama.date()).days
                new_record = max(record, cur_record)

                c.execute('update drama set record = ?, last_drama = ?', (new_record, today))
                c.execute('insert into drama_archive values (?)', (today,))
                conn.commit()

                event.msg.reply('Uh oh, {} alert :popcorn:\nThe peace lasted for {} {}. {}\n\n{}'.format(
                    event.name,
                    cur_record,
                    'day' if cur_record == 1 else 'days',
                    ':unamused:' if cur_record <= 1 else '',
                    'New record btw :clap:' if cur_record > record and record > 0 else ''
                ))

            elif action == 'archive':
                if c.execute('select count(*) from drama_archive').fetchone()[0] == 0:
                    event.msg.reply('There has never been any {}'.format(event.name))
                else:
                    incidents = c.execute('select count(*) from drama_archive').fetchone()[0]
                    r = '{} {} {}:\n'.format(incidents, 'Dramatic' if event.name == 'drama' else 'Nonsensical', 'event' if incidents == 1 else 'events')
                    c.execute('select incident from drama_archive')
                    for row in c:
                        r += '{:%x - %I:%M%p EST}\n'.format(row[0])
                    event.msg.reply(r)


        except sqlite3.OperationalError:
            event.msg.reply('[INFO] - First time running `!{}` command, creating new table in database'.format(event.name))
            c.execute('create table drama (record integer, last_drama timestamp)')
            c.execute('create table drama_archive (incident timestamp)')
            conn.commit()
            event.msg.reply('Table created. Please run your command again.')

        finally:
            conn.close()

    @staticmethod
    def clean_html(raw_html):
        """Cleans html tags from jeopardy questions
        that happen to have them.
        """
        p = re.compile('<.*?>')
        clean_text = re.sub(p, '', raw_html)
        return clean_text

    @Plugin.command('jeopardy', aliases=['j'], parser=True)
    @Plugin.add_argument('-r', '--random', action='store_true')
    def jeopardy_command(self, event, args):
        self.log.info('{} executed !jeopardy with args: {}'.format(event.author, args))
        
        if not args.random:
            return
        
        jservice_base_url = 'http://jservice.io/{}'
        jservice_random = '/api/random'
        jeopardy_response = requests.get(jservice_base_url.format(jservice_random)).json()[0]
        
        from pprint import pprint
        pprint(jeopardy_response)
        
        jeopardy_q = jeopardy_response['question'].replace('&', 'and')
        jeopardy_a = self.clean_html(jeopardy_response['answer'])
        jeopardy_id = jeopardy_response['id']
        jeopardy_amount = '${}'.format(jeopardy_response['value'])
        jeopardy_category = jeopardy_response['category']['title']

        jeopardy_q = '\n'.join([' '.join(jeopardy_q.split()[s:s+6]) for s in range(0, len(jeopardy_q.split()), 6)])

        self.log.info('amount: {}'.format(jeopardy_amount))

        img2txt_url = 'http://api.img4me.com/?text={}&font=impact&size=35&fcolor={}&bcolor=060CE9'
        question_color = 'FFFFFF'
        amount_color = 'D49516'
        question_value = requests.get(img2txt_url.format(jeopardy_q, question_color)).text
        amount_value = requests.get(img2txt_url.format(jeopardy_amount, amount_color)).text

        embed = MessageEmbed()
        embed.set_author(name='Jeopardy!', url='http://jservice.io/', icon_url='http://jservice.io/assets/trebek-503ecf6eafde622b2c3e2dfebb13cc30.png')
        embed.title = 'Category: {}'.format(jeopardy_category)
        embed.timestamp = pendulum.now().in_tz('America/New_York').isoformat()
        embed.set_thumbnail(url=amount_value)
        embed.set_image(url=question_value)
        embed.set_footer(text='Powered by jservice.io')
        embed.color = '13931798' # dark yellow (hex: #D49516)

        event.msg.reply(embed=embed)

    @Plugin.command('qr', '<text:str...>')
    def qr_command(self, event, text):
        event.msg.delete()
        img = qrcode.make(text)
        f = StringIO()
        img.save(f, img.format)
        code = f.getvalue()
        f.close()
        event.msg.reply(attachments=[('qrcode.png', code)])
