from discord.ext import commands
import disputils
import regex as re

class LogCommands(commands.Cog):
	def __init__(bot):
		self.bot = bot
		self.util = self.bot.get_cog('Util')
		self.lnk_matcher = re.compile('https://discord.com/channels/[0-9]{18}/([0-9]{18})/([0-9]{18})')

	@commands.command()
	async def last(ctx,n=1):
		entries = self.util.client[str(ctx.guild.id)][str(ctx.channel.id)].find().sort('timestamp',-1).limit(n)
		embeds = self.util.data_to_msg(entries,f'Last {n} messages:',f'In <#{ctx.channel.id}>',ctx.channel.id,ctx.guild,False)
		paginator = disputils.BotEmbedPaginator(ctx,embeds)
		await paginator.run()

	@commands.command()
	async def search(ctx,query,channel: discord.TextChannel=None):
		channel = ctx.channel if not channel else channel
		entries = self.util.client[str(ctx.guild.id)][str(channel.id)].find({'edits':{'$regex':f'.*{re.escape(query)}.*'}}).limit(20)
		embed = None
		if not entries:
			await self.util.msg_to_db(ctx.message)
			embed = discord.Embed(title=f'No results for query: {query}')
			await ctx.send(embed=embed)
		else:
			embeds = self.util.data_to_msg(entries,f'Results for query: {query}','',channel.id,ctx.guild,False)
			paginator = disputils.BotEmbedPaginator(ctx,embeds)
			await paginator.run()

	@commands.command()
	async def snipe(ctx):
		entries = self.util.client[str(ctx.guild.id)][str(ctx.channel.id)].find().sort('timestamp',-1).limit(20)
		for entry in entries:
			print('deleted:',entry['deleted'],entry['edits'][0])
			if entry['deleted']:
				embed = data_to_msg([entry],'Sniped message:','',ctx.channel.id,ctx.guild,False)[0]
				await ctx.send(embed=embed)
				return

		await ctx.send('Nothing to snipe')

	@commands.command()
	async def unpurge(ctx,n: int):
		entries = self.util.client[str(ctx.guild.id)][str(ctx.channel.id)].find({'deleted':True}).sort('timestamp',-1).limit(n)[::-1]
		for entry in entries:
			await ctx.send(embed=data_to_msg([entry],'Message:','',ctx.channel.id,ctx.guild,False)[0])

	@commands.command()
	async def after(ctx,msg,n=1):
		if n <= 0:
			await ctx.send('Invalid range')
			return
		db = self.util.client[str(ctx.guild.id)]
		match = lnk_matcher.match(msg)
		channel_id = match.group(1) if match else str(ctx.channel.id)
		msg_id = int(match.group(2)) if match else int(msg)
		msg_entry = db[channel_id].find_one({'msg_id':msg_id})
		if not msg_entry:
			await ctx.send('Message not found')
			return
		entries = db[channel_id].find({'timestamp':{'$gt':msg_entry['timestamp']}}).sort('timestamp',1).limit(n)
		embeds = data_to_msg(entries,f'First {n} messages after requested message:',f'In <#{ctx.channel.id}>',int(channel_id),ctx.guild,False)
		paginator = disputils.BotEmbedPaginator(ctx,embeds)
		await paginator.run()

	@commands.command()
	async def before(ctx,msg,n=1):
		if n <= 0:
			await ctx.send('Invalid range')
			return
		db = client[str(ctx.guild.id)]
		match = lnk_matcher.match(msg)
		channel_id = match.group(1) if match else str(ctx.channel.id)
		msg_id = int(match.group(2)) if match else int(msg)
		msg_entry = db[channel_id].find_one({'msg_id':msg_id})
		if not msg_entry:
			await ctx.send('Message not found')
			return
		entries = db[channel_id].find({'timestamp':{'$lt':msg_entry['timestamp']}}).sort('timestamp',-1).limit(n)
		embeds = data_to_msg(entries,f'Last {n} messages before requested message:',f'In <#{ctx.channel.id}>',int(channel_id),ctx.guild,False)
		paginator = disputils.BotEmbedPaginator(ctx,embeds)
		await paginator.run()
