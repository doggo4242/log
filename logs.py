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
import time

'''
TODO: fix this garbage
- check for command error with on_command_error x
- check for edits with on_message_edit x
- check for no results in search x
- timestamp bc history, _id does not allow concurrency with indexing x
- add replies x
- add file db x
- allow setting of file db channel x
- rebuild db and test
'''

#file_db_id=int(847308528515416064)
file_db_channel=None

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix='l!',intents=intents)

client = pymongo.MongoClient('mongodb://localhost:27017/')
#db = client['db']
file_db = client['file_db']['links']

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

def data_to_msg(entries,title,desc,channel_id,guild,is_reply):
	field_len = 1024
	embed_len = 6000
	embeds = []
	count = len(title)+len(desc)
	for entry in entries:
		for edit in entry['edits']:
			if edit:
				user = bot.get_user(int(entry['author_id']))
				user = f'@{user.name}#{user.discriminator}' if user else '@Deleted User#0000'
				text = f'[Link](https://discord.com/channels/{guild.id}/{channel_id}/{entry["msg_id"]})\n{edit}'
				name = f'From {user}:' if not is_reply else f'In response to {user}:'

				n_fields = len(text)//field_len+1
				count+=len(text)+(n_fields*len(name))+(n_fields*len('...'))
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

		if entry['reply'] and not is_reply:
			reply = client[str(guild.id)][str(channel_id)].find_one({'msg_id':entry['reply']})
			if reply:
				reply_embed = data_to_msg([reply],title,desc,channel_id,guild,True)[0]
				text_len = sum([len(field.value) for field in reply_embed.fields])
				count+=text_len+((text_len//field_len+1)*len(reply_embed.fields[0].name))
				if (count//embed_len+1) > len(embeds):
					embeds.append(reply_embed)
					count+=len(title)+len(desc)
				else:
					for field in reply_embed.fields:
						embeds[count//embed_len].add_field(name=field.name,value=field.value)

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
		record = file_db.find_one({'orig_link':attachment.proxy_url})
		if record:
			links.append(record['db_link'])
		else:
			channel = await bot.fetch_channel(file_db_channel)
			try:
				file = await attachment.to_file(use_cached=True)
				file_msg = await channel.send(file=file)
				links.append(file_msg.attachments[0].proxy_url)
				file_db.insert_one({'orig_link':attachment.proxy_url,'db_link':file_msg.attachments[0].proxy_url})
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
		record = file_db.find_one({'orig_link':str(emote.url)})
		if record:
			msg.content = msg.content.replace(emotes[i],f'[:{emote.name}:]({record["db_link"]})')
		else:
			data = await emote.url.read()
			name = str(emote.url)
			name = name[name.rfind('/')+1:]
			channel = await bot.fetch_channel(file_db_channel)
			file = discord.File(io.BytesIO(data),filename=name)
			try:
				file_msg = await channel.send(file=file)
				msg.content = msg.content.replace(emotes[i],f'[:{emote.name}:]({file_msg.attachments[0].proxy_url})')
				file_db.insert_one({'orig_link':str(emote.url),'db_link':file_msg.attachments[0].proxy_url})
			except Exception as e:
				print(traceback.format_exc())

	reply_id = msg.reference.message_id if msg.reference and msg.reference.message_id else None

	return {'author_id':msg.author.id,'edits':[msg.content],'msg_id':msg.id,'attachments':links,'deleted':False,'timestamp':msg.created_at.timestamp(),'reply':reply_id}

async def msg_to_db(msg):
	elem = await msg_to_dict(msg)
	client[str(msg.guild.id)][str(msg.channel.id)].insert_one(elem)

#@bot.event
#async def on_command_error(ctx,error):
#	print('command error: ',error)
#	await msg_to_db(ctx.message)

@bot.event
async def on_message_edit(before,after):
	if after.author == bot.user:
		return
	db = client[str(after.guild.id)]
	print('edit:',after.content)
	record = db[str(after.channel.id)].find_one({'msg_id':after.id})
	record['edits'].append(after.content)
	db[str(after.channel.id)].update_one({'_id':record['_id']},{'$set':record},upsert=False)

@bot.event
async def on_message_delete(msg):
	if msg.author == bot.user:
		return
	db = client[str(msg.guild.id)]
	record = db[str(msg.channel.id)].find_one({'msg_id':msg.id})
	record['deleted'] = True
	db[str(msg.channel.id)].update_one({'_id':record['_id']},{'$set':record},upsert=False)

@bot.event
async def on_message(msg):
	if msg.author == bot.user or msg.type != discord.MessageType.default:
		return
	print('msg:',msg.content)
	msg_strip = control_re.sub('',msg.content)
	if any(i in msg_strip[:2] for i in '!@$%&?+=-\''):
		try:
			msg.content = msg_strip
			await bot.process_commands(msg)
			return
		except Exception as e:
			print(traceback.format_exc())
	await msg_to_db(msg)

@bot.command()
async def last(ctx,n=1):
	entries = client[str(ctx.guild.id)][str(ctx.channel.id)].find().sort('timestamp',-1).limit(n)
	embeds = data_to_msg(entries,f'Last {n} messages:',f'In <#{ctx.channel.id}>',ctx.channel.id,ctx.guild,False)
	paginator = disputils.BotEmbedPaginator(ctx,embeds)
	await paginator.run()

@bot.command()
async def search(ctx,query,channel: discord.TextChannel=None):
	channel = ctx.channel if not channel else channel
	entries = client[str(ctx.guild.id)][str(channel.id)].find({'edits':{'$regex':f'.*{re.escape(query)}.*'}}).limit(20)
	embed = None
	if not entries:
		await msg_to_db(ctx.message)
		embed = discord.Embed(title=f'No results for query: {query}')
		await ctx.send(embed=embed)
	else:
		embeds = data_to_msg(entries,f'Results for query: {query}','',channel.id,ctx.guild,False)
		paginator = disputils.BotEmbedPaginator(ctx,embeds)
		await paginator.run()

@bot.command()
async def snipe(ctx):
	entries = client[str(ctx.guild.id)][str(ctx.channel.id)].find().sort('timestamp',-1).limit(20)
	for entry in entries:
		print('deleted:',entry['deleted'],entry['edits'][0])
		if entry['deleted']:
			embed = data_to_msg([entry],'Sniped message:','',ctx.channel.id,ctx.guild,False)[0]
			await ctx.send(embed=embed)
			return

	await ctx.send('Nothing to snipe')


@bot.event
async def on_ready():
	await bot.change_presence(activity=discord.Activity(name='you 👁️',type=discord.ActivityType.watching))
	global file_db_channel
	with open('file_db.txt','r') as f:
		file_db_channel = int(f.read())

	for guild in bot.guilds:
		for channel in guild.text_channels:
			if channel.id == file_db_channel:
				continue
			try:
				latest_db_msg = None
				if str(channel.id) in client[str(guild.id)].list_collection_names():
					latest_db_msg = int(client[str(guild.id)][str(channel.id)].find().sort('timestamp',-1).limit(1)[0]['msg_id'])
				if channel.last_message_id != latest_db_msg:
					latest_msg = await channel.fetch_message(latest_db_msg) if latest_db_msg else None
					async for msgs in channel.history(limit=None,after=latest_msg,oldest_first=True).chunk(10240):
						entries = []
						for msg in msgs:
							if msg.author == bot.user:
								continue
							entry = client[str(guild.id)][str(channel.id)].find_one({'msg_id':msg.id})
							if not entry:
								elem = await msg_to_dict(msg)
								entries.append(elem)
						if entries:
							client[str(guild.id)][str(channel.id)].insert_many(entries)
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
	entries = reversed(list(client[str(ctx.guild.id)][str(ctx.channel.id)].find({'deleted':True}).sort('timestamp',-1).limit(n)))
	for entry in entries:
		await ctx.send(embed=data_to_msg([entry],'Message:','',ctx.channel.id,ctx.guild,False)[0])

@bot.event
async def on_guild_channel_delete(channel):
	print('deleting channel:',channel.name)
	client[str(channel.guild.id)][str(channel.id)].drop()

@bot.command()
async def after(ctx,msg,n=1):
	db = client[str(ctx.guild.id)]
	match = re.match('https://discord.com/channels/[0-9]{18}/([0-9]{18})/([0-9]{18})',msg)
	channel_id = match.group(1) if match else str(ctx.channel.id)
	msg_id = int(match.group(2)) if match else int(msg)
	msg_entry = db[channel_id].find_one({'msg_id':msg_id})
	entries = db[channel_id].find({'timestamp':{'$gt':msg_entry['timestamp']}}).sort('timestamp',1).limit(n)
	embeds = data_to_msg(entries,f'First {n} messages after requested message:',f'In <#{ctx.channel.id}>',int(channel_id),ctx.guild,False)
	paginator = disputils.BotEmbedPaginator(ctx,embeds)
	await paginator.run()

@bot.command()
async def before(ctx,msg,n=1):
	db = client[str(ctx.guild.id)]
	match = re.match('https://discord.com/channels/[0-9]{18}/([0-9]{18})/([0-9]{18})',msg)
	channel_id = match.group(1) if match else str(ctx.channel.id)
	msg_id = int(match.group(2)) if match else int(msg)
	msg_entry = db[channel_id].find_one({'msg_id':msg_id})
	entries = db[channel_id].find({'timestamp':{'$lt':msg_entry['timestamp']}}).sort('timestamp',-1).limit(n)
	embeds = data_to_msg(entries,f'Last {n} messages before requested message:',f'In <#{ctx.channel.id}>',int(channel_id),ctx.guild,False)
	paginator = disputils.BotEmbedPaginator(ctx,embeds)
	await paginator.run()

@bot.command()
async def setDbChannel(ctx):
	if str(ctx.author.id) not in auth_users:
		await ctx.send("can't do that ya dum dum")
		return
	global file_db_channel
	with open('file_db.txt','w') as f:
		f.write(str(ctx.channel.id))
	file_db_channel = ctx.channel.id
	await ctx.send(f'Files will now be stored in {ctx.channel.mention}')

with open('auth_users.txt','r') as f:
	auth_users = f.read().splitlines()

bot.run(os.getenv('LOG_TOKEN'))
