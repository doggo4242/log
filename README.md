# log
A simple discord bot for logging messages

## Usage
See the [wiki](https://github.com/doggo4242/log/wiki) for usage instructions.

## Install
Clone the repo, and create the required files in the `config` directory. 

`auth_users.txt`: Contains user ids of users who you want to allow to shut down the bot and change the channel in which user content is stored.

Build the image:
```
LOG_TOKEN=<token> docker-compose build
```

Start the bot:
```
docker-compose up -d
```
Done :)
