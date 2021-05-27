#include <sleepy_discord/sleepy_discord.h>
#include <mongocxx/client.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/options/client.hpp>
#include <mongocxx/uri.hpp>
#include <bsoncxx/builder/stream/helpers.hpp>
#include <bsoncxx/builder/stream/document.hpp>
#include <bsoncxx/builder/stream/array.hpp>
#include <bsoncxx/json.hpp>
#include <bsoncxx/view_or_value.hpp>


class LogClient : public SleepyDiscord::DiscordClient {
public:
	mongocxx::instance instance;
	mongocxx::client client;
	mongocxx::database db;
	LogClient(){
		instance = mongocxx::instance{};
		client = mongocxx::client{mongocxx::uri("mongo://localhost:27017")};
		db = client["db"];
	}
	using SleepyDiscord::DiscordClient::DiscordClient;
	void onMessage(SleepyDiscord::Message msg) override {
		if(msg.author == getUser(getID()).cast()){
			return;
		}
		auto builder = bsoncxx::builder::stream::document{};
		auto value = builder << "author_id" << msg.author.ID.string()
		                     << "msg" << msg.content
		                     << "msg_id" << msg.ID.string() << bsoncxx::builder::stream::finalize;
		db[msg.channelID.string()].insert_one(value);
	}

	void onReady(SleepyDiscord::Ready data) override{
		for(const auto& server : data.servers) {
			auto channels = getServerChannels(server.ID).vector();
			for(const auto& channel : channels){
				auto msgs = getMessages(channel.ID,before,channel.lastMessageID).vector();
				for(const auto& msg : msgs){
					auto res = db[msg.channelID.string()].find_one(bsoncxx::builder::stream::document{} << "msg_id"
							<< msg.author.ID.string() << bsoncxx::builder::stream::finalize);
					if(res){
						continue;
					}
					auto builder = bsoncxx::builder::stream::document{};
					auto value = builder << "author_id" << msg.author.ID.string()
					                     << "msg" << msg.content
					                     << "msg_id" << msg.ID.string() << bsoncxx::builder::stream::finalize;
					db[msg.channelID.string()].insert_one(value);
				}
			}
		}
	}
};
