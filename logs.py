#!/usr/bin/env python3
import discord
from discord.ext import commands,tasks
import disputils
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
- shit i forgot to store channel id thats gonna be an issue
- add replies
- rebuild db and test
'''


file_db_id=int(847308528515416064)

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix='l!',intents=intents)

client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client['db']

auth_users = []

control_re = re.compile(r'\p{C}')

def chunk_str(string,n):
	f = string[:n]
	n-=len('...')
	return [f]+['...'+string[i:i+n] for i in range(n,len(string),n)]

def chunk_list(lst,n):
	chunks = []
	count = 0
	for item in lst:
		count+=len(item)
		if count//n+1 > len(chunks):
			chunks.append([item])
		else:
			chunks[count//n].append(item)
	return chunks

def data_to_msg(entries,title,desc,channel_id,guild):
	field_len = 512
	embed_len = 3000
	embeds = []
	count = len(title)+len(desc)
	for entry in entries:
		for edit in entry['edits']:
			if edit:
				user = bot.get_user(int(entry['author_id']))
				user = f'@{user.name}#{user.discriminator}' if user else '@Deleted User#0000'
				text = f'[Link](https://discord.com/channels/{guild.id}/{channel_id}/{entry["msg_id"]})\n{edit}'
				name = f'From {user}:'

				count+=len(text)+len(name)+((len(text)//field_len-1)*len('...'))
				print('count:',count,count//embed_len)
				if (count//embed_len+1) > len(embeds):
#					print('embed len:',len(embeds[count//embed_len-1]))
					embeds.append(discord.Embed(title=title,description=desc))
					count += len(title)+len(desc)

				chunks = chunk_str(text,field_len)
				embeds[count//embed_len].add_field(name=name,value=chunks[0])
				for chunk in chunks[1:]:
					embeds[count//embed_len].add_field(name=name,value=chunk)
					print('embed field len:',len(chunk))

		if entry['attachments']:
			links = []
			for url in entry['attachments']:
				links.append(f'[Link]({url})')
			user = bot.get_user(int(entry['author_id']))
			user = f'@{user.name}#{user.discriminator}' if user else '@Deleted User#0000'

			count+=sum([len(i) for i in links])
			if (count//embed_len+1) > len(embeds):
				embeds.append(discord.Embed(title=title,description=desc))
				count += len(title)+len(desc)

			chunks = chunk_list(links,field_len)
			for chunk in chunks:
				embeds[count//embed_len].add_field(name=f'Attachments from {user}',value=chunk)
				print('embed field len:',len(chunk))

	for embed in embeds:
		print(len(embed))
	return embeds

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

	for i,emote in enumerate(custom_emotes):
		data = await emote.url.read()
		name = str(emote.url)
		name = name[name.rfind('/')+1:]
		channel = bot.get_guild(file_db_id).text_channels[0]
		file = discord.File(io.BytesIO(data),filename=name)
		try:
			file_msg = await channel.send(file=file)
			msg.content = msg.content.replace(emotes[i],f'[:{emote.name}:]({file_msg.attachments[0].proxy_url})')
		except Exception as e:
			print(traceback.format_exc())

	return {'author_id':msg.author.id,'edits':[msg.content],'msg_id':msg.id,'attachments':links,'deleted':False}

async def msg_to_db(msg):
	elem = await msg_to_dict(msg)
	db[str(msg.channel.id)].insert_one(elem)

@bot.event
async def on_command_error(ctx,error):
	print('command error: ',error)
	await msg_to_db(ctx.message)

@bot.event
async def on_message_edit(before,after):
	if after.author == bot.user:
		return
	print('edit:',after.content)
	record = db[str(after.channel.id)].find_one({'msg_id':after.id})
	record['edits'].append(after.content)
	db[str(after.channel.id)].update_one({'_id':record['_id']},{'$set':record},upsert=False)

@bot.event
async def on_message_delete(msg):
	if msg.author == bot.user:
		return
	record = db[str(msg.channel.id)].find_one({'msg_id':msg.id})
	record['deleted'] = True
	db[str(msg.channel.id)].update_one({'_id':record['_id']},{'$set':record},upsert=False)

@bot.event
async def on_message(msg):
	if msg.author == bot.user or msg.guild.id == file_db_id:
		return
	print('msg:',msg.content)
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
	embeds = data_to_msg(entries,f'Last {n} messages:',f'In <#{ctx.channel.id}>',ctx.channel.id,ctx.guild)
	paginator = disputils.BotEmbedPaginator(ctx,embeds)
	await paginator.run()

@bot.command()
async def search(ctx,query,channel: discord.TextChannel=None):
	channel = ctx.channel if not channel else channel
	entries = db[str(channel.id)].find({'edits':{'$regex':f'.*{re.escape(query)}.*'}}).limit(20)
	embed = None
	if not entries:
		await msg_to_db(ctx.message)
		embed = discord.Embed(title=f'No results for query: {query}')
		await ctx.send(embed=embed)
	else:
		embeds = data_to_msg(entries,f'Results for query: {query}','',channel.id,ctx.guild)
		paginator = disputils.BotEmbedPaginator(ctx,embeds)
		await paginator.run()

@bot.command()
async def snipe(ctx):
	entries = db[str(ctx.channel.id)].find().sort('_id',-1).limit(20)
	for entry in entries:
		print('deleted:',entry['deleted'],entry['edits'][0])
		if entry['deleted']:
			embed = data_to_msg([entry],'Sniped message:','',ctx.channel.id,ctx.guild)[0]
			await ctx.send(embed=embed)
			return

	await ctx.send('Nothing to snipe')


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
					async for msgs in channel.history(limit=None,after=latest_msg,oldest_first=True).chunk(10240):
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
				print(channel.id)
	print('finished reading history')

@bot.command()
async def shutdown(ctx):
	if str(ctx.author.id) in auth_users:
		await bot.close()
	else:
		await ctx.send("can't do that ya dum dum")

@bot.command()
async def unpurge(ctx,n: int):
	entries = reversed(list(db[str(ctx.channel.id)].find({'deleted':True}).sort('_id',-1).limit(n)))
	for entry in entries:
		await ctx.send(embed=data_to_msg([entry],'Message:','',ctx.channel.id,ctx.guild)[0])

@bot.event
async def on_guild_channel_delete(channel):
	print('deleting channel:',channel.name)
	db[str(channel.id)].drop()

@bot.command()
async def after(ctx,msg,n=1):
	match = re.match('https://discord.com/channels/[0-9]{18}/[0-9]{18}/([0-9]{18})',msg)
	msg_id = int(match.group(1)) if match else int(msg)
	msg_entry = db[str(ctx.channel.id)].find_one({'msg_id':msg_id})
	entries = db[str(ctx.channel.id)].find({'_id':{'$gt':msg_entry['_id']}}).sort('_id',1).limit(n)
	embeds = data_to_msg(entries,f'First {n} messages after requested message:',f'In <#{ctx.channel.id}>',ctx.channel.id,ctx.guild)
	paginator = disputils.BotEmbedPaginator(ctx,embeds)
	await paginator.run()

@bot.command()
async def before(ctx,msg,n=1):
	match = re.match('https://discord.com/channels/[0-9]{18}/[0-9]{18}/([0-9]{18})',msg)
	msg_id = int(match.group(1)) if match else int(msg)
	msg_entry = db[str(ctx.channel.id)].find_one({'msg_id':msg_id})
	entries = db[str(ctx.channel.id)].find({'_id':{'$lt':msg_entry['_id']}}).sort('_id',-1).limit(n)
	embeds = data_to_msg(entries,f'Last {n} messages before requested message:',f'In <#{ctx.channel.id}>',ctx.channel.id,ctx.guild)
	paginator = disputils.BotEmbedPaginator(ctx,embeds)
	await paginator.run()

with open('auth_users.txt','r') as f:
	auth_users = f.read().splitlines()

bot.run(os.getenv('LOG_TOKEN'))
