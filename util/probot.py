"""The bot's ProBot subclass module, to operate the whole bot."""
import asyncio
from math import floor
import discord.ext.commands as commands
from discord.ext.commands.bot import Context, StringView, CommandError, CommandNotFound
from cleverbot import Cleverbot
from properties import bot_name as bname
from util.datastore import get_cmdfix, get_prop, set_prop, write, dump
import util.ranks as rank

class ProBot(commands.Bot):
    """The brain of the bot, ProBot."""

    auto_convo_starters = [
        'do', 'oh',
        'are', 'you',
        'u', 'ur',
        'ready', 'begin',
        'lets',
        'go',
        'p',
        'can',
        'could',
        'would',
        'will',
        'hi',
        'hello',
        'hey',
        'heya',
        'hoi',
        'what',
        'wot',
        'wut',
        'shut',
        'watch',
        'behave',
        'test',
        'testing',
        'stop',
        'stahp',
        'ask',
        'ho',
        'um',
        'uh',
        'y',
        'tell',
        'gre',
        'why',
        'd'
    ]
    cnf_fmt = '{0.mention} The command you tried to execute, `{2}{1}`, does not exist. Type `{2}help` for help.'
    npm_fmt = '{0.mention} Sorry, the `{2}{1}` command does not work in DMs. Try a channel.'
    ccd_fmt = '{0.mention} Sorry, the `{2}{1}` command is currently disabled. Try again later!'
    cpe_fmt = '{0.mention} Sorry, you don\'t have **permission** to execute `{2}{1}`!'
    ece_fmt = '{0.mention} Hey, we don\'t have empty commands here! Try `{2}help` instead of `{2}` for help.'

    def __init__(self, **kwargs):
        self.cb = Cleverbot()
        super().__init__(**kwargs)
        self.is_restart = False
        self.loop = asyncio.get_event_loop()
        self.auto_convos = []

    async def sctx(self, ctx, msg):
        """Send a message to the context's message origin.'"""
        self.send_message(ctx.message.channel, msg)

    async def askcb(self, query):
        """A method of querying Cleverbot safe for async."""
        blocking_cb = self.loop.run_in_executor(None, self.cb.ask, query)
        return await blocking_cb

    async def on_command_error(self, exp, ctx):
        cmdfix = await get_cmdfix(ctx.message)
        cproc = ctx.message.content.split(' ')[0]
        cprocessed = cproc[len(cmdfix):]
        print(ctx.message.server.id + ': ' + str(type(exp)) + ' - ' + str(exp))
        if isinstance(exp, commands.CommandNotFound):
            await self.send_message(ctx.message.channel, self.cnf_fmt.format(ctx.message.author, cprocessed, cmdfix))
        elif isinstance(exp, commands.NoPrivateMessage):
            await self.send_message(ctx.message.channel, self.npm_fmt.format(ctx.message.author, cprocessed, cmdfix))
        elif isinstance(exp, commands.DisabledCommand):
            await self.send_message(ctx.message.channel, self.ccd_fmt.format(ctx.message.author, cprocessed, cmdfix))
        elif isinstance(exp, commands.CommandInvokeError):
            if str(exp).startswith('Command raised an exception: CommandPermissionError: '):
                await self.send_message(ctx.message.channel, self.cpe_fmt.format(ctx.message.author, cprocessed, cmdfix))
            else:
                await self.send_message(ctx.message.channel, 'An internal error has occured!```' + str(exp) + '```')
        else:
            await self.send_message(ctx.message.channel, 'An internal error has occured!```' + str(exp) + '```')

    async def casein(self, substr, clist):
        """Return if a substring is found in any of clist."""
        for i in clist:
            if substr in i:
                return True
        return False

    def bdel(self, s, r): return s[len(r):]

    async def auto_cb_convo(self, msg, kickstart):
        """The auto conversation manager."""
        absid = msg.server.id + msg.channel.id + msg.author.id
        if absid not in self.auto_convos:
            await self.send_typing(msg.channel)
            self.auto_convos.append(absid)
            lmsg = msg.content.lower()
            reply = lmsg
            reply_bot = await self.askcb(self.bdel(lmsg, kickstart + ' '))
            await self.send_message(msg.channel, msg.author.mention + ' ' + reply_bot)
            while await self.casein('?', [reply_bot, reply]):
                rep = await self.wait_for_message(author=msg.author)
                reply = rep.content
                reply_bot = await self.askcb(reply)
                await self.send_message(msg.channel, msg.author.mention + ' ' + reply_bot)
            self.auto_convos.remove(absid)

    async def on_message(self, msg):
        cmdfix = await get_cmdfix(msg)
        try:
            myself = msg.server.me
        except AttributeError:
            myself = self.user
        if msg.author.id != myself.id:
            if not msg.author.bot:
                if not msg.channel.is_private:
                    int_name = await get_prop(msg, 'bot_name')
                    if msg.server.me.display_name != int_name:
                        await self.change_nickname(msg.server.me, int_name)
                    if not msg.content.startswith(cmdfix):
                        prof_name = 'profile_' + msg.server.id
                        prof = await get_prop(msg, prof_name)
                        prof['exp'] += 1
                        new_level = rank.xp_level(prof['exp'])[0]
                        if new_level > prof['level']:
                            await self.send_message(msg.channel, '**Hooray!** {0.mention} has just *advanced to* **level {1}**! Nice! Gotta get to **level {2}** now! :stuck_out_tongue:'.format(msg.author, str(new_level), str(new_level + 1)))
                        prof['level'] = new_level
                        await set_prop(msg, 'by_user', prof_name, prof)
                if myself in msg.mentions:
                    await self.auto_cb_convo(msg, self.user.mention)
                elif msg.channel.is_private:
                    if msg.content.split('\n')[0] == cmdfix:
                        await self.send_typing(msg.channel)
                        await self.send_message(msg.channel, self.ece_fmt.format(msg.author, '', cmdfix))
                    elif msg.content.startswith(cmdfix):
                        await self.send_typing(msg.channel)
                        await self.sprocess_commands(msg, cmdfix)
                    else:
                        await self.send_typing(msg.channel)
                        cb_reply = await self.askcb(msg.content)
                        await self.send_message(msg.channel, ':speech_balloon: ' + cb_reply)
                elif msg.content.lower().startswith(bname.lower() + ' '):
                    nmsg = self.bdel(msg.content.lower(), bname.lower())
                    for i in self.auto_convo_starters:
                        if nmsg.startswith(' ' + i):
                            await self.auto_cb_convo(msg, bname.lower() + ' ')
                        elif nmsg.endswith('?'):
                            await self.auto_cb_convo(msg, bname.lower() + ' ')
                        elif nmsg.startswith(', '):
                            await self.auto_cb_convo(msg, bname.lower() + ', ')
                        elif nmsg.startswith('... '):
                            await self.auto_cb_convo(msg, bname.lower() + '... ')
                else:
                    if msg.content.split('\n')[0] == cmdfix:
                        await self.send_typing(msg.channel)
                        await self.send_message(msg.channel, self.ece_fmt.format(msg.author, '', cmdfix))
                    elif msg.content.startswith(cmdfix):
                        await self.send_typing(msg.channel)
                        await self.sprocess_commands(msg, cmdfix)

    async def sprocess_commands(self, message, prefix):
        """|coro|
        This function processes the commands that have been registered
        to the bot and other groups. Without this coroutine, none of the
        commands will be triggered.
        By default, this coroutine is called inside the :func:`on_message`
        event. If you choose to override the :func:`on_message` event, then
        you should invoke this coroutine as well.
        Warning
        --------
        This function is necessary for :meth:`say`, :meth:`whisper`,
        :meth:`type`, :meth:`reply`, and :meth:`upload` to work due to the
        way they are written. It is also required for the :func:`on_command`
        and :func:`on_command_completion` events.
        Parameters
        -----------
        message : discord.Message
            The message to process commands for.
        prefix : str
            Command prefix to use in context.
        """
        view = StringView(message.content)
        view.skip_string(prefix)
        cmd = view.get_word()
        tmp = {
            'bot': self,
            'invoked_with': cmd,
            'message': message,
            'view': view,
            'prefix': prefix
        }
        ctx = Context(**tmp)
        del tmp

        if cmd in self.commands:
            command = self.commands[cmd]
            self.dispatch('command', command, ctx)
            try:
                await command.invoke(ctx)
            except CommandError as exp:
                ctx.command.dispatch_error(exp, ctx)
            else:
                self.dispatch('command_completion', command, ctx)
        else:
            exc = CommandNotFound('Command "{}" is not found'.format(cmd))
            self.dispatch('command_error', exc, ctx)
