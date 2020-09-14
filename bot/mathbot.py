import discord as d
from discord.ext import commands as com

import json
import pickle
import urllib.parse
import subprocess as sp
import os
from math import ceil

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

class Courses:

    def __init__(self):
        self.math = []
        self.stat = []
        self.oprs = []
        self.requests = {}

DATNAME = "course.data"
coursedat = None

def persist_courses():
    with open(DATNAME, 'wb') as f:
        pickle.dump(coursedat,f)

if os.path.exists(DATNAME):
    with open(DATNAME, 'rb') as f:
        coursedat = pickle.load(f)

delete_emoji = chr(10060)
@bot.event
async def on_ready():
    global guild, coursedat
    guild = d.utils.get(bot.guilds, name=config.server_name)
    sp.run('mkdir -p .tex', shell=True)
    print(f"Bot connected to {guild}")
    if coursedat is None:
        print(f"Recovering courses from guild...")
        channels = await guild.fetch_channels()
        coursedat = Courses()
        math = d.utils.get(channels, name="MATH Courses")
        stat = d.utils.get(channels, name="STAT Courses")
        oprs = d.utils.get(channels, name="OPRS Courses")
        math_courses = [chan.name for chan in math.text_channels]
        stat_courses = [chan.name for chan in stat.text_channels]
        oprs_courses = [chan.name for chan in oprs.text_channels]
        math_courses = sorted(math_courses)
        stat_courses = sorted(stat_courses)
        oprs_courses = sorted(oprs_courses)
        coursedat.math = math_courses
        coursedat.stat = stat_courses
        coursedat.oprs = oprs_courses
        persist_courses()

    
tex_pagestart = r"""
\documentclass[preview,border={1pt,0pt,0pt,0pt}]{standalone}
\usepackage[margin=2.75in]{geometry}
\usepackage{amsmath}
\usepackage{amsthm}
\usepackage{amssymb}
\usepackage{xcolor}
\newcommand*{\Z}{\mathbb{Z}}
\newcommand*{\N}{\mathbb{N}}
\newcommand*{\R}{\mathbb{R}}
\newcommand*{\Q}{\mathbb{Q}}
\newcommand*{\F}{\mathbb{F}}
\newcommand*{\T}{\mathbb{T}}
\begin{document}
\nopagecolor
\color{white}{
"""

tex_pageend = r"""
}
\end{document}
"""

@bot.command(aliases=['tex'])
async def latex(ctx):
    if ctx.guild != guild:
        return
    if ctx.prefix != '$':
        return
    author = ctx.author
    
    channel = ctx.channel 
    webhooks = await channel.webhooks()
    tex_hook = d.utils.get(webhooks, name='texhook')
    if tex_hook is None:
        tex_hook = await channel.create_webhook(name='texhook')

    message = ctx.message
    com, _, tex = message.content.partition(' ')

    with open('.tex/render.tex', 'w') as f:
        f.write(tex_pagestart)
        f.write(tex)
        f.write(tex_pageend)

    with open(os.devnull, 'w') as devnull:
        rc = sp.run('./rendertex.sh', stdout=devnull, stderr=devnull)

    if rc.returncode != 0:
        await message.delete()
        await tex_hook.send(
            f'Invalid Tex: {tex}',
            username=author.display_name,
            avatar_url=author.avatar_url
        )
        async for mes in tex_hook.channel.history():
            if mes.author.bot and mes.author != guild.me:
                await mes.add_reaction(delete_emoji)
                return
        return

    with open('.tex/render.png', 'rb') as f:
        texf = d.File(f, filename=f'{author.id}.png')

    await message.delete()
    texmes_info = await tex_hook.send(
        username=author.display_name,
        avatar_url=author.avatar_url,
        file=texf
    )

base_tex_url = 'https://latex.codecogs.com/png.latex?'
dpi = 256
dpistr = f'%5Cdpi%7B{dpi}%7D'

@bot.command(aliases=[''])
async def math(ctx):
    if ctx.guild != guild:
        return
    if ctx.prefix != '$':
        return
    author = ctx.author
    
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
        async for mes in tex_hook.channel.history():
            if mes.author.bot and mes.author != guild.me:
                await add_reaction(delete_emoji)
                return
        return

    buf = BytesIO(resp.content)
    texf = d.File(buf, filename=f'{author.id}.png')
    
    await message.delete()
    await tex_hook.send(
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

def iter_all(*args):
    for arg in args:
        yield from arg

def find_pos(lst, elem):
    i = 0
    for item in lst:
        if elem > item:
            i+=1
        else:
            break
    return i

async def _addcourse(dep, num):
    cat_name = f'{dep.upper()} Courses'
    channels = await guild.fetch_channels()
    cat = d.utils.get(channels, name=cat_name)
    course_list = coursedat.__dict__[dep]
    course = f'{dep}-{num}'
    if course in course_list:
        return None
    pos = find_pos(course_list, course)
    course_list.insert(pos, course)
    roles = await guild.fetch_roles()
    mod = d.utils.get(roles, name='Moderator')
    overwrites = {
        mod: d.PermissionOverwrite(view_channel=True),
        guild.default_role: d.PermissionOverwrite(view_channel=False)
    }
    chan = await cat.create_text_channel(course, overwrites=overwrites)
    await chan.edit(position=pos)
    await chan.edit(position=pos)
    await chan.edit(position=pos)
    return chan

@bot.command(aliases=['createcourse',])
async def addcourse(ctx, *args):
    if ctx.guild != guild or ctx.prefix != '!':
        return
    mem = ctx.author
    Moderator = d.utils.get(mem.roles, name='Moderator')
    if Moderator is None:
        return
    if len(args) == 0 or len(args) >= 2 or len(args[0]) != 9:
        await ctx.channel.send(f'Usage: `!addcourse <course name>`. Course name must start with "math", "stat", or "oprs", followed by a dash, then 4 digits.')
        return
    course = args[0].lower()
    try:
        dep,num = course.split('-')
    except:
        await ctx.channel.send(f'Usage: `!addcourse <course name>`. Course name must start with "math", "stat", or "oprs", followed by a dash, then 4 digits.')
        return
    if dep != 'math' and dep != 'stat' and dep != 'oprs':
        await ctx.channel.send(f'Usage: `!addcourse <course name>`. Course name must start with "math", "stat", or "oprs", followed by a dash, then 4 digits.')
        return
    try:
        int(num)
    except ValueError:
        await ctx.channel.send(f'Usage: `!addcourse <course name>`. Course name must start with "math", "stat", or "oprs", followed by a dash, then 4 digits.')
        return
    channel = await _addcourse(dep, num)
    persist_courses()
    if channel == None:
        await ctx.channel.send(f'"{course.upper()}" already exists.')
        return
    channels = await guild.fetch_channels()
    bot_log = d.utils.get(channels, name='bot-log')
    await bot_log.send(f'{channel.mention} created by mod.')
    await ctx.channel.send(f'Successfully created channel {channel.mention}.')

@bot.command(aliases=['deletecourse',])
async def removecourse(ctx, *args):
    if ctx.guild != guild or ctx.prefix != '!':
        return
    Mod = d.utils.get(ctx.author.roles, name='Moderator')
    if Mod is None:
        return
    if len(args) == 0 or len(args) >= 2 or len(args[0]) != 9:
        await ctx.channel.send(f'Usage: `!deletecourse <course name>`. Course name must start with "math", "stat", or "oprs", followed by a dash, then 4 digits.')
        return
    course = args[0].lower()
    channels = await guild.fetch_channels()
    if course in coursedat.math:
        coursedat.math.remove(course)
        chan = d.utils.get(channels,name=course)
        await chan.delete()
    elif course in coursedat.stat:
        coursedat.stat.remove(course)
        chan = d.utils.get(channels,name=course)
        await chan.delete()
    elif course in coursedat.oprs:
        coursedat.oprs.remove(course)
        chan = d.utils.get(channels,name=course)
        await chan.delete()
    else:
        await ctx.channel.send(f'That course does not exist.')
        return
    try:
        await ctx.channel.send(f'Deleted course {course.upper()}.')
    except:
        pass
    bot_log = d.utils.get(channels, name='bot-log')
    await bot_log.send(f'{course.upper()} deleted by mod.')
    persist_courses()

@bot.command()
async def dropuser(ctx, *args):
    if ctx.guild != guild or ctx.prefix != '!':
        return
    Mod = d.utils.get(ctx.author.roles, name = 'Moderator')
    if Mod is None:
        return
    if len(args) < 2:
        await ctx.channel.send(f'Usage: `!dropuser <course name> @mention1 [@mention2 ...]`. Must be existing course name, and valid mention to user.')
        return
    course = args[0].lower()
    try:
        dep, num = course.split('-')
    except:
        await ctx.channel.send(f'Usage: `!dropuser <course name> @mention1 [@mention2 ...]`. Must be existing course name, and valid mention to user.')
        return
    if dep != 'math' and dep != 'stat' and dep != 'oprs':
        await ctx.channel.send(f'Usage: `!dropuser <course name> @mention1 [@mention2 ...]`. Must be existing course name, and valid mention to user.')
        return
    course_list = coursedat.__dict__[dep]
    if course not in course_list:
        await ctx.channel.send(f'Usage: `!dropuser <course name> @mention1 [@mention2 ...]`. Must be existing course name, and valid mention to user.')
        return
    channels = await guild.fetch_channels()
    chan = d.utils.get(channels,name=course)
    ow = chan.overwrites
    for mem in ctx.message.mentions:
        if mem in ow:
            del ow[mem]
    await chan.edit(overwrites=ow)

@bot.command()
async def drop(ctx, *args):
    if ctx.guild != guild or ctx.prefix != '!':
        return
    if ctx.channel.name != 'terminal':
        return
    if len(args) == 0:
        await ctx.channel.send(f'{ctx.author.mention}, to drop a course, look through the existing courses using the `!courses` command, and enter `!drop <course name>` to leave the channel for that course. You may also drop all courses with `!drop all`, or all MATH courses with `!drop math` (the same goes for STAT and OPRS courses). Example: `!drop math1241` or `!drop oprs`.')
        return
    if len(args) >= 2 and Mod is None:
        await ctx.channel.send(f'{ctx.author.mention}, you provided too many arguments to the `!drop` command. Enter `!drop` to see how this command is used.')
        return
    course = args[0].lower()
    channels = await guild.fetch_channels()
    single = False
    if course == 'all':
        drop_courses = iter_all(coursedat.math, coursedat,stat, coursedat.oprs)
    elif course == 'math' or course == 'stat' or course == 'oprs':
        drop_courses = coursedat.__dict__[course]
    else:
        if len(course) != 9:
            await ctx.channel.send(f'{ctx.author.mention}, "{course}" is not a valid course name. Enter `!drop` to see how courses should be formatted')
            return
        try:
            dep, num = course.split('-')
        except:
            await ctx.channel.send(f'{ctx.author.mention}, "{course}" is not a valid course name. Enter `!drop` to see how courses should be formatted')
            return
        valid_course = True
        if dep == 'math':
            if course not in coursedat.math:
                valid_course = False
        elif dep == 'stat':
            if course not in coursedat.stat:
                valid_course = False
        elif dep == 'oprs':
            if course not in coursedat.oprs:
                valid_course = False
        else:
            valid_course = False
        if not valid_course:
            await ctx.channel.send(f'{ctx.author.mention}, "{course}" does not exist, so it could not be dropped.')
            return
        single = True
        drop_courses = (course,)
    for course in drop_courses:
        channel = d.utils.get(channels, name=course)
        ow = channel.overwrites
        if ctx.author in ow:
            del ow[ctx.author]
            await channel.edit(overwrites = ow)
    if single:
        await ctx.channel.send(f'{ctx.author.mention} successfully dropped from "{course.upper()}"!')
    else:
        await ctx.channel.send(f'{ctx.author.mention} successfully dropped from all requested channels!')

@bot.command()
async def request(ctx, *args):
    if ctx.guild != guild or ctx.prefix != '!':
        return
    if ctx.channel.name != 'terminal':
        return
    if len(args) == 0:
        await ctx.channel.send(f'{ctx.author.mention}, to request a course, enter `!request <course name>`. The course name should start with either "math", "stat", or "oprs", be followed by a hypen, then a 4 digit number. If you are the first to request a course, nothing will happen, but if someone else also requests the same course, it will automatically be created, and both of you will be added and notified. Requesting an existing course will act like registering for it. Example `!request math-0900` or `!request oprs-1234`.')
        return
    if len(args) >= 2:
        await ctx.channel.send(f'{ctx.author.mention}, you provided too many arguments to the `!request` command. Enter `!request` to see how this command is used.')
        return
    course = args[0].lower()
    if course in coursedat.requests:
        if coursedat.requests[course] == ctx.author:
            await ctx.channel.send(f'{ctx.author.mention}, you have already requested this course, and it will only be added if *another* user requests it.')
            return
        await ctx.channel.send(f'{ctx.author.mention}, someone previously requested this course, creating a channel for it now...')
        othermem = coursedat.requests[course]
        dep, num = course.split('-')
        chan = await _addcourse(dep,num)
        overwrites = chan.overwrites
        po = d.PermissionOverwrite(view_channel=True)
        overwrites[ctx.author] = po
        overwrites[othermem] = po
        await chan.edit(overwrites=overwrites)
        await chan.send(f'{ctx.author.mention} and {othermem.mention}, thanks for adding {course.upper()} to the server!')
        del coursedat.requests[course]
        persist_courses()
        channels = await guild.fetch_channels()
        bot_log = d.utils.get(channels, name='bot-log')
        await bot_log.send(f'{chan.mention} created by request.')
        return
        
    if len(course) != 9:
        await ctx.channel.send(f'{ctx.author.mention}, "{course}" is not a valid course name. Enter `!request` to see how courses should be formatted')
        return
    try:
        dep, num = course.split('-')
    except:
        await ctx.channel.send(f'{ctx.author.mention}, "{course}" is not a valid course name. Enter `!request` to see how courses should be formatted')
        return
    try:
        res = int(num)
        if res < 0:
            raise Exception()
    except:
        await ctx.channel.send(f'{ctx.author.mention}, "{course}" is not a valid course name. Enter `!request` to see how courses should be formatted')
        return
    if dep == 'math':
        if course in coursedat.math:
            await register(ctx, *args)
            return
    elif dep == 'stat':
        if course in coursedat.stat:
            await register(ctx, *args)
            return
    elif dep == 'oprs':
        if course in coursedat.oprs:
            await register(ctx, *args)
            return

    coursedat.requests[course] = ctx.author
    await ctx.channel.send(f'Thank you for requesting "{course.upper()}", {ctx.author.mention}. If someone else requests this course, it will automatically be added.')

COURSES_PER_PAGE = 10

@bot.command()
async def courses(ctx, *args):
    if ctx.guild != guild or ctx.prefix != '!':
        return
    if ctx.channel.name != 'terminal':
        return
    if len(args) == 0:
        await ctx.channel.send(f'{ctx.author.mention}, to see the available courses, enter the command `!courses <course type>`, replacing the course type with math, stat, or oprs. Example: `!courses math`')
        return
    if len(args) >= 3:
        await ctx.channel.send(f'{ctx.author.mention}, you included too many arugments to the `!courses` command. Enter `!courses` to see how to use it.')
        return
    dep = args[0].lower()
    page = 1
    if len(args) == 2:
        try:
            page = int(args[1])
            if page < 1:
                raise Exception()
        except:
            await ctx.channel.send(f'{ctx.author.mention}, the second argument for the `!courses` command must be a natural number indicating the page you want to see.')
            return
    if dep != 'math' and dep != 'stat' and dep != 'oprs':
        await ctx.channel.send(f'{ctx.author.mention}, the first argument for the `!courses` command must be either "math", "stat", or "oprs".')
        return
    courses_list = coursedat.__dict__[dep]
    num_pages = ceil(len(courses_list)/COURSES_PER_PAGE)
    if num_pages == 0:
        await ctx.channel.send(f'There are no {dep.upper()} courses yet. Request one with the `!request` command.')
        return
    if page > num_pages:
        page = num_pages
    first_idx = COURSES_PER_PAGE*(page-1)
    end_idx = first_idx + COURSES_PER_PAGE
    page_courses = courses_list[first_idx:end_idx]
    message = [f'Available {dep.upper()} courses (Page {page}/{num_pages}):','```',]
    for i, course in zip(range(first_idx+1, end_idx+1), page_courses):
        message.append(f'{i:3}.) {course.upper()}')
    message.append('```')
    await ctx.channel.send('\n'.join(message))

@bot.command()
async def registeruser(ctx, *args):
    if ctx.guild != guild or ctx.prefix != '!':
        return
    Mod = d.utils.get(ctx.author.roles, name = 'Moderator')
    if Mod is None:
        return
    if len(args) < 2:
        await ctx.channel.send(f'Usage: `!registeruser <course name> @mention1 [@mention2 ...]`. Must be existing course name, and valid mention to user.')
        return
    course = args[0].lower()
    try:
        dep, num = course.split('-')
    except:
        await ctx.channel.send(f'Usage: `!registeruser <course name> @mention1 [@mention2 ...]`. Must be existing course name, and valid mention to user.')
        return
    if dep != 'math' and dep != 'stat' and dep != 'oprs':
        await ctx.channel.send(f'Usage: `!registeruser <course name> @mention1 [@mention2 ...]`. Must be existing course name, and valid mention to user.')
        return
    course_list = coursedat.__dict__[dep]
    if course not in course_list:
        await ctx.channel.send(f'Usage: `!registeruser <course name> @mention1 [@mention2 ...]`. Must be existing course name, and valid mention to user.')
        return
    channels = await guild.fetch_channels()
    chan = d.utils.get(channels,name=course)
    ow = chan.overwrites
    po = d.PermissionOverwrite(view_channel=True)
    for mem in ctx.message.mentions:
        ow[mem] = po
    await chan.edit(overwrites=ow)

@bot.command()
async def register(ctx, *args):
    if ctx.guild != guild or ctx.prefix != '!':
        return
    if ctx.channel.name != 'terminal':
        return
    if len(args) == 0:
        await ctx.channel.send(f'{ctx.author.mention}, to register for a course, look through the existing courses using the `!courses` command. If you do not see the course you want to register for, use the `!request` command. If you do, enter `!register <course name>` to join the course and be able to see the channel for it. You can also register for all courses with `!register all`, for all MATH courses with `!register math` (the same goes for STAT and OPRS courses). Once you register for a course, it will appear after the "General" category of channels, and before the "Off Topic" category. Example: `!register math-1241` or `!register stat`.')
        return
    if len(args) >= 2:
        await ctx.channel.send(f'{ctx.author.mention}, you provided too many arguments to the `!register` command. Enter `!register` to see how this command is used.')
        return
    course = args[0].lower()
    channels = await guild.fetch_channels()
    single = False
    if course == 'all':
        add_courses = iter_all(coursedat.math, coursedat,stat, coursedat.oprs)
    elif course == 'math' or course == 'stat' or course == 'oprs':
        add_courses = coursedat.__dict__[course]
    else:
        if len(course) != 9:
            await ctx.channel.send(f'{ctx.author.mention}, "{course}" is not a valid course name. Enter `!register` to see how courses should be formatted.')
            return
        try:
            dep,num = course.split('-')
        except:
            await ctx.channel.send(f'{ctx.author.mention}, "{course}" is not a valid course name. Enter `!register` to see how courses should be formatted.')
            return
        valid_course = True
        if dep == 'math':
            if course not in coursedat.math:
                valid_course = False
        elif dep == 'stat':
            if course not in coursedat.stat:
                valid_course = False
        elif dep == 'oprs':
            if course not in coursedat.oprs:
                valid_course = False
        else:
            valid_course = False
        if not valid_course:
            await ctx.channel.send(f'{ctx.author.mention}, "{course}" does not exist. Make sure that you can see it with the `!courses` command, or request that the course be added with `!request`.')
            return
        single = True
        add_courses = (course,)
    for course in add_courses:
        channel = d.utils.get(channels, name=course)
        ow = channel.overwrites
        ow[ctx.author] = d.PermissionOverwrite(view_channel=True)
        await channel.edit(overwrites = ow)
    if single:
        await ctx.channel.send(f'{ctx.author.mention} successfully added to "{course.upper()}"!')
    else:
        await ctx.channel.send(f'{ctx.author.mention} successfully added to channels!')

bot.run(config.token)

