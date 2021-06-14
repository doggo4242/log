'''
   Copyright 2021 doggo4242 Development

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
'''

import discord
from discord.ext import commands
import traceback
import regex as re

class Listeners(commands.Cog):
	def __init__(self,bot):
		self.bot = bot
		self.util = self.bot.get_cog('Util')
		self.control_re = re.compile(r'\p{C}')

	@commands.Cog.listener()
	async def on_command_error(self,ctx,error):
		print('command error: ',error)
		await self.util.msg_to_db(ctx.message)

	@commands.Cog.listener()
	async def on_message_edit(self,before,after):
		if after.author == self.bot.user:
			return
		db = self.util.client[str(after.guild.id)]
		print('edit:',after.content)
		record = db[str(after.channel.id)].find_one({'msg_id':after.id})
		record['edits'].append(after.content)
		db[str(after.channel.id)].update_one({'_id':record['_id']},{'$set':record},upsert=False)

	@commands.Cog.listener()
	async def on_message_delete(self,msg):
		if msg.author == self.bot.user:
			return
		db = self.util.client[str(msg.guild.id)]
		record = db[str(msg.channel.id)].find_one({'msg_id':msg.id})
		record['deleted'] = True
		db[str(msg.channel.id)].update_one({'_id':record['_id']},{'$set':record},upsert=False)

	@commands.Cog.listener()
	async def on_message(self,msg):
		if msg.author == self.bot.user or msg.type != discord.MessageType.default:
			return
		print('msg:',msg.content)
		ctx = await self.bot.get_context(msg)
		if ctx.valid:
			return
		msg.content = self.control_re.sub('',msg.content)
		await self.util.msg_to_db(msg)

	@commands.Cog.listener()
	async def on_guild_channel_delete(self,channel):
		print('deleting channel:',channel.name)
		self.util.client[str(channel.guild.id)][str(channel.id)].drop()

	@commands.Cog.listener()
	async def on_ready(self):
		await self.bot.change_presence(activity=discord.Activity(name='you 👁️',type=discord.ActivityType.watching))
		with open('/etc/log/auth_users.txt','r') as f:
			mgmt = self.bot.get_cog('Management')
			mgmt.auth_users = f.read().splitlines()

		with open('/etc/log/file_db.txt','r') as f:
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
						latest_msg = await channel.fetch_message(latest_db_msg[0]['msg_id'])
						print(len([i for i in latest_db_msg]))
						'''
						if latest_db_msg.retrieved:
							latest_db_msg = latest_db_msg[0]
							while True:
								try:
									latest_msg = await channel.fetch_message(latest_db_msg['msg_id'])
									break
								except:
									latest_db_msg = self.util.client[str(guild.id)][str(channel.id)].find({'timestamp':{'$lt':latest_db_msg['timestamp']}}).sort('timestamp',-1).limit(1)
									if not latest_db_msg.retrieved:
										latest_msg = None
										break
									else:
										latest_db_msg = latest_db_msg[0]
						'''
					if channel.last_message_id != latest_db_msg:
						async for msgs in channel.history(limit=None,after=latest_msg,oldest_first=True).chunk(10240):
							entries = []
							for msg in msgs:
								if msg.author == self.bot.user:
									continue
								entry = self.util.client[str(guild.id)][str(channel.id)].find_one({'msg_id':msg.id})
								if not entry:
									elem = await self.util.msg_to_dict(msg)
									entries.append(elem)
							if entries:
								self.util.client[str(guild.id)][str(channel.id)].insert_many(entries)
				except Exception:
					print(traceback.format_exc())
					print(channel.id)
		print('finished reading history')

