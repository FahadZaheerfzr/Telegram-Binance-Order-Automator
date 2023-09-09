import json
import threading
import websocket
from symbols import cryptocurrencies
from data import PriceData

socket = f'wss://stream.binance.com:9443/stream?streams=btcusdt@ticker'

price_data = PriceData()

for i in cryptocurrencies:
    socket += f'/{i.lower()}@ticker'
  

def on_message(ws,message):
    message = json.loads(message)
    price_data.price_data[cryptocurrencies.index(message['data']['s'])] = round(float(message['data']['c']),3)
def on_error(ws,error):
    print(error)

def on_open(ws):
    print('Connection Open')

def on_close(ws,close_status,close_msg):
    print('CONNECTION CLOSED')

ws = websocket.WebSocketApp(socket,on_open=on_open,on_message=on_message,on_error=on_error,on_close=on_close)


def main():
  ws.run_forever()

s_thread = threading.Thread(target=main)
s_thread.daemon = True
s_thread.start()
