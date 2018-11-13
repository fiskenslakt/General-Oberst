# -*- coding: utf-8 -*-
# This code is real bad, it was early in development when I was still
# learning how to use the library. I haven't had the time to go back
# and fix it, so for now please look away...

import time
import inspect

from disco.bot import Plugin


class HelpPlugin(Plugin):
    secret_commands = [
        'foo',
        'someone',
        'test',
        'strawpoll',
        'add',
        'delete',
        'update',
        'list',
        'get',
        'is_voice_channel',
        'on_message_create',
        'on_guild_join',
        'jeopardy',
        'qr',
    ]

    @Plugin.command('help', '[cmd:str]')
    def help_command(self, event, cmd=None):
        """= help =
        Displays all available commands
        usage    :: !help [command]
        aliases  :: None
        category :: Help
        """
        plugins_list = [
            self.bot.plugins.get('InfoPlugin'),
            self.bot.plugins.get('FunPlugin'),
            self.bot.plugins.get('UtilitiesPlugin'),
            self.bot.plugins.get('HelpPlugin'),
            self.bot.plugins.get('MinecraftPlugin'),
            # self.bot.plugins.get('VoicePlugin'),
        ]

        if cmd is None:
            categories = {}
            all_commands = []

            for plugin in plugins_list:
                categories[plugin.__class__.__name__] = [
                    (command.name, inspect.cleandoc(command.get_docstring()).splitlines()[1])
                    for command in plugin.commands if command.name not in self.secret_commands
                ]
                all_commands += [
                    command.name
                    for plugin in plugins_list
                    for command in plugin.commands
                    if command not in self.secret_commands
                ]

            help_msg = '= Command List =\n\n[Use !help <command> for details]\n\n'
            
            for category, commands in categories.iteritems():
                help_msg += '== {} ==\n'.format(category.replace('Plugin', ''))

                for command in commands:
                    help_msg += '!{:{align}{width}} :: {}\n'.format(command[0], command[1], align='<', width=str(len(max(all_commands, key=len))))

                help_msg += '\n'

            r = event.msg.reply('```asciidoc\n{}\n```'.format(help_msg))

        else:
            for plugin in plugins_list:
                for method_name, obj in inspect.getmembers(plugin, predicate=inspect.ismethod):
                    if cmd in method_name and inspect.getdoc(obj) is not None:
                        help_msg = inspect.getdoc(obj)
                        break
                else:
                    continue
                break
            else:
                return

            r = event.msg.reply('```asciidoc\n{}\n```'.format(help_msg))

        if not event.channel.is_dm:
            time.sleep(60)
            r.delete()
            event.msg.delete()
