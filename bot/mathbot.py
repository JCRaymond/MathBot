import discord as d
from discord.ext import commands as com

import json
import urllib.parse

import requests as r

from PIL import Image
from io import BytesIO

class dotdict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

with open('../config.json', 'r') as f:
    config = json.loads(f.read(), object_pairs_hook=dotdict)

bot = com.Bot(command_prefix=('$','!'))
delete_emoji = chr(10060)
newpalette = [128]*768
base_dm_url = 'https://discordapp.com/channels/@me/'
base_tex_url = 'https://latex.codecogs.com/png.latex?'
dpi = 150
dpistr = f'%5Cdpi%7B{dpi}%7D'

@bot.event
async def on_ready():
    global guild
    guild = d.utils.get(bot.guilds, name=config.server_name)
    print(f"Bot connected to {guild}")

@bot.command(aliases=['latex',''])
async def tex(ctx):
    if ctx.prefix != '$' or ctx.guild != guild:
        return
    author = ctx.author
    dm_url = base_dm_url + str(author.id) + '/'
    
    channel = ctx.channel 
    webhooks = await channel.webhooks()
    tex_hook = d.utils.get(webhooks, name='texhook')
    if tex_hook is None:
        tex_hook = await channel.create_webhook(name='texhook')

    message = ctx.message
    com, _, tex = message.content.partition(' ')
    quoted_tex = urllib.parse.quote(f'\color{{white}}{{{tex.strip()}}}', safe='')
    tex_url = base_tex_url + dpistr + quoted_tex

    resp = r.get(tex_url)
    if resp.status_code != 200:
        await message.delete()
        await tex_hook.send(
            f'Invalid Tex: {tex}',
            username=author.display_name,
            avatar_url=author.avatar_url
        )
        return

    buf = BytesIO(resp.content)
    texf = d.File(buf, filename=f'{author.id}.png')
    
    await message.delete()
    texmes_info = await tex_hook.send(
        username=author.display_name,
        avatar_url=author.avatar_url,
        file=texf
    )

@bot.event
async def on_raw_reaction_add(payload):
    if payload.event_type != 'REACTION_ADD':
        return
    payload_guild = await bot.fetch_guild(payload.guild_id)
    if payload_guild != guild:
        return
    emoji = payload.emoji.name
    if emoji is None:
        return
    react_mem = payload.member
    if emoji != delete_emoji or react_mem == guild.me:
        return
    channel = await bot.fetch_channel(payload.channel_id)
    if channel is None:
        return
    message = await channel.fetch_message(payload.message_id)
    if message is None:
        return
    if not message.author.bot:
        return
    attachments = message.attachments
    if len(attachments) == 0:
        if message.author.name != react_mem.display_name:
            return
        await message.delete()
        return
    picture = attachments[0]
    tex_id, _, _ = picture.filename.partition('.')
    try:
        tex_id = int(tex_id)
    except ValueError:
        return
    if react_mem.id != tex_id:
        return
    await message.delete()

bot.run(config.token)

