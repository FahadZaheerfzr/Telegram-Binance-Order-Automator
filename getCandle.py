import json
import threading
from symbols import cryptocurrencies
from data import PriceData,Data
from utils import setup_logger
from configparser import ConfigParser
from price_precision import price_precision
from binance.client import Client
from binance.um_futures import UMFutures
import time
from utils import setup_logger



config = ConfigParser()
config.read('default_config.ini')
loggerCandle = setup_logger("getCandle")
loggerBuy = setup_logger("Monitor-buy")
loggerSell = setup_logger("Monitor-sell")

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
    try:
        binance_client = Client(binance_api_key, binance_api_secret)
    except Exception as e:
        loggerCandle.error("Error in binance_client, get_candle: %s",e)
        print("Error in binance_client: ",e)
        binance_client = Client(binance_api_key, binance_api_secret, testnet=True)
else:
    try:
        binance_client = Client(binance_api_key, binance_api_secret, testnet=True)
    except Exception as e:
        loggerCandle.error("Error in binance_client get_candle: %s",e)
        print("Error in binance_client: ",e)
URL = f'{BASE_URL}/stream?streams=btcusdt@kline_1m'

price_data = PriceData()
# function to make api call and get candle data without socket
def getCandle(symbol):
    # api call to get candle data
    try:
        candle = binance_client.futures_klines(symbol=symbol, interval='1m', limit=1)
        loggerCandle.info("candle: %s",candle)
        loggerCandle.info("low: %s", candle[0][3])
        print(candle,"low: ",candle[0][3])
        return candle[0][3]
    except Exception as e:
        loggerCandle.error("Error in getCandle: %s",e)
        print("Error in getCandle: ",e)
        return
# function to monitor price and send alert
def monitorPriceBuy(symbol,currentTime,sell):
    data = Data()
    data.update_last_processed_time(symbol+"USDT")
    # get candle data
    try:
        candle = float(getCandle(symbol+"USDT"))
        # multiply with percentage and add to candle low

        price = candle + (candle * float(CounterTradeTickerPercentage)/100 )
        loggerBuy.info("Trigger price: %s",price)
        print("Trigger price: ",price)
        # check if candle low is less than price
        while True:
            # get current price

            try:
                currentPrice = price_data.price_data[cryptocurrencies.index(symbol+"USDT")]
            except Exception as e:
                currentPrice = float(um_futures_client.ticker_price(symbol+"USDT")["price"])
            
            # print (currentPrice,price,time.time()-currentTime)
            if currentPrice >= price:
                # send alert
                loggerBuy.info("buy - currentPrice: %s - priceToSell: %s",currentPrice,price)
                sell(symbol)
                break
            if (time.time() - currentTime) > float(CounterTradeTickerTimer)*60:
                print ("break")
                break
    except Exception as e:
        loggerBuy.error("Error in monitorPriceBuy: %s",e)
        print("Error in monitorPriceBuy: ",e)
        return

def monitorPriceSell(symbol,currentTime,buy):
    data = Data()
    data.update_last_processed_time(symbol+"USDT")
    # get candle data
    try:
        candle = float(getCandle(symbol+"USDT"))
        # multiply with percentage and add to candle low

        price = candle - (candle * float(CounterTradeTickerPercentage)/100 )
        loggerSell.info("Trigger price: %s",price)
        print("Trigger price: ",price)
        # check if candle low is less than price
        while True:
            # get current price
            try:
                currentPrice = price_data.price_data[cryptocurrencies.index(symbol+"USDT")]
            except Exception as e:
                currentPrice = float(um_futures_client.ticker_price(symbol+"USDT")["price"])
            
            if currentPrice < price:
                loggerSell.info("sell - currentPrice: %s - priceToSell: %s",currentPrice,price)
                # send alert
                buy(symbol)
                break
            if (time.time() - currentTime) > float(CounterTradeTickerTimer)*60:
                break
            
    except Exception as e:
        loggerSell.error("Error in monitorPriceSell: %s",e)
        print("Error in monitorPriceSell: ",e)
        return


    



