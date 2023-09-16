import json
import time
import threading
import websocket
from symbols import cryptocurrencies
from data import PositionData
from utils import setup_logger
from binance.client import Client
from configparser import ConfigParser
from binance.um_futures import UMFutures
import telebot

config = ConfigParser()
config.read('default_config.ini')

binance_api_key = config.get('Binance','BINANCE_API_KEY')
binance_api_secret = config.get('Binance','BINANCE_API_SECRET')
mode = config.get('Binance','MODE')

if mode == 'LIVE':
    binance_client = Client(binance_api_key, binance_api_secret)
else:
    binance_client = Client(binance_api_key, binance_api_secret, testnet=True)


listen_key = binance_client.futures_stream_get_listen_key()

if mode == 'LIVE':
    BASE_URL = 'wss://fstream.binance.com'
else:
    BASE_URL = 'wss://fstream.binancefuture.com'

socket = f'{BASE_URL}/ws/{listen_key}'

position_data = PositionData()

# price_data_logger = setup_logger('price_data_logger')

# for i in cryptocurrencies:
#     socket += f'/{i.lower()}@ticker'


BOT_TOKEN = config.get('Telegram','BOT_TOKEN')

alert_bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)


def on_message(ws,message):
    message = json.loads(message)
    if message['e'] == 'ORDER_TRADE_UPDATE':
        message = message['o']
        if message['ot'] == 'STOP_MARKET' and message['X'] == 'FILLED':
            print(message)
            position_data.position_data[cryptocurrencies.index(message['s'])] = True
    #price_data_logger.info(price_data.price_data+['\n'])


def on_error(ws,error):
    print(error)

def on_open(ws):
    print('Position connection open')

def on_close(ws,close_status,close_msg):
    print('CONNECTION CLOSED')

ws = websocket.WebSocketApp(socket,on_open=on_open,on_message=on_message,on_error=on_error,on_close=on_close)

def main():
  ws.run_forever()

def refresh_listen_key():
    while True:
        binance_client.futures_stream_keepalive(listen_key)
        time.sleep(60*30)



r_thread = threading.Thread(target=refresh_listen_key)
r_thread.daemon = True
r_thread.start()

s_thread = threading.Thread(target=main)
s_thread.daemon = True
s_thread.start()