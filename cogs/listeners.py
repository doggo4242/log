import discord
from discord.ext import commands
import regex as re

class Listeners(commands.Cog):
	def __init__(bot):
		self.bot = bot
		self.util = self.bot.get_cog('Util')
		self.control_re = re.compile(r'\p{C}')

	@commands.Cog.listener()
	async def on_command_error(ctx,error):
		print('command error: ',error)
		await self.util.msg_to_db(ctx.message)

	@commands.Cog.listener()
	async def on_message_edit(before,after):
		if after.author == self.bot.user:
			return
		db = self.util.client[str(after.guild.id)]
		print('edit:',after.content)
		record = db[str(after.channel.id)].find_one({'msg_id':after.id})
		record['edits'].append(after.content)
		db[str(after.channel.id)].update_one({'_id':record['_id']},{'$set':record},upsert=False)

	@commands.Cog.listener()
	async def on_message_delete(msg):
		if msg.author == self.bot.user:
			return
		db = self.util.client[str(msg.guild.id)]
		record = db[str(msg.channel.id)].find_one({'msg_id':msg.id})
		record['deleted'] = True
		db[str(msg.channel.id)].update_one({'_id':record['_id']},{'$set':record},upsert=False)

	@commands.Cog.listener()
	async def on_message(msg):
		if msg.author == self.bot.user or msg.type != discord.MessageType.default:
			return
		print('msg:',msg.content)
		msg_strip = self.control_re.sub('',msg.content)
		if any(i in msg_strip[:2] for i in '!@$%&?+=-\''):
			try:
				msg.content = msg_strip
				await self.bot.process_commands(msg)
				return
			except Exception as e:
				print(traceback.format_exc())
		await self.util.msg_to_db(msg)

	@commands.Cog.listener()
	async def on_guild_channel_delete(channel):
		print('deleting channel:',channel.name)
		self.util.client[str(channel.guild.id)][str(channel.id)].drop()

	@commands.Cog.listener()
	async def on_ready():
		await self.bot.change_presence(activity=discord.Activity(name='you 👁️',type=discord.ActivityType.watching))
		with open('config/file_db.txt','r') as f:
			self.util.file_db_channel = int(f.read())

		for guild in self.bot.guilds:
			for channel in guild.text_channels:
				if channel.id == self.util.file_db_channel:
					continue
				try:
					latest_db_msg = None
					latest_msg = None
					if str(channel.id) in self.util.client[str(guild.id)].list_collection_names():
						latest_db_msg = self.util.client[str(guild.id)][str(channel.id)].find().sort('timestamp',-1).limit(1)
						if latest_db_msg.retrieved:
							latest_db_msg = latest_db_msg[0]
							while True:
								try:
									latest_msg = await channel.fetch_message(latest_db_msg['msg_id'])
									break
								except:
									latest_db_msg = self.util.client[str(guild.id)][str(channel.id)].find({'timestamp':{'$lt':latest_db_msg['timestamp']}}).limit(1)
									if not latest_db_msg.retrieved:
										latest_msg = None
										break
									else:
										latest_db_msg = latest_db_msg[0]
					if channel.last_message_id != latest_db_msg:
						async for msgs in channel.history(limit=None,after=latest_msg,oldest_first=True).chunk(10240):
							entries = []
							for msg in msgs:
								if msg.author == self.bot.user:
									continue
								entry = self.util.client[str(guild.id)][str(channel.id)].find_one({'msg_id':msg.id})
								if not entry:
									elem = await msg_to_dict(msg)
									entries.append(elem)
							if entries:
								self.util.client[str(guild.id)][str(channel.id)].insert_many(entries)
				except Exception:
					print(traceback.format_exc())
					print(channel.id)
		print('finished reading history')

