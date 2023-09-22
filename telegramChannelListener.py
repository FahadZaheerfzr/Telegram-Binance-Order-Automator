import time
from telethon import TelegramClient, events
from binance.client import Client
import json
import logging
import threading
from configparser import ConfigParser
import asyncio
from data import Data, PositionData
from utils import setup_logger
import createTestOrder
import price_socket
import position_socket
from connection import DB
import telebot  # pip install pyTelegramBotAPI
from timer import start_timer, end_timer
from symbols import cryptocurrencies

logger = setup_logger("telegram-listener")


# Setting configation values
# Replace 'YOUR_API_KEY' and 'YOUR_API_SECRET' with your actual Binance API credentials
config = ConfigParser()
config.read('default_config.ini')

api_key = config.get('Telegram', 'API_ID')
api_secret = config.get('Telegram', 'API_HASH')
username = config.get('Telegram', 'USERNAME')
bot_token = config.get('Telegram', 'BOT_TOKEN')
user_input_channel = int(config.get('Telegram', 'TARGET_GROUP'))
excluded_symbols = config.get(
    'Binance', 'EXCLUDED_SYMBOLS').strip('][').split(',')
binance_api_key = config.get('Binance', 'BINANCE_API_KEY')
binance_api_secret = config.get('Binance', 'BINANCE_API_SECRET')
mode = config.get('Binance', 'MODE')

if mode == 'LIVE':
    binance_client = Client(binance_api_key, binance_api_secret)
else:
    binance_client = Client(binance_api_key, binance_api_secret, testnet=True)

WORDS_DICT = {
    'buy': [['buy', 'setup'], ['long', 'setup'], ['buy', 'high', 'sell', 'higher']],
    'sell': [['sell', 'short'], ['sell', 'setup'], ['short', 'setup'], ['sell', 'low', 'buy', 'lower']]
}

# Keep binance_client alive


def keep_alive():
    while True:
        try:
            binance_client.futures_create_order(
                symbol='XXX',
                side='SELL',
                type='MARKET',
                quantity=1,
                recvWindow=60000
            )
        except Exception as e:
            logger.error(f'Invalid Order just to keep binance Alive')
        time.sleep(60)


ping_binance = threading.Thread(target=keep_alive)
ping_binance.daemon = True
ping_binance.start()

print(excluded_symbols)

client = TelegramClient(username, api_key, api_secret)


def sell(symbol):
    try:
        print(symbol, "Called here")
        obj = createTestOrder.Binance(symbol, binance_client)
        obj.sell()
    except Exception as e:
        logger.error(f'Error in selling : {e}')
        return


def buy(symbol):
    obj = createTestOrder.Binance(symbol, binance_client)
    obj.buy()

# a function that monitors unclosed transactions


def monitor_thread(data, binance_client, bot_token):
    obj = createTestOrder.Binance(data['symbol'], binance_client)
    alert_bot = telebot.TeleBot(bot_token, parse_mode=None)
    if data['state'] == 'BUY':
        obj.buyMonitor(data['_id'], alert_bot)
    else:
        obj.sellMonitor(data['_id'], alert_bot)


# get all unclosed transactions from database
collections = DB["collections"]
buy_data = collections.find({})

threads = []
# Start threads for each transaction
for data in buy_data:
    thread = threading.Thread(target=monitor_thread,
                              args=(data, binance_client, bot_token))
    threads.append(thread)
    thread.start()



position_data = PositionData()

@client.on(events.NewMessage(chats=user_input_channel))
async def newMessageListener(event):
    try:
        newMessage = event.message.message
        newMessage = newMessage.lower()
        symbol = newMessage.split("#")[1].split(" ")[0].upper()
    except Exception as e:
        print(e)
        return

    if symbol+"USDT" in Data.data:
        logger.info(f'Already recieved message for {symbol}')
        return

    start_timer()
    logger.info(f'Recieved new message : {newMessage}')

    if symbol in excluded_symbols:
        logger.info(f'Symbol {symbol} is excluded')
        return

    position_data.position_data[cryptocurrencies.index(symbol+"USDT")] = False
    # checking for targeted keywords in message
        # logic for selling
    if ('buy' in newMessage and 'setup' in newMessage) or ('long' in newMessage and 'setup' in newMessage):
        buy(symbol)
        # logic for buying
    elif ('sell' in newMessage and 'setup' in newMessage) or ('short' in newMessage and 'setup' in newMessage):
        sell(symbol)

    # un comment this line to save messages in telegram :
    # await client.forward_messages(entity='me',messages=event.message)

with client:
    client.run_until_disconnected()
