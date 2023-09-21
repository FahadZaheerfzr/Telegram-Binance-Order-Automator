import json
import threading
import websocket
from symbols import cryptocurrencies
from data import PriceData
from utils import setup_logger
from configparser import ConfigParser
from price_precision import price_precision

config = ConfigParser()
config.read('default_config.ini')

mode = config.get('Binance','MODE')


if mode == 'LIVE':
    BASE_URL = 'wss://fstream.binance.com'
else:
    BASE_URL = 'wss://fstream.binancefuture.com'

socket = f'{BASE_URL}/stream?streams=btcusdt@ticker'

price_data = PriceData()

price_data_logger = setup_logger('price_data_logger')

for i in cryptocurrencies:
    socket += f'/{i.lower()}@ticker'
  

def on_message(ws,message):
    message = json.loads(message) 
    price_data.price_data[cryptocurrencies.index(message['data']['s'])] = round(float(message['data']['c']), price_precision[message['data']['s']])
    #price_data_logger.info(price_data.price_data+['\n'])



def on_error(ws,error):
    print(error)

def on_open(ws):
    print('Price connection Open')

def on_close(ws,close_status,close_msg):
    print('CONNECTION CLOSED')

ws = websocket.WebSocketApp(socket,on_open=on_open,on_message=on_message,on_error=on_error,on_close=on_close)


def main():
  ws.run_forever()

s_thread = threading.Thread(target=main)
s_thread.daemon = True
s_thread.start()
