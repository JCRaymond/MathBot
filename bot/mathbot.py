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

bot = com.Bot(command_prefix='$')
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
    author = ctx.author
    dm_url = base_dm_url + str(author.id) + '/'
    
    channel = ctx.channel 
    webhooks = await channel.webhooks()
    tex_hook = d.utils.get(webhooks, name='texhook')
    if tex_hook is None:
        tex_hook = await channel.create_webhook(name='texhook')

    message = ctx.message
    com, _, tex = message.content.partition(' ')
    tex = urllib.parse.quote(tex.strip(), safe='')
    tex_url = base_tex_url + dpistr + tex

    resp = r.get(tex_url)
    if resp.status_code != 200:
        await message.delete()
        await tex_hook.send(
            'Invalid Tex',
            username=author.display_name,
            avatar_url=author.avatar_url
        )
        return

    #i = Image.open(BytesIO(resp.content))
    #i.putpalette(newpalette)
    #buf = BytesIO()
    #i.save(buf, format='PNG')
    #buf.seek(0)
    buf = BytesIO(resp.content)
    texf = d.File(buf, filename='tex.png')
    
    await message.delete()
    texmes = await tex_hook.send(
        username=author.display_name,
        avatar_url=author.avatar_url,
        file=texf
    )

@bot.event
async def on_raw_reaction_add(payload):
    if payload.event_type != 'REACTION_ADD':
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
    if message is None or message.author != guild.me:
        return
    embeds = message.embeds
    if len(embeds) == 0:
        return
    embed = embeds[0]
    try:
        poster_id = int(embed.author.url[len(base_dm_url):-1])
    except ValueError:
        return
    if poster_id != react_mem.id:
        return
    await message.delete()

bot.run(config.token)

