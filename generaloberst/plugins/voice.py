import sqlite3

from cStringIO import StringIO

from google.cloud import texttospeech

from disco.bot import Plugin
from disco.bot.command import CommandLevels
from disco.voice.client import VoiceClient, VoiceState, VoiceException
from disco.voice.player import Player
from disco.voice.playable import OpusFilePlayable, FFmpegInput, BufferedOpusEncoderPlayable
from disco.util.logging import LoggingClass

class VoicePlugin(Plugin):
    voice_client = {}

    # @staticmethod
    def is_voice_channel(self):
        # self.log.info('Inside is_voice_channel')
        server_id = self.guild.id
        try:
            conn = sqlite3.connect('db/{}.db'.format(server_id), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            c = conn.cursor()
            text_channel_id, voice_channel_id = c.execute('select * from voice').fetchone()

            # print 'voice states:'
            # self.log.info(self.state.voice_states)
            # if not self.state.me.id in [i.user_id for i in event.guild.voice_states.values()]:
            #     return
            return self.channel.id == text_channel_id
        except (sqlite3.OperationalError, TypeError), e:
            LoggingClass().log.warning('Exception raised in voice.VoicePlugin.is_voice_channel: {}'.format(e))
            return
        finally:
            conn.close()

    @Plugin.listen('MessageCreate', conditional=is_voice_channel)
    def on_message_create(self, event):
        self.log.info('Synthesizing: {}'.format(event.content))

        # server_id = event.guild.id
        # try:
        #     conn = sqlite3.connect('db/{}.db'.format(server_id), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        #     c = conn.cursor()
        #     voice_channel_id = c.execute('select voice_channel from voice').fetchone()[0]
        # except sqlite3.OperationalError, e:
        #     self.log.error(e)
        # finally:
        #     conn.close()

        # voice_channel = event.guild.channels.get(voice_channel_id)
        # voice_client = VoiceClient(voice_channel)
        self.log.info('Attempting to connect to voice channel')
        voice_client = self.voice_client['client']
        self.log.info('Connected to voice channel')

        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.types.SynthesisInput(text=event.content)

        voice = texttospeech.types.VoiceSelectionParams(
            language_code='en-US-Wavenet-E',
            ssml_gender=texttospeech.enums.SsmlVoiceGender.MALE)

        audio_config = texttospeech.types.AudioConfig(
            audio_encoding=texttospeech.enums.AudioEncoding.MP3)

        # audio_config = texttospeech.types.AudioConfig(
        #     audio_encoding=texttospeech.enums.AudioEncoding.OGG_OPUS)

        response = client.synthesize_speech(synthesis_input, voice, audio_config)
        # f = OpusFilePlayable(response.audio_content)
        # voice_player = Player(voice_client)
        # voice_player.play(f)
        # f = StringIO(response.audio_content)
        self.log.info('Synthesized, writing file now')
        with open('audio/output.mp3', 'wb+') as f:
            self.log.info('File open')
            f.write(response.audio_content)
            self.log.info('wrote contents')
        audio = FFmpegInput('audio/output.mp3').pipe(BufferedOpusEncoderPlayable)
        self.log.info('ffmpeg done')
        voice_player = Player(voice_client)
        self.log.info('created player')
        voice_player.play(audio)
        self.log.info('executed play(audio)')

        # with open('audio/output.mp3', 'rb') as f:
        #     audio = FFmpegInput(f).pipe(BufferedOpusEncoderPlayable)
        #     voice_player = Player(voice_client)
        #     voice_player.play(audio)

    @Plugin.command('voice', parser=True)
    @Plugin.add_argument('--on', action='store_true')
    @Plugin.add_argument('--off', action='store_true')
    @Plugin.add_argument('-s', '--set', nargs=2, type=int)
    def voice_command(self, event, args):
        """= voice =
        Control panel for text-to-speech synthesizer
        usage    :: !voice [--on] [--off] [-s/--set snowflake snowflake]
        aliases  :: None
        category :: Voice
        == Note
        snowflake :: This is the ID of a channel, if you don't know how to get this, go here:
                  :: https://support.discordapp.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-
        == Examples
        !voice `Shows currently set channels'
        !voice --set 441753440209731584 441753474208628736 `Sets first ID to be text channel for synthesizing and second ID for voice channel to speak in'
        !voice -s 441753440209731584 441753474208628736 `Equivalent to previous example'
        !voice --on `Connects bot to voice channel'
        !voice --off `Disconnects bot from voice channel'
        """
        server_id = event.guild.id
        user_level = self.bot.get_level(event.author)

        if args.set and user_level < CommandLevels.MOD:
            self.log.error('{} tried setting voice channels'.format(event.author))
            event.msg.reply('You don\'t have permission to do that')
            return

        if sum(map(bool, vars(args).values())) > 1:
            self.log.error('{} tried using !voice with too many args'.format(event.author))
            return

        try:
            conn = sqlite3.connect('db/{}.db'.format(server_id), detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            c = conn.cursor()

            if sum(map(bool, vars(args).values())) == 0:
                if c.execute('select count(*) from voice').fetchone()[0] == 0:
                    event.msg.reply('No channels set yet')
                else:
                    voice_channel_id = c.execute('select voice_channel from voice').fetchone()[0]
                    voice_channel = event.guild.channels.get(voice_channel_id)
                    text_channel_id = c.execute('select text_channel from voice').fetchone()[0]
                    text_channel = event.guild.channels.get(text_channel_id)
                    if voice_channel:
                        voice_channel = voice_channel.name
                    if text_channel:
                        text_channel = text_channel.name

                    event.msg.reply('Text Channel: {}, Voice Channel: {}'.format(text_channel, voice_channel))
                    return

            if args.on:
                if c.execute('select count(*) from voice').fetchone()[0] == 0:
                    self.log.error('{} tried turning voice on but channels aren\'t set yet'.format(event.author))
                    event.msg.reply('You have to set the channels first')
                    return
                try:
                    voice_channel_id = c.execute('select voice_channel from voice').fetchone()[0]
                    voice_channel = event.guild.channels.get(voice_channel_id)
                    if voice_channel:
                        self.voice_client['client'] = voice_channel.connect()
                    else:
                        self.log.error('{} no longer exists'.format(voice_channel_id))
                        event.msg.reply('{} no longer exists'.format(voice_channel_id))
                        return
                except VoiceException, e:
                    self.log.error('{} | voice channel: {}'.format(e, voice_channel_id))

            elif args.off:
                # voice_channel_id = c.execute('select voice_channel from voice').fetchone()[0]
                # voice_channel = event.guild.channels.get(voice_channel_id)
                # VoiceClient(voice_channel).disconnect()
                self.voice_client['client'].disconnect()

            elif args.set:
                text_channel_id, voice_channel_id = args.set
                text_channel = event.guild.channels.get(text_channel_id)
                voice_channel = event.guild.channels.get(voice_channel_id)
                if text_channel and voice_channel:
                    if not voice_channel.is_voice:
                        self.log.error('Invalid voice channel - snowflake: {}'.format(voice_channel_id))
                        event.msg.reply('{} isn\'t a valid voice channel'.format(voice_channel_id))
                        return
                    else:
                        c = conn.cursor()
                        if c.execute('select count(*) from voice').fetchone()[0] == 0:
                            c.execute('insert into voice values (?,?)', (text_channel_id, voice_channel_id))
                            conn.commit()

                        c.execute('update voice set text_channel = ?, voice_channel = ?', (text_channel_id, voice_channel_id))
                        conn.commit()
                        self.log.info('{} set text channel to {} and voice channel to {}'.format(event.author, text_channel_id, voice_channel_id))
                        event.msg.reply('Successfully set channels')
                else:
                    self.log.error('One or both of {} and {} are not valid channels'.format(text_channel_id, voice_channel_id))
                    event.msg.reply('One or both of those channels are not valid')

        except sqlite3.OperationalError:
            self.log.info('First time running `!{}` command, creating new table in database'.format(event.name))
            event.msg.reply('[INFO] - First time running `!{}` command, creating new table in database'.format(event.name))
            c = conn.cursor()
            c.execute('create table voice (text_channel integer, voice_channel integer)')
            conn.commit()
            event.msg.reply('[INFO] - Table created. Please run your command again.')

        finally:
            conn.close()
