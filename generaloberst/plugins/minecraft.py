import requests

from cStringIO import StringIO

from disco.bot import Plugin
from disco.types.message import MessageEmbed


class MinecraftPlugin(Plugin):
    @staticmethod
    def get_mc_uuid(ign):
        url = 'https://api.mojang.com/users/profiles/minecraft/{}'.format(ign)
        r = requests.get(url)
        try:
            mc_uuid = r.json()['id']
        except ValueError:
            return
        else:
            return mc_uuid

    @Plugin.command('wiki', '[query:str...]')
    def wiki_command(self, event, query=None):
        """= wiki =
        Search minecraft wiki
        usage    :: !wiki [QUERY...]
        aliases  :: None
        category :: Minecraft
        == Examples
        !wiki `Return link to minecraft wiki'
        !wiki anvil `Searches wiki for anvil'
        !wiki armor stand `Searches wiki for armor stand'
        """
        base_url = 'https://minecraft.gamepedia.com'

        if query is None:
            event.msg.reply(base_url)
            return

        url = 'http://minecraft.gamepedia.com/index.php?title=Special:Search&search={}'
        r = requests.get(url.format(query))

        if 'search' in r.url:
            self.log.error('{} failed search to wiki with query: {}'.format(event.author, query))
            self.log.error('returned url: {}'.format(r.url))
            event.msg.reply('No results - Try searching yourself: {}'.format(base_url))
        else:
            event.msg.reply(r.url)

    @Plugin.command('player', aliases=['pl'], parser=True)
    @Plugin.add_argument('ign')
    @Plugin.add_argument('-s', '--skin', action='store_true')
    @Plugin.add_argument('-b', '--body', action='store_true')
    @Plugin.add_argument('-h', '--head', action='store_true')
    @Plugin.add_argument('-a', '--avatar', action='store_true')
    def player_command(self, event, args):
        """= player =
        Get player's skin
        usage    :: !player <IGN> [-s] [-b] [-h] [-a]
        aliases  :: pl
        category :: Minecraft
        == Arguments
        IGN :: Must be the exact username of the player (in game name)
        == Flags
        -s/--skin   :: Player skin
        -b/--body   :: 3D render of player's body
        -h/--head   :: 3D render of player's head
        -a/--avatar :: 2D render of player's head
        == Example
        !player notch -b ``Displays 3D render of notch's body''
        """
        mc_uuid = self.get_mc_uuid(args.ign)

        if mc_uuid is None:
            self.log.error('ign "{}" not found'.format(args.ign))
            event.msg.reply('The user "{}" doesn\'t exist'.format(args.ign))
            return

        base_url = 'https://crafatar.com/'

        if args.skin:
            img = base_url + 'skins/{}?helm'.format(mc_uuid)
        elif args.body:
            img = base_url + 'renders/body/{}?helm'.format(mc_uuid)
        elif args.head:
            img = base_url + 'renders/head/{}?helm'.format(mc_uuid)
        elif args.avatar:
            img = base_url + 'avatars/{}?helm'.format(mc_uuid)
        else:
            img = base_url + 'renders/body/{}?helm'.format(mc_uuid)

        r = requests.get(img)
        f = StringIO(r.content)
        
        event.msg.reply(attachments=[('{}.png'.format(mc_uuid), f)])
        f.close()

    @Plugin.command('server', '[IP:str]')
    def server_command(self, event, IP=None): # change default to retro
        """= server =
        Gets server info
        usage    :: !server [IP]
        aliases  :: None
        category :: Minecraft
        == Arguments
        IP :: The server's IP address
        == Examples
        !server `Gets server info for retro (default)'
        !server c.nerd.nu `Gets server info for reddit creative server'
        """
        if IP is None and event.guild.id == 414960415018057738: # Retro
            IP = 'Retro.serv.nu'

        if IP is None:
            return
        
        url = 'https://use.gameapis.net/mc/query/info/{}'.format(IP)
        banner_url = 'https://use.gameapis.net/mc/query/banner/{}'.format(IP)

        r = requests.get(url)

        try:
            server_version = r.json()['version']
        except KeyError:
            self.log.error('{} got an error: {}'.format(event.author, r.json()['error']))
            event.msg.reply(r.json()['error'])
            return

        banner_img = requests.get(banner_url).content

        embed = MessageEmbed()
        embed.description = 'Version: {}'.format(server_version)
        embed.set_image(url=banner_url)

        event.msg.reply(embed=embed)

    @Plugin.command('status')
    def status_command(self, event):
        """= status =
        Gets status on Microsoft/Minecraft servers (WIP)
        usage    :: !status
        aliases  :: None
        category :: Minecraft
        """
        url = 'https://use.gameapis.net/mc/extra/status'
        r = requests.get(url)

        msg = '```'
        for server, status in r.json().items():
            msg += '{:>24}: {}\n'.format(server, status['status'])
        msg += '```'

        event.msg.reply(msg)
