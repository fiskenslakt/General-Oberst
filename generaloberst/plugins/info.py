from datetime import datetime

from disco.bot import Plugin
from disco.types.message import MessageEmbed


embed = MessageEmbed()

embed.set_author(name='fiskenslakt#9545', icon_url='https://cdn.discordapp.com/avatars/170208380739256320/dcb3c939597392dc3208de3264ccfe58.png')
embed.title = 'Bot for Retro'
embed.description = 'This is a bot for Retro for various moderation tasks. There are also commands for purely entertainment purposes. If you have a feature in mind that you would like added, post it to #meta'
embed.add_field(name='Made with:', value='Python', inline=True)
embed.add_field(name='Library:', value='Disco', inline=True)
embed.add_field(name='Made by:', value='Fiskenslakt', inline=False)
embed.timestamp = datetime.utcnow().isoformat()
embed.set_thumbnail(url='https://i.imgur.com/uddZWLw.png')
embed.set_footer(text='Generaloberst Bot v0.13.0')
embed.color = '10038562'

class InfoPlugin(Plugin):
    @Plugin.command('info', aliases=['about'])
    def info_command(self, event):
        """= info =
        Displays information about bot
        usage    :: !info
        aliases  :: !about
        category :: Info
        """
        event.msg.reply(embed=embed)
