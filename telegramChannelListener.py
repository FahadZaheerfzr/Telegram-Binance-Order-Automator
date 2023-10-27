import time
#from telethon import TelegramClient, events
from binance.client import Client
import threading
from configparser import ConfigParser
from data import Data, PositionData
from utils import setup_logger
import createTestOrder
import price_socket
import position_socket
from connection import DB
import telebot  # pip install pyTelegramBotAPI
from timer import start_timer, end_timer
from symbols import cryptocurrencies
import re
from pyrogram import Client as pyroClient, filters
from getCandle import monitorPriceBuy, monitorPriceSell
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
CoolDownTime = config.get('Binance', 'COOLDOWN_TIME')
CounterTradeTicker = config.getboolean('Binance', 'COUNTER_TRADE_TICKER')
CounterTradeTickerPercentage = config.get(
    'Binance', 'COUNTER_TRADE_TICKER_PERCENTAGE')
CounterTradeTickerTimer = config.get(
    'Binance', 'COUNTER_TRADE_TICKER_TIMER')

if mode == 'LIVE':
    try:
        binance_client = Client(binance_api_key, binance_api_secret)
    except Exception as e:
        logger.error(f'Error in binance_client: {e}')
        print(f'Error in binance_client: {e}')
        binance_client = Client(binance_api_key, binance_api_secret, testnet=True)
else:
    try:
        binance_client = Client(binance_api_key, binance_api_secret, testnet=True)
    except Exception as e:
        logger.error(f'Error in binance_client: {e}')
        print(f'Error in binance_client: {e}')

WORDS_DICT = {
    'buy': [['buy', 'setup'], ['long', 'setup'], ['buy', 'high', 'sell', 'higher']],
    'sell': [['sell', 'short'], ['sell', 'setup'], ['short', 'setup'], ['sell', 'low', 'buy', 'lower']]
}

# Keep binance_client alive


def keep_alive():
    while True:
        try:
            binance_client.futures_account_balance()
        except Exception as e:
            logger.error(f'Invalid Order just to keep binance Alive')
            print(e)
        time.sleep(60)


ping_binance = threading.Thread(target=keep_alive)
ping_binance.daemon = True
ping_binance.start()

print(excluded_symbols)

#client = TelegramClient(username, api_key, api_secret)
app = pyroClient(username, api_key, api_secret)


def sell(symbol):
    try:
        print(symbol, "Called here")
        obj = createTestOrder.Binance(symbol, binance_client)
        obj.sell()
    except Exception as e:
        logger.error(f'Error in selling : {e}')
        print(f'Error in selling : {e}')
        return


def buy(symbol):
    try:
        obj = createTestOrder.Binance(symbol, binance_client)
        obj.buy()
    except Exception as e:
        logger.error(f'Error in buying : {e}')
        print(f'Error in buying : {e}')
        return

# a function that monitors unclosed transactions


def monitor_thread(data, binance_client, bot_token):
    try:
        obj = createTestOrder.Binance(data['symbol'], binance_client)
        alert_bot = telebot.TeleBot(bot_token, parse_mode=None)
        if data['state'] == 'BUY':
            obj.buyMonitor(data['_id'], alert_bot)
        else:
            obj.sellMonitor(data['_id'], alert_bot)
    except Exception as e:
        logger.error(f'Error in monitor_thread : {e}')
        print(f'Error in monitor_thread : {e}')
        return


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

buyPattern = r'\bbuy\b'
sellPattern = r'\bsell\b'
setupPattern = r'\bsetup\b'
longPattern = r'\blong\b'
shortPattern = r'\bshort\b'
highPattern = r'\bhigh\b'
higherPattern = r'\bhigher\b'
scalpPattern = r'\bscalp\b'
swingPattern = r'\bswing\b'
# in this if you want to add more key words, lets say longlong for buy,
# you can add it like this : longlongPattern = r'\bbuy\b|\blonglong\b'
#and if for example you want to add more keywords for sell, lets say shortshort for sell,
# you can add it like this : shortshortPattern = r'\bsell\b|\bshortshort\b'
#then go to line 167 and see the comment there


@app.on_message(filters.chat(user_input_channel))
async def newMessageListener(client, message):
    try:
        logger.info(f'Time sent to telegram : {message.date}')
        print(f'Time sent to telegram : {message.date}')
        content = message.caption if message.media and message.caption else message.text
        logger.info(f'Received new message : {content}')
        print(f'Received new message : {content}')
        try:
            newMessage = message.caption if message.media and message.caption else message.text
            newMessage = newMessage.lower()
            symbol = newMessage.split("#")[1].split(" ")[0].upper()
            # remove anything after \n
            symbol = symbol.split("\n")[0]
            logger.info(f'Got symbol : {symbol}')
            
        except Exception as e:
            print(e, "error in getting symbol")
            logger.error(f'Error in getting symbol : {e}')
            return

        # Check if enough time has passed since the last processing of this symbol
        current_time_minutes = time.time() / 60
        last_processed_time = Data.get_last_processed_time(symbol + "USDT")
        cooldown_minutes = int(CoolDownTime)

        if last_processed_time > 0 and current_time_minutes - last_processed_time < cooldown_minutes:
            logger.info(f'Cooldown active for {symbol}, time remaining: {round((current_time_minutes - last_processed_time) - cooldown_minutes, 2)} minutes')
            print(f'Cooldown active for {symbol}, time remaining: {round((current_time_minutes - last_processed_time) - cooldown_minutes, 2)} minutes')
            return

        if symbol + "USDT" in Data.data:
            logger.info(f'Already received message for {symbol}')
            print(f'Already received message for {symbol}')
            return


        if symbol in excluded_symbols:
            logger.info(f'Symbol {symbol} is excluded')
            print(f'Symbol {symbol} is excluded')
            return

        position_data.position_data[cryptocurrencies.index(symbol + "USDT")] = False
        # checking for targeted keywords in message
            # logic for selling
            # 'setup' in newMessage) or ('long' in newMessage and 'setup' in newMessage): use regex patterns

        if (re.search(buyPattern, newMessage, re.IGNORECASE) and re.search(setupPattern, newMessage, re.IGNORECASE)) or (re.search(longPattern, newMessage, re.IGNORECASE) and re.search(setupPattern, newMessage, re.IGNORECASE)) or (re.search(buyPattern, newMessage, re.IGNORECASE) and re.search(highPattern, newMessage, re.IGNORECASE) and re.search(higherPattern, newMessage, re.IGNORECASE)) or (re.search(buyPattern, newMessage, re.IGNORECASE) and re.search(scalpPattern, newMessage, re.IGNORECASE) and re.search(setupPattern, newMessage, re.IGNORECASE)) or (re.search(buyPattern, newMessage, re.IGNORECASE) and re.search(swingPattern, newMessage, re.IGNORECASE) and re.search(setupPattern, newMessage, re.IGNORECASE)):
            start_timer()
            if CounterTradeTicker:
                currentTime = time.time()
                logger.info(f'CounterTradeTicker is True buy')
                monitorPriceBuy(symbol, currentTime,sell)
            else:
                buy(symbol)
        # logic for selling
        elif (re.search(sellPattern, newMessage, re.IGNORECASE) and re.search(setupPattern, newMessage, re.IGNORECASE)) or (re.search(shortPattern, newMessage, re.IGNORECASE) and re.search(setupPattern, newMessage, re.IGNORECASE)) or (re.search(sellPattern, newMessage, re.IGNORECASE) and re.search(swingPattern, newMessage, re.IGNORECASE) and re.search(setupPattern, newMessage, re.IGNORECASE)) or (re.search(shortPattern, newMessage, re.IGNORECASE) and re.search(swingPattern, newMessage, re.IGNORECASE) and re.search(setupPattern, newMessage, re.IGNORECASE)) or (re.search(sellPattern, newMessage, re.IGNORECASE) and re.search(scalpPattern, newMessage, re.IGNORECASE) and re.search(setupPattern, newMessage, re.IGNORECASE)) or (re.search(shortPattern, newMessage, re.IGNORECASE) and re.search(scalpPattern, newMessage, re.IGNORECASE) and re.search(setupPattern, newMessage, re.IGNORECASE)):
            start_timer()
            if CounterTradeTicker:
                currentTime = time.time()
                logger.info(f'CounterTradeTicker is True sell')
                monitorPriceSell(symbol, currentTime,buy)
            else:
                sell(symbol)
        #here, lets say you added search for longlong in buyPattern and shortshort in sellPattern
        #then you can add this condition here :
        #elif (re.search(buyPattern, newMessage, re.IGNORECASE) and re.search(longlongPattern, newMessage, re.IGNORECASE)):
        #    buy(symbol)
        #elif (re.search(sellPattern, newMessage, re.IGNORECASE) and re.search(shortshortPattern, newMessage, re.IGNORECASE)):
        #    sell(symbol)
        
        # un comment this line to save messages in telegram :
        # await client.forward_messages(entity='me',messages=event.message)
    except Exception as e:
        logger.error(f'Error in newMessageListener : {e}')
        print(f'Error in newMessageListener : {e}')

# with client:
#     client.run_until_disconnected()

app.run()