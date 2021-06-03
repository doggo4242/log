from discord.ext import commands

class Management(commands.Cog):
	def __init__(self,bot):
		self.bot = bot
		self.auth_users = None
		self.util = self.bot.get_cog('Util')

	@commands.command()
	async def shutdown(self,ctx):
		if str(ctx.author.id) in auth_users:
			await bot.close()
		else:
			await ctx.send("can't do that ya dum dum")

	@commands.command()
	async def setDbChannel(self,ctx):
		if str(ctx.author.id) not in auth_users:
			await ctx.send("can't do that ya dum dum")
			return
		with open('file_db.txt','w') as f:
			f.write(str(ctx.channel.id))
		self.util.file_db_channel = ctx.channel.id
		await ctx.send(f'Files will now be stored in {ctx.channel.mention}')
