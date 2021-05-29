#!/usr/bin/env python3
import discord
from discord.ext import commands,tasks
import pymongo
import traceback
import io
import aiohttp
import os
import regex as re

'''
TODO: fix this garbage
- check for command error with on_command_error x
- check for edits with on_message_edit x
- check for no results in search x
- rebuild db and test
'''


file_db_id=int(847308528515416064)

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='l!',intents=intents)

client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client['db']

auth_users = []

control_re = re.compile(r'\p{C}')

def find_edits(channel_id,msg_id):
	return db[str(channel_id)].find({'msg_id':msg_id})

def data_to_msg(entries,embed,channel_id,guild):
	for entry in entries:
		edits = find_edits(channel_id,entry['msg_id'])
		for edit in edits:
			if edit['msg']:
				user = discord.utils.get(guild.members,id=int(entry['author_id']))
				text = f'[Link](https://discord.com/channels/{guild.id}/{channel_id}/{entry["msg_id"]})\n{edit["msg"]}'
				if not user:
					embed.add_field(name=f'From @Deleted User',value=text)
				else:
					embed.add_field(name=f'From @{user.name}#{user.discriminator}:',value=text)
			if edit['attachments']:
				links = []
				for url in edit['attachments']:
					links.append(f'[Link]({url})')
				user = discord.utils.get(guild.members,id=int(entry['author_id']))
				embed.add_field(name=f'Attachments from @{user.name}#{user.discriminator}:',value='\n'.join(links))
	return embed

async def msg_to_dict(msg):
	links = []
	for attachment in msg.attachments:
		async with aiohttp.ClientSession() as session:
			async with session.get(attachment.proxy_url) as res:
					name = attachment.proxy_url
					name = name[name.rfind('/')+1:]
					data = await res.read()
					channel = bot.get_guild(file_db_id).text_channels[0]
					file = discord.File(io.BytesIO(data),filename=name)
					try:
						file_msg = await channel.send(file=file)
						links.append(file_msg.attachments[0].proxy_url)
					except Exception as e:
						print(traceback.format_exc())

	emotes = re.findall(r'<a?:\w*:\d*>', msg.content)

	custom_emotes = []
	for emote in emotes:
		match = re.match(r'<(a?):([a-zA-Z0-9\_]+):([0-9]+)>$', emote)
		emoji_animated = bool(match.group(1))
		emoji_name = match.group(2)
		emoji_id = int(match.group(3))
		custom_emotes.append(discord.PartialEmoji.with_state(bot._connection, animated=emoji_animated, name=emoji_name,id=emoji_id))

	for emote in custom_emotes:
		data = await emote.url.read()
		name = str(emote.url)
		name = name[name.rfind('/')+1:]
		channel = bot.get_guild(file_db_id).text_channels[0]
		file = discord.File(io.BytesIO(data),filename=name)
		try:
			file_msg = await channel.send(file=file)
			links.append(file_msg.attachments[0].proxy_url)
		except Exception as e:
			print(traceback.format_exc())

	return {'author_id':msg.author.id,'msg':msg.content,'msg_id':msg.id,'attachments':links}

async def msg_to_db(msg):
	elem = await msg_to_dict(msg)
	db[str(msg.channel.id)].insert_one(elem)

@bot.event
async def on_command_error(ctx,error):
	print('command error: ',error)
	await msg_to_db(ctx.message)

@bot.event
async def on_message_edit(before,after):
	await msg_to_db(after)

@bot.event
async def on_message(msg):
	if msg.author == bot.user:
		return
	msg_strip = control_re.sub('',msg.content)
	if any(i in msg.content[:2] for i in '!@$%&?+=-\''):
		try:
			msg.content = msg_strip
			await bot.process_commands(msg)
			return
		except Exception as e:
			print(traceback.format_exc())
	await msg_to_db(msg)

@bot.command()
async def last(ctx,n=1):
	entries = db[str(ctx.channel.id)].find().sort('_id',-1).limit(n)
	embed = discord.Embed(title=f'Last {n} messages:',description=f'In <#{ctx.channel.id}>')
	embed = data_to_msg(entries,embed,ctx.channel.id,ctx.guild)
	await ctx.send(embed=embed)

@bot.command()
async def search(ctx,query,channel: discord.TextChannel=None):
	channel = ctx.channel if not channel else channel
	entries = db[str(channel.id)].find({'msg':{'$regex':f'.*{re.escape(query)}.*'}}).limit(20)
	embed = None
	if not entries:
		await msg_to_db(ctx.message)
		embed = discord.Embed(title=f'No results for query: {query}')
	else:
		embed = discord.Embed(title=f'Results for query: {query}')
		embed = data_to_msg(entries,embed,channel.id,ctx.guild)
	await ctx.send(embed=embed)

@bot.command()
async def snipe(ctx):
	entry = db[str(ctx.channel.id)].find().sort('_id',-1).limit(1)
	try:
		msg = ctx.fetch_message(int(entry[0]['msg_id']))
		await ctx.send('Nothing to snipe')
	except Exception as e:
		print(traceback.format_exc())
	embed = discord.Embed(title='DEBUG: Sniped message')
	embed = data_to_msg([entry],embed,ctx.channel.id,ctx.guild)
	await ctx.send(embed=embed)


@bot.event
async def on_ready():
	await bot.change_presence(activity=discord.Activity(name='you 👁️',type=discord.ActivityType.watching))
	for guild in bot.guilds:
		if guild.id == file_db_id:
			continue
		for channel in guild.text_channels:
			try:
				latest_db_msg = None
				if str(channel.id) in db.list_collection_names():
					latest_db_msg = int(db[str(channel.id)].find().sort('_id',-1).limit(1)[0]['msg_id'])
				if channel.last_message_id != latest_db_msg:
					latest_msg = await channel.fetch_message(latest_db_msg) if latest_db_msg else None
					async for msgs in channel.history(limit=None,after=latest_msg,oldest_first=True).chunk(10000):
						entries = []
						for msg in msgs:
							if msg.author == bot.user:
								continue
							entry = db[str(channel.id)].find_one({'msg_id':msg.id})
							if not entry:
								elem = await msg_to_dict(msg)
								entries.append(elem)
						if entries:
							db[str(channel.id)].insert_many(entries)
			except Exception:
				print(traceback.format_exc())
	print('finished reading history')

@bot.command()
async def shutdown(ctx):
	if str(ctx.author.id) in auth_users:
		await bot.close()
	else:
		await ctx.send("can't do that ya dum dum")

@bot.command()
async def unpurge(ctx,n: int):
	entries = reversed(db[str(ctx.channel.id)].find().sort('_id',-1).limit(n))
	for entry in entries:
		embed = discord.Embed(title='Message:')
		await ctx.send(embed=data_to_msg([entry],embed,ctx.channel.id,ctx.guild))

with open('auth_users.txt','r') as f:
	auth_users = f.read().splitlines()

bot.run(os.getenv('LOG_TOKEN'))
