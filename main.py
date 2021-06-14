#!/usr/bin/env python3
import discord
from discord.ext import commands
import pymongo
import os
from log_cogs import *

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix='l!',intents=intents)

client = pymongo.MongoClient('mongodb://mongodb:27017/')
file_db = client['file_db']['links']

bot.add_cog(Util(bot,client,file_db))
bot.add_cog(Management(bot))
bot.add_cog(Listeners(bot))
bot.add_cog(LogCommands(bot))
bot.run(os.getenv('LOG_TOKEN'))
