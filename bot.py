import discord
import re
import asyncio
import websockets
import logging
import sys
from threading import Thread
from queue import Queue

DISCORD_TOKEN = ""
DISCORD_GUILD = ""
CHANNEL = 69
URI = "ws://localhost:8765"

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
LOGGER.addHandler(handler)

loop = asyncio.new_event_loop()
discord_loop = asyncio.new_event_loop()
client = discord.Client(loop=discord_loop)

queue_in = Queue(1)
queue_out = Queue(1)


async def handle_messages(discord_loop):
    while True:
        if client.is_ready():
            LOGGER.info("Waiting for message")
            try:
                async with websockets.connect(URI) as websocket:
                    await websocket.send(queue_out.get())
                    LOGGER.info("Message sent to application")
                    queue_in.put(await websocket.recv())

                LOGGER.info("Received message from application")
                asyncio.run_coroutine_threadsafe(
                    client.get_channel(CHANNEL).send(queue_in.get()), discord_loop)
            except Exception:
                pass


def message_loop(loop, discord_loop):
    asyncio.set_event_loop(loop)
    asyncio.get_event_loop().run_until_complete(handle_messages(discord_loop))
    asyncio.get_event_loop().run_forever()


@client.event
async def on_ready():
    LOGGER.info("Discord bot is ready")


@client.event
async def on_message(message):
    global CHANNEL
    if message.author == client.user:
        return
    if re.match("^!send .+", message.content):
        text = message.content[len("!send") + 1:]
        queue_out.put(text)


def start_bot():
    Thread(target=message_loop, args=(loop, discord_loop)).start()
    discord_loop.run_until_complete(client.start(DISCORD_TOKEN))
