import json
import threading
from symbols import cryptocurrencies
from data import PriceData
from utils import setup_logger
from configparser import ConfigParser
from price_precision import price_precision
from binance.client import Client
from binance.um_futures import UMFutures
from telegramChannelListener import buy, sell
import time


config = ConfigParser()
config.read('default_config.ini')

mode = config.get('Binance', 'MODE')
binance_api_key = config.get('Binance', 'BINANCE_API_KEY')
binance_api_secret = config.get('Binance', 'BINANCE_API_SECRET')
CounterTradeTickerPercentage = config.get(
    'Binance', 'COUNTER_TRADE_TICKER_PERCENTAGE')
CounterTradeTickerTimer = config.get(
    'Binance', 'COUNTER_TRADE_TICKER_TIMER')

um_futures_client = UMFutures()

if mode == 'LIVE':
    BASE_URL = 'wss://fstream.binance.com'
else:
    BASE_URL = 'wss://fstream.binancefuture.com'

if mode == 'LIVE':
    binance_client = Client(binance_api_key, binance_api_secret)
else:
    binance_client = Client(binance_api_key, binance_api_secret, testnet=True)
URL = f'{BASE_URL}/stream?streams=btcusdt@kline_1m'


# function to make api call and get candle data without socket
def getCandle(symbol):
    # api call to get candle data
    candle = binance_client.futures_klines(symbol=symbol, interval='1m', limit=1)
    print(candle,"low: ",candle[0][3])
    return candle[0][3]

# function to monitor price and send alert
def monitorPriceBuy(symbol,currentTime):
    # get candle data
    candle = float(getCandle(symbol))
    # multiply with percentage and add to candle low

    price = candle + (candle * float(CounterTradeTickerPercentage)/100 )
    print("price: ",price)
    # check if candle low is less than price
    while True:
        # get current price
        currentPrice=float(um_futures_client.ticker_price(symbol)["price"])
        if currentPrice <= price:
            # send alert
            sell(symbol)
            break
        if (time.time() - currentTime) > float(CounterTradeTickerTimer):
            break

def monitorPriceSell(symbol,currentTime):
    # get candle data
    candle = float(getCandle(symbol))
    # multiply with percentage and add to candle low

    price = candle - (candle * float(CounterTradeTickerPercentage)/100 )
    print("price: ",price)
    # check if candle low is less than price
    while True:
        # get current price
        currentPrice=float(um_futures_client.ticker_price(symbol)["price"])
        if currentPrice >= price:
            # send alert
            buy(symbol)
            break
        if (time.time() - currentTime) > float(CounterTradeTickerTimer):
            break
            


    



