import discord
from discord.ext import commands
import io
import regex as re

class Util(commands.Cog):
	def __init__(bot,client,channel):
		self.bot = bot
		self.client = client
		self.file_db_channel = channel
		self.emote_finder_re = re.compile(r'<a?:\w*:\d*>')
		self.emote_matcher_re = re.compile(r'<(a?):([a-zA-Z0-9\_]+):([0-9]+)>$')

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
					text = f'[Link](https://discord.com/channels/{guild.id}/{channel_id}/{entry["msg_id"]})\n{edit}'
					name = f'From {entry["author"]}:' if not is_reply else f'In response to {entry["author"]}:'

					n_fields = len(text)//field_len+1
					count+=len(text)+(n_fields*len(name))+(n_fields*len('...'))
					print('count:',count,count//embed_len)
					if (count//embed_len+1) > len(embeds):
#						print('embed len:',len(embeds[count//embed_len-1]))
						embeds.append(discord.Embed(title=title,description=desc))
						count += len(title)+len(desc)

					chunks = chunk_str(text,field_len)
					embeds[count//embed_len].add_field(name=name,value=chunks[0])
					for chunk in chunks[1:]:
						embeds[count//embed_len].add_field(name=name,value=chunk)
						print('embed field len:',len(chunk))

			if entry['reply'] and not is_reply:
				reply = self.client[str(guild.id)][str(channel_id)].find_one({'msg_id':entry['reply']})
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

				count+=sum([len(i) for i in links])
				if (count//embed_len+1) > len(embeds):
					embeds.append(discord.Embed(title=title,description=desc))
					count += len(title)+len(desc)

				chunks = chunk_list(links,field_len)
				for chunk in chunks:
					embeds[count//embed_len].add_field(name=f'Attachments from {entry["author"]}',value=chunk)
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
				channel = await self.bot.fetch_channel(self.file_db_channel)
				try:
					file = await attachment.to_file(use_cached=True)
					file_msg = await channel.send(file=file)
					links.append(file_msg.attachments[0].proxy_url)
					file_db.insert_one({'orig_link':attachment.proxy_url,'db_link':file_msg.attachments[0].proxy_url})
				except Exception as e:
					print(traceback.format_exc())

		emotes = self.emote_finder_re.findall(msg.content)

		custom_emotes = []
		for emote in emotes:
			match = self.emote_matcher_re.match(emote)
			emoji_animated = bool(match.group(1))
			emoji_name = match.group(2)
			emoji_id = int(match.group(3))
			custom_emotes.append(discord.PartialEmoji.with_state(self.bot._connection, animated=emoji_animated, name=emoji_name,id=emoji_id))

		for i,emote in enumerate(custom_emotes):
			record = file_db.find_one({'orig_link':str(emote.url)})
			if record:
				msg.content = msg.content.replace(emotes[i],f'[:{emote.name}:]({record["db_link"]})')
			else:
				data = await emote.url.read()
				name = str(emote.url)
				name = name[name.rfind('/')+1:]
				channel = await self.bot.fetch_channel(self.file_db_channel)
				file = discord.File(io.BytesIO(data),filename=name)
				try:
					file_msg = await channel.send(file=file)
					msg.content = msg.content.replace(emotes[i],f'[:{emote.name}:]({file_msg.attachments[0].proxy_url})')
					file_db.insert_one({'orig_link':str(emote.url),'db_link':file_msg.attachments[0].proxy_url})
				except Exception as e:
					print(traceback.format_exc())

		reply_id = msg.reference.message_id if msg.reference and msg.reference.message_id else None

		return {'author':f'@{msg.author.name}#{msg.author.discriminator}','edits':[msg.content],'msg_id':msg.id,'attachments':links,'deleted':False,'timestamp':msg.created_at.timestamp(),'reply':reply_id}

	async def msg_to_db(msg):
		elem = await msg_to_dict(msg)
		self.client[str(msg.guild.id)][str(msg.channel.id)].insert_one(elem)
