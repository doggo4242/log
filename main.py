#!/usr/bin/env python3
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
