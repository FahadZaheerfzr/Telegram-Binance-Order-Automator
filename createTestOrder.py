import time
from binance.client import Client
from configparser import ConfigParser
from binance.um_futures import UMFutures
import telebot  # pip install pyTelegramBotAPI
from data import Data, PriceData, PositionData
import dotenv
import sys
from utils import setup_logger
from symbols import cryptocurrencies
import price_precision
from connection import DB
from timer import end_timer
import threading
from configparser import ConfigParser
from getCandle import monitorPriceBuy, monitorPriceSell
config = ConfigParser()
config.read('default_config.ini')

# Read a variable called CONFIG from dotenv
# This variable will contain the path to the configuration file
SYMBOLS = dotenv.dotenv_values()['SYMBOLS']

time_logger = setup_logger("time-logger")

logger = setup_logger("binance-order")

collections = DB["collections"]  # Replace with your collection name

SYMBOLS = SYMBOLS.split(',')
Stoploss_To_Entry= config.getboolean('Binance', 'STOPLOSS_TO_ENTRY')
# COUNTER_TRADE_TICKER
CounterTradeTicker = config.getboolean('Binance', 'COUNTER_TRADE_TICKER')

class Binance():

    def __init__(self, symbol, binance_client):

        self.price_data = PriceData()
        self.position_data = PositionData()
        self.stoplossUpdateQty = 0
        self.orderIds = []

        try:
            # reading config file
            self.configur = ConfigParser()
            if symbol.upper() in SYMBOLS:
                print("Special Symbol")
                print(f'{symbol.lower()}_config.ini')
                self.configur.read(f'{symbol.lower()}_config.ini')
            else:
                self.configur.read('default_config.ini')
            self.stop_loss_levels = self.configur.getint(
                'Binance', 'STOP_LOSS_UPDATE_LEVEL')
            self.bot_token = self.configur.get('Telegram', 'BOT_TOKEN')
            self.user = self.configur.getint('Telegram', 'MY_USER')
            self.symbol = symbol+"USDT"
            self.data = Data()
            # Replace 'YOUR_API_KEY' and 'YOUR_API_SECRET' with your actual Binance API credentials
            # self.api_key = self.configur.get('Binance','BINANCE_API_KEY')
            # self.api_secret = self.configur.get('Binance','BINANCE_API_SECRET')
            # Initialize the Binance client
            # self.mode = self.configur.get('Binance','MODE')
            self.client = binance_client
            # if self.mode == 'LIVE':
            #     self.client = Client(self.api_key, self.api_secret)
            # else:
            #     self.client = Client(self.api_key, self.api_secret, testnet=True)

            # for accessing public api
            self.um_futures_client = UMFutures()

        except Exception as e:
            logger.error('FAILED TO INITIATE TRADE')
            logger.error(f'ERROR INDENTIFIED : {e}')
            print("FAILED TO INITIATE TRADE")
            print(f'ERROR INDENTIFIED : {e}')
            sys.exit()

    def set_leverage(self):
        time_start = time.time()
        try:
            leverage = int(self.configur.get('Binance', 'LEVERAGE'))
            # self.symbol = self.configur.get('Binance','SYMBOL')
            logger.info(f'ATTEMPTING TO SET LEVERAGE TO with api call where symbol is {self.symbol} and leverage is {leverage}')
            self.client.futures_change_leverage(
                symbol=self.symbol, leverage=leverage, recvWindow=60000)
            time_end = time.time()
            time_logger.info(
                f'TIME TAKEN TO SET LEVERAGE : {time_end-time_start}')
            print(f'TIME TAKEN TO SET LEVERAGE : {time_end-time_start}')
            logger.info(f'LEVERAGE SET TO : {leverage}')
            print(f'LEVERAGE SET TO : {leverage}')

        except Exception as e:
            logger.error('FAILED TO SET LEVERAGE')
            logger.error(f'ERROR INDENTIFIED : {e}')
            print("FAILED TO SET LEVERAGE")
            print(f'ERROR INDENTIFIED : {e}')
            sys.exit()

    def set_margintype(self):
        time_start = time.time()
        try:
            margin_type = self.configur.get('Binance', 'MARGIN_TYPE')
            # symbol = self.configur.get('Binance','SYMBOL')
            logger.info(f'ATTEMPTING TO SET MARGIN TYPE with api call TO {margin_type} and symbol is {self.symbol}')
            self.client.futures_change_margin_type(
                symbol=self.symbol, marginType=margin_type, recvWindow=60000)
            time_end = time.time()
            time_logger.info(
                f'TIME TAKEN TO SET MARGIN TYPE : {time_end-time_start}')
            print(f'TIME TAKEN TO SET MARGIN TYPE : {time_end-time_start}')
            logger.info(f'MARGIN TYPE SET TO : {margin_type}')
            print(f'MARGIN TYPE SET TO : {margin_type}')

        except Exception as e:
            logger.error('FAILED TO SET MARGIN TYPE')
            print("FAILED TO SET MARGIN TYPE")
            logger.error(f'ERROR INDENTIFIED : {e}')
            print(f'ERROR INDENTIFIED : {e}')

    # def get_quantity(self):

    #     try:
    #         pass
    #     except Exception as e:
    #         pass

    async def pingBinance(self):
        try:
            self.client.futures_ping()
        except Exception as e:
            logger.error(f'FAILED TO PING BINANCE')
            print("FAILED TO PING BINANCE")
            logger.error(f'ERROR INDENTIFIED : {e}')
            print(f'ERROR INDENTIFIED : {e}')
            sys.exit()

    def buyMonitor(self, item_id, alert_bot):
        try:
            logger.info('THREAD STARTED')
            print('THREAD STARTED')
            item = collections.find_one({"_id": item_id})
            self.stoplossUpdateQty = item['stoplossUpdateQty']
            entry_price = item['entry_price']
            quantity = item['quantity']
            exit_prices = item['exit_points']
            stop_loss_price = item['stop_loss']
            exit_target_quantity_list = item['exit_target_quantity_list']
            current_index = item['index']
            stop_loss_index = 0
            lastpnl = 0
            while True:
                time.sleep(0.2)
                current_price = float(
                    self.um_futures_client.ticker_price(self.symbol)["price"])
                positionClosed = self.position_data.position_data[cryptocurrencies.index(
                    self.symbol)]  # get position data from position_data.py
                # print (current_price)
                # positions = PositionData.position_data

                if current_index == len(exit_prices):
                    trades = self.client.futures_account_trades(
                        symbol=self.symbol, recvWindow=60000)
                    # acc to current index we will sum up the pnl in trades from the end of trades
                    # we will check order id in trades and if it is in order id list then we will add it to pnl


                    pnl = 0
                    for i in range(len(trades)):
                        if trades[i]['orderId'] in self.orderIds:
                            logger.info(f'found order id : {trades[i]["orderId"]}')

                            pnlNew = trades[i]
                            pnl = float(pnlNew["realizedPnl"]) + pnl
                    logger.info(f'when exit then lastpnl remains {pnl}')

                    for y in range(3):
                        try:
                            alert_bot.send_message(
                                self.user, f'POSITION CLOSED. FINAL PNL : {pnl}')
                            break
                        except Exception as e:
                            logger.error(f'FAILED TO SEND TELEGRAM MESSAGE')
                            logger.error(f'ERROR INDENTIFIED : {e}')
                            print("FAILED TO SEND TELEGRAM MESSAGE")
                            print(f'ERROR INDENTIFIED : {e}')
                            time.sleep(10)
                    logger.info(f'ALL EXIT POINTS ACHIEVED')
                    print('ALL EXIT POINTS ACHIEVED')
                    self.data.remove(self.symbol)
                    collections.delete_one({"_id": item_id})
                    cancel_order = self.client.futures_cancel_all_open_orders(
                        symbol=self.symbol, recvWindow=60000)
                    sys.exit()

                if positionClosed == True:
                    trades = self.client.futures_account_trades(
                        symbol=self.symbol, recvWindow=60000)

                    pnl = 0
                    for i in range(len(trades)):
                        if trades[i]['orderId'] in self.orderIds:
                            logger.info(f'found order id : {trades[i]["orderId"]}')

                            pnlNew = trades[i]
                            pnl = float(pnlNew["realizedPnl"]) + pnl
                    for y in range(3):
                        try:
                            alert_bot.send_message(
                                self.user, f'POSITION CLOSED. FINAL PNL : {pnl}')
                            break
                        except Exception as e:
                            logger.error(f'FAILED TO SEND TELEGRAM MESSAGE')
                            logger.error(f'ERROR INDENTIFIED : {e}')
                            print("FAILED TO SEND TELEGRAM MESSAGE")
                            print(f'ERROR INDENTIFIED : {e}')
                            time.sleep(10)
                    logger.info(
                        f'POSITION {self.symbol} CLOSED BY STOP LOSS ORDER')
                    print(f'POSITION {self.symbol} CLOSED BY STOP LOSS ORDER')
                    for y in range(3):
                        try:
                            alert_bot.send_message(
                                self.user, f'POSITION ${self.symbol} CLOSED BY STOP LOSS ORDER')
                            break
                        except Exception as e:
                            logger.error(f'FAILED TO SEND TELEGRAM MESSAGE')
                            logger.error(f'ERROR INDENTIFIED : {e}')
                            print("FAILED TO SEND TELEGRAM MESSAGE")
                            print(f'ERROR INDENTIFIED : {e}')
                            time.sleep(10)

                    collections.delete_one({"_id": item_id})
                    self.data.remove(self.symbol)
                    cancel_order = self.client.futures_cancel_all_open_orders(
                        symbol=self.symbol, recvWindow=60000)
                    sys.exit()

                if current_price >= exit_prices[current_index]:
                    sell_price = exit_prices[current_index]
                    sell_quantity = (
                        int(exit_target_quantity_list[current_index])/100)*quantity

                    if sell_quantity > 1:
                        sell_quantity = int(sell_quantity)
                    else:
                        sell_quantity = round(
                            sell_quantity, price_precision.quantity_precision[self.symbol])
                    try:
                        if current_index == len(exit_prices)-1:
                            positions = next(obj for obj in self.client.futures_account(
                                recvWindow=60000)['positions'] if obj['symbol'] == self.symbol)
                            if positions['positionAmt'][0] == "-":
                                positions['positionAmt'] = positions['positionAmt'][1:]
                            logger.info(f'api request to create order with symbol {self.symbol} and side sell and type market and quantity {positions["positionAmt"]} and recvWindow 60000')
                            sell_order = self.client.futures_create_order(
                                symbol=self.symbol,
                                side='SELL',
                                type='MARKET',
                                reduceOnly=True,
                                quantity=float(positions['positionAmt']),
                                recvWindow=60000
                            )
                            current_index += 1
                            cancel_order = self.client.futures_cancel_all_open_orders(
                                symbol=self.symbol, recvWindow=60000)
                        else:
                            logger.info(f'api request to create order with symbol {self.symbol} and side sell and type market and quantity {sell_quantity} and recvWindow 60000')
                            sell_order = self.client.futures_create_order(
                                symbol=self.symbol,
                                side='SELL',
                                type='MARKET',
                                quantity=sell_quantity,
                                recvWindow=60000,
                                reduceOnly=True,
                            )
                            current_index += 1
                    except Exception as e:
                        logger.error(
                            f'FAILED TO SELL AT EXIT POINT {current_index+1}')
                        print(f'FAILED TO SELL AT EXIT POINT {current_index+1}')
                        logger.error(f'ERROR INDENTIFIED : {e}')
                        print(f'ERROR INDENTIFIED : {e}')
                        continue

                    cancel_order = self.client.futures_cancel_all_open_orders(
                        symbol=self.symbol, recvWindow=60000)


                    self.stoplossUpdateQty -= sell_quantity


                    collections.update_one(
                        {"_id": item_id}, {"$set": {"index": current_index, "stoplossUpdateQty": self.stoplossUpdateQty}})

                    if sell_order:
                        logger.info(f'EXIT POINT {current_index} ACHIEVED')
                        print(f'EXIT POINT {current_index} ACHIEVED')
                        logger.info(f'SOLD at {current_price}')
                        print(f'SOLD at {current_price}')

                    alert_bot.send_message(
                        self.user, f'EXIT POINT {current_index} ACHIEVED. SELLING {sell_quantity} {self.symbol} AT {current_price}')
                    
                    if current_index % self.stop_loss_levels == 0 and current_index != 0:
                        if stop_loss_index == 0 or Stoploss_To_Entry:
                            stop_loss_price = entry_price
                            stop_loss_index += 1
                        else:
                            stop_loss_price = exit_prices[stop_loss_index-1]

                    stop_loss_price = round(
                        stop_loss_price, price_precision.price_precision[self.symbol])

                    logger.info(f'old stoploss {self.stoplossUpdateQty}')

                    self.stoplossUpdateQty = round(
                            self.stoplossUpdateQty, price_precision.quantity_precision[self.symbol])
                    logger.info(f'stoploss updating at {self.stoplossUpdateQty}, sell qty is {sell_quantity}')
                    logger.info(f'api request to create order with symbol {self.symbol} and side sell and type stop market and quantity {self.stoplossUpdateQty} and stopPrice {stop_loss_price} and recvWindow 60000 and reduceOnly True')

                    if current_index != len(exit_prices):
                        for i in range (10):
                            time.sleep(3)
                            try:
                                updated_stop_loss = self.client.futures_create_order(
                                    symbol=self.symbol,
                                    side='SELL',
                                    type='STOP_MARKET',
                                    quantity=self.stoplossUpdateQty,
                                    stopPrice=stop_loss_price,
                                    recvWindow=60000,
                                    reduceOnly=True,
                                )
                                collections.update_one(
                                    {"_id": item_id}, {"$set": {"stop_loss": stop_loss_price}})
                                alert_bot.send_message(
                                    self.user, f'STOP LOSS ORDER UPDATED FOR {self.stoplossUpdateQty} {self.symbol} at {stop_loss_price}.')
                                logger.info(
                                    f'STOP LOSS ORDER UPDATED FOR {self.stoplossUpdateQty} {self.symbol} at {stop_loss_price}.')
                                print(
                                    f'STOP LOSS ORDER UPDATED FOR {self.stoplossUpdateQty} {self.symbol} at {stop_loss_price}.')                           
                                break
                            except Exception as e:
                                logger.error("UNABLE TO PLACE STOPP LOSS ORDER. RETRYING...")
                                print("UNABLE TO PLACE STOPP LOSS ORDER. RETRYING...")
                                logger.error(e)
                                print(e)
                                time.sleep(3)
                                continue
                    logger.info(f'getting trades from api with symbol {self.symbol} and recvWindow 60000')
                    trades = self.client.futures_account_trades(
                        symbol=self.symbol, recvWindow=60000)
                    pnl = 0
                    for i in range(len(trades)):
                        logger.info(f'order ids : {self.orderIds}')
                        if trades[i]['orderId'] in self.orderIds:
                            logger.info(f'found order id : {trades[i]["orderId"]}')
                            pnlNew = trades[i]
                            pnl = float(pnlNew["realizedPnl"]) + pnl
                    alert_bot.send_message(
                        self.user, f'CURRENT PNL : {pnl}')

                    # lastpnl = pnl
        except Exception as e:
            logger.error('FAILED TO MONITOR PRICE')
            print("FAILED TO MONITOR PRICE")
            logger.error(f'ERROR INDENTIFIED : {e}')
            print(f'ERROR INDENTIFIED : {e}')

    def buy(self):
        try:
            # setting desired margin type and leverage
            # self.set_leverage()
            # self.set_margintype()
            budget = self.configur.getfloat('Binance', 'USDT_BUDGET')
            print("symb in buy is ",self.symbol)
            try:
                current_price = self.price_data.price_data[cryptocurrencies.index(
                    self.symbol)]
            except Exception as e:
                current_price = float(
                    self.um_futures_client.ticker_price(self.symbol)["price"])
            

            logger.info(f'CURRENT PRICE OF {self.symbol} is {current_price}')
            print(f'CURRENT PRICE OF {self.symbol} is {current_price}')
            quantity = budget/current_price


            quantity = float(round(quantity, price_precision.quantity_precision[self.symbol]))

            logger.info(
                f'ATTEMPTING TO BUY {quantity} {self.symbol} at {current_price}')
            print(
                f'ATTEMPTING TO BUY {quantity} {self.symbol} at {current_price}')
            logger.info(f'api request to create order with symbol {self.symbol} and side buy and type market and quantity {quantity} and recvWindow 60000')
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity,
                recvWindow=60000,
            )
            print(order,"orderrr")
            logger.info(
                f'ORDER PLACED : {order["orderId"]} at {current_price}')
            print(f'ORDER PLACED : {order["orderId"]} at {current_price}')
            self.orderIds.append(order["orderId"])

            time_end = end_timer()

            
            # if CounterTradeTicker:
            #     current_time = time.time()
            #     s_thread = threading.Thread(
            #         target=monitorPriceBuy, args=(self.symbol, current_time,))
            #     s_thread.daemon = True
            #     s_thread.start()
            

            time_logger.info(f'TIME TAKEN TO PLACE ORDER : {time_end}')
            print(f'TIME TAKEN TO PLACE ORDER : {time_end}')
            self.data.add(self.symbol)
            self.data.update_last_processed_time(self.symbol)

            # Check the response
            if order:
                order_details = self.client.futures_get_order(
                    symbol=self.symbol, orderId=order['orderId'], recvWindow=60000)
                entry_price = float(order_details['avgPrice'])
                stop_loss_percentage = self.configur.getfloat(
                    'Binance', 'STOP_PERCENTAGE')
                stop_loss_price = round(entry_price - ((stop_loss_percentage / 100)
                                        * entry_price), price_precision.price_precision[self.symbol])
                logger.info(
                    f'ATTEMPTING TO PLACE STOP LOSS ORDER FOR {quantity} {self.symbol} at {stop_loss_price}')
                print(
                    f'ATTEMPTING TO PLACE STOP LOSS ORDER FOR {quantity} {self.symbol} at {stop_loss_price}')
                time_start = time.time()
                for y in range(10):
                    try:
                        print(f"Trying to place stop loss order with {quantity} {self.symbol} at {stop_loss_price} ")
                        logger.info(f"Trying to place stop loss order with  api {quantity} {self.symbol} at {stop_loss_price} ")
                        stop_loss_order = self.client.futures_create_order(
                            symbol=self.symbol,
                            side='SELL',
                            type='STOP_MARKET',
                            quantity=quantity,
                            stopPrice=stop_loss_price,
                            recvWindow=60000,
                            reduceOnly=True,
                        )
                        break
                    except Exception as e:
                        logger.error(
                            "UNABLE TO PLACE STOPP LOSS ORDER. RETRYING...")
                        logger.error(e)
                        print("UNABLE TO PLACE STOPP LOSS ORDER. RETRYING...")
                        print(e)
                        time.sleep(3)
                        continue

                time_end = time.time()
                time_logger.info(
                    f'TIME TAKEN TO PLACE STOP LOSS ORDER : {time_end-time_start}')
                print(
                    f'TIME TAKEN TO PLACE STOP LOSS ORDER : {time_end-time_start}')
                logger.info(
                    f'ORDER PLACED : {order["orderId"]} at {entry_price}')
                print(f'ORDER PLACED : {order["orderId"]} at {entry_price}')
                logger.info(
                    f'STOP LOSS ORDER PLACED : {stop_loss_order["orderId"]} at {stop_loss_price}')
                print(
                    f'STOP LOSS ORDER PLACED : {stop_loss_order["orderId"]} at {stop_loss_price}')

                # getting trade data ready
                exit_points = self.configur.getint(
                    'Binance', 'NUMBER_OF_EXIT_POINTS')
                exit_percentages = self.configur.get(
                    'Binance', 'EXIT_PERCENTAGES')

                # Convert a string to a list
                exit_target_quantity_list = exit_percentages.strip(
                    '][').split(',')

                exit_target_percentages_list = []  # store percentages

                for i in range(1, exit_points+1):
                    exit_target_percentages_list.append(
                        self.configur.getfloat('Binance', f'EXIT_{i}_TARGET_PRICE'))

                exit_prices = []    # store target prices
                # convert percentages into prices
                for i in exit_target_percentages_list:
                    exit_prices.append(((i * entry_price) / 100) + entry_price)

        except Exception as e:
            logger.error(f'FAILED TO PLACE AN ORDER')
            logger.error(f'ERROR INDENTIFIED : {e}')
            print("FAILED TO PLACE AN ORDER")
            print(f'ERROR INDENTIFIED : {e}')
            return
        self.stoplossUpdateQty=quantity.__round__(2)
        for i in range(3):
            try:
                alert_bot = telebot.TeleBot(self.bot_token, parse_mode=None)
                alert_bot.send_message(
                    self.user, f'BUY ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {entry_price}.\nSTOP LOSS PRICE : {stop_loss_price}\nEXIT POINTS : {exit_prices}')
                alert_bot.send_message(
                    self.user, f'STOP LOSS ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {stop_loss_price}.')
                break
            except Exception as e:
                time.sleep(10)
                if i == 2:
                    logger.error(f'FAILED TO SEND TELEGRAM MESSAGE')
                    logger.error(f'ERROR INDENTIFIED : {e}')
                    print("FAILED TO SEND TELEGRAM MESSAGE")
                    print(f'ERROR INDENTIFIED : {e}')
                else:
                    logger.error(
                        f'FAILED TO SEND TELEGRAM MESSAGE. RETRYING...')
                    logger.error(f'ERROR INDENTIFIED : {e}')
                    print("FAILED TO SEND TELEGRAM MESSAGE. RETRYING...")
                    print(f'ERROR INDENTIFIED : {e}')

        # Insert the document into the collection
        item = collections.insert_one({
            'symbol': self.symbol[:-4],
            'stoplossUpdateQty': quantity,
            'entry_price': entry_price,
            'quantity': quantity,
            'state': 'BUY',
            'exit_target_quantity_list': exit_target_quantity_list,
            'stop_loss': stop_loss_price,
            'exit_points': exit_prices,
            'index': 0,
        })

        # Monitor the price of the token

        s_thread = threading.Thread(
            target=self.buyMonitor, args=(item.inserted_id, alert_bot,))
        s_thread.daemon = True
        s_thread.start()

    # Monitor the price of the token

    def sellMonitor(self, item_id, alert_bot):
        try:
            logger.info('THREAD STARTED')
            print('THREAD STARTED')
            item = collections.find_one({"_id": item_id})
            self.stoplossUpdateQty = item['stoplossUpdateQty']
            entry_price = item['entry_price']
            quantity = item['quantity']
            exit_prices = item['exit_points']
            stop_loss_price = item['stop_loss']
            exit_target_quantity_list = item['exit_target_quantity_list']
            current_index = item['index']
            stop_loss_index = 0
            lastpnl = 0
            while True:
                time.sleep(0.2)

                positionClosed = self.position_data.position_data[cryptocurrencies.index(
                    self.symbol)]  # get position data from position_data.py

                if current_index == len(exit_prices):
                    trades = self.client.futures_account_trades(
                        symbol=self.symbol, recvWindow=60000)

                    pnl = 0
                    for i in range(len(trades)):
                        if trades[i]['orderId'] in self.orderIds:
                            pnlNew = trades[i]
                            pnl = float(pnlNew["realizedPnl"]) + pnl 
                    logger.info(f'when exit then lastpnl remains {pnl}')
                    alert_bot.send_message(
                        self.user, f'POSITION CLOSED. FINAL PNL : {pnl}')

                    logger.info(f'ALL EXIT POINTS ACHIEVED')
                    print('ALL EXIT POINTS ACHIEVED')
                    self.data.remove(self.symbol)
                    collections.delete_one({"_id": item_id})
                    cancel_order = self.client.futures_cancel_all_open_orders(
                        symbol=self.symbol, recvWindow=60000)
                    sys.exit()

                if positionClosed == True:


                    logger.info(
                        f'POSITION ${self.symbol} CLOSED BY STOP LOSS ORDER')
                    print(f'POSITION ${self.symbol} CLOSED BY STOP LOSS ORDER')
                    alert_bot.send_message(
                        self.user, f'POSITION ${self.symbol} CLOSED BY STOP LOSS ORDER')
                    trades = self.client.futures_account_trades(
                        symbol=self.symbol, recvWindow=60000)
                    pnl = 0
                    for i in range(len(trades)):
                        if trades[i]['orderId'] in self.orderIds:
                            pnlNew = trades[i]
                            pnl = float(pnlNew["realizedPnl"]) + pnl   

                    alert_bot.send_message(
                        self.user, f'POSITION CLOSED. FINAL PNL : {pnl}')
                    self.data.remove(self.symbol)
                    collections.delete_one({"_id": item_id})
                    cancel_order = self.client.futures_cancel_all_open_orders(
                        symbol=self.symbol, recvWindow=60000)

                    sys.exit()

                current_price = self.price_data.price_data[cryptocurrencies.index(
                    self.symbol)]
                
    
                if current_price <= exit_prices[current_index]:
                    sell_quantity = (
                        int(exit_target_quantity_list[current_index])/100)*quantity

                    if sell_quantity > 1:
                        sell_quantity = int(sell_quantity)
                    else:
                        sell_quantity = round(
                            sell_quantity, price_precision.quantity_precision[self.symbol])
                    try:
                        if current_index == len(exit_prices)-1:
                            positions = next(obj for obj in self.client.futures_account(
                                recvWindow=60000,)['positions'] if obj['symbol'] == self.symbol)
                            if positions['positionAmt'][0] == "-":
                                sell_quantity = positions['positionAmt'][1:]
                            logger.info(f'api request to create order with symbol {self.symbol} and side buy and type market and quantity {sell_quantity} and recvWindow 60000 and reduceOnly True')
                            sell_order = self.client.futures_create_order(
                                symbol=self.symbol,
                                side='BUY',
                                type='MARKET',
                                quantity=float(sell_quantity),
                                recvWindow=60000,
                                reduceOnly=True,
                            )
                            current_index += 1
                            cancel_order = self.client.futures_cancel_all_open_orders(
                                symbol=self.symbol, recvWindow=60000)
                        else:
                            logger.info(f'api request to create order with symbol {self.symbol} and side buy and type market and quantity {sell_quantity} and recvWindow 60000')
                            sell_order = self.client.futures_create_order(
                                symbol=self.symbol,
                                side='BUY',
                                type='MARKET',
                                quantity=sell_quantity,
                                reduceOnly=True,
                                recvWindow=60000
                            )
                            current_index += 1
                    except Exception as e:
                        logger.error(
                            f'FAILED TO SELL AT EXIT POINT {current_index+1}')
                        logger.error(f'ERROR INDENTIFIED : {e}')
                        print(f'FAILED TO SELL AT EXIT POINT {current_index+1}')
                        print(f'ERROR INDENTIFIED : {e}')
                        continue

                    cancel_order = self.client.futures_cancel_all_open_orders(
                        symbol=self.symbol, recvWindow=60000)
                    self.stoplossUpdateQty -= sell_quantity
                    collections.update_one(
                        {"_id": item_id}, {"$set": {"index": current_index, "stoplossUpdateQty": self.stoplossUpdateQty}})

                    if sell_order:
                        logger.info(f'EXIT POINT {current_index} ACHIEVED')
                        print(f'EXIT POINT {current_index} ACHIEVED')
                        logger.info(f'SOLD at {current_price}')
                        print(f'SOLD at {current_price}')



                    alert_bot.send_message(
                        self.user, f'EXIT POINT {current_index} ACHIEVED. BUYING {sell_quantity} {self.symbol} AT {current_price}.')
                    
                    if current_index % self.stop_loss_levels == 0 and current_index != 0:
                        if stop_loss_index == 0 or Stoploss_To_Entry:
                            stop_loss_price = entry_price
                            stop_loss_index += 1
                        else:
                            stop_loss_price = exit_prices[stop_loss_index-1]
                    

                    stop_loss_price = round(stop_loss_price, price_precision.price_precision[self.symbol])
                    logger.info(f'old stoploss {self.stoplossUpdateQty}')
                    # self.stoplossUpdatePrice=round(self.stoplossUpdatePrice - float(sell_quantity), price_precision.quantity_precision[self.symbol])

                    self.stoplossUpdateQty = round(
                            self.stoplossUpdateQty, price_precision.quantity_precision[self.symbol])
                    logger.info(f'stoploss updating at {self.stoplossUpdateQty}, sell qty is {sell_quantity}')
                    logger.info(f'api request to create order with symbol {self.symbol} and side sell and type stop market and quantity {self.stoplossUpdateQty} and stopPrice {stop_loss_price} and recvWindow 60000 and reduceOnly True')
                    if current_index != len(exit_prices):
                        for i in range (10):
                            time.sleep(3)
                            try:
                                updated_stop_loss = self.client.futures_create_order(
                                    symbol=self.symbol,
                                    side='BUY',
                                    type='STOP_MARKET',
                                    quantity=self.stoplossUpdateQty,
                                    stopPrice=stop_loss_price,
                                    recvWindow=60000,
                                    reduceOnly=True,
                                )
                                collections.update_one(
                                    {"_id": item_id}, {"$set": {"stop_loss": stop_loss_price}})
                                alert_bot.send_message(
                                    self.user, f'STOP LOSS ORDER UPDATED FOR {self.stoplossUpdateQty} {self.symbol} at {stop_loss_price}.')
                                logger.info(
                                    f'STOP LOSS ORDER UPDATED FOR {self.stoplossUpdateQty} {self.symbol} at {stop_loss_price}.')
                                print(
                                    f'STOP LOSS ORDER UPDATED FOR {self.stoplossUpdateQty} {self.symbol} at {stop_loss_price}.')
                                break
                            except Exception as e:
                                logger.error("UNABLE TO PLACE STOPP LOSS ORDER")
                                logger.error(e)
                                print("UNABLE TO PLACE STOPP LOSS ORDER")
                                print(e)
                    logger.info(f'getting trades from api with symbol {self.symbol} and recvWindow 60000')
                    trades = self.client.futures_account_trades(
                        symbol=self.symbol, recvWindow=60000)
                    pnl = 0
                    for i in range(len(trades)):
                        if trades[i]['orderId'] in self.orderIds:
                            pnlNew = trades[i]
                            pnl = float(pnlNew["realizedPnl"]) + pnl   
                    alert_bot.send_message(
                        self.user, f'CURRENT PNL : {pnl}')
                # elif current_price <= stop_loss_price:
                #     logger.info(f'STOP LOSS ACHIEVED')
                #     # sell all if stop_loss_price is acheived
                #     try:
                #         sell_order = self.client.futures_create_order(
                #             symbol=self.symbol,
                #             side='SELL',
                #             type='MARKET',
                #             quantity=quantity,
                #             recvWindow=60000
                #         )
                #         self.data.remove(self.symbol)
                #         alert_bot.send_message(self.user, f'STOP LOSS ACHIEVED. SELLING {quantity} AT {current_price}.')
                #         sys.exit()
                #     except Exception as e:
                #         logger.error(f'FAILED TO SELL AT STOP LOSS')
                #         logger.error(f'ERROR INDENTIFIED : {e}')
                #         continue
        except Exception as e:
            logger.error('FAILED TO MONITOR PRICE')
            print("FAILED TO MONITOR PRICE")
            logger.error(f'ERROR INDENTIFIED : {e}')
            print(f'ERROR INDENTIFIED : {e}')

    def sell(self):
        try:
            # setting desired margin type and leverage
            # self.set_leverage()
            # self.set_margintype()
            budget = self.configur.getfloat('Binance', 'USDT_BUDGET')
            try:
                current_price = self.price_data.price_data[cryptocurrencies.index(
                    self.symbol)]
            except Exception as e:
                current_price = float(
                    self.um_futures_client.ticker_price(self.symbol)["price"])

            logger.info(f'CURRENT PRICE OF {self.symbol} is {current_price}')
            print(f'CURRENT PRICE OF {self.symbol} is {current_price}')

            quantity = budget/current_price

            if quantity > 1:
                quantity = int(quantity)  # if it is 1.14324 return 1
            else:
                # if it is 0.95435 return 0.954
                quantity = float(
                    round(quantity, price_precision.quantity_precision[self.symbol]))

            logger.info(
                f'ATTEMPTING TO SELL {quantity} {self.symbol} at {current_price}')
            print(
                f'ATTEMPTING TO SELL {quantity} {self.symbol} at {current_price}')
        
            logger.info(f'api request to create order with symbol {self.symbol} and side sell and type market and quantity {quantity} and recvWindow 60000')
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity,
                recvWindow=60000,
            )
            self.orderIds.append(order["orderId"])


            # if CounterTradeTicker:
            #     current_time = time.time()
            #     s_thread = threading.Thread(
            #         target=monitorPriceSell, args=(self.symbol, current_time,))
            #     s_thread.daemon = True
            #     s_thread.start()
            
            time_taken = end_timer
            time_logger.info(f'TIME TAKEN TO PLACE ORDER : {time_taken}')
            print(f'TIME TAKEN TO PLACE ORDER : {time_taken}')

            self.data.add(self.symbol)

            # Check the response
            if order:
                order_details = self.client.futures_get_order(
                    symbol=self.symbol, orderId=order['orderId'], recvWindow=60000)
                entry_price = float(order_details['avgPrice'])

                stop_loss_percentage = self.configur.getfloat(
                    'Binance', 'STOP_PERCENTAGE')
                stop_loss_price = round(entry_price + ((stop_loss_percentage / 100)
                                        * entry_price), price_precision.price_precision[self.symbol])

                time_start = time.time()

                logger.info(
                    f'ATTEMPTING TO PLACE STOP LOSS ORDER where in api,  qty={quantity} symbol={self.symbol} at stoplosprice={stop_loss_price}')
                print(
                    f'ATTEMPTING TO PLACE STOP LOSS ORDER FOR {quantity} {self.symbol} at {stop_loss_price}')
                for y in range(10):
                    try:
                        print(f"Trying to place stop loss order with {quantity} {self.symbol} at {stop_loss_price} ")
                        # logger.info(f"Trying to place stop loss order wit {quantity} {self.symbol} at {stop_loss_price} ")
                        stop_loss_order = self.client.futures_create_order(
                            symbol=self.symbol,
                            side='BUY',
                            type='STOP_MARKET',
                            quantity=quantity,
                            stopPrice=stop_loss_price,
                            recvWindow=60000,
                            reduceOnly=True,
                        )
                        break
                    except Exception as e:
                        logger.error(
                            "UNABLE TO PLACE STOPP LOSS ORDER. RETRYING...")
                        logger.error(e)
                        print("UNABLE TO PLACE STOPP LOSS ORDER. RETRYING...")
                        print(e)
                        time.sleep(3)
                        continue

                time_end = time.time()
                time_logger.info(
                    f'TIME TAKEN TO PLACE STOP LOSS ORDER : {time_end-time_start}')
                print(
                    f'TIME TAKEN TO PLACE STOP LOSS ORDER : {time_end-time_start}')

                logger.info(
                    f'ORDER PLACED : {order["orderId"]} at {entry_price}')
                print(f'ORDER PLACED : {order["orderId"]} at {entry_price}')
                logger.info(
                    f'STOP LOSS ORDER PLACED : {stop_loss_order["orderId"]} at {stop_loss_price}')
                print(
                    f'STOP LOSS ORDER PLACED : {stop_loss_order["orderId"]} at {stop_loss_price}')

                # getting trade data ready
                exit_points = self.configur.getint(
                    'Binance', 'NUMBER_OF_EXIT_POINTS')
                exit_percentages = self.configur.get(
                    'Binance', 'EXIT_PERCENTAGES')

                # Convert a string to a list
                exit_target_quantity_list = exit_percentages.strip(
                    '][').split(',')

                exit_target_percentages_list = []  # store percentages

                for i in range(1, exit_points+1):
                    exit_target_percentages_list.append(
                        self.configur.getfloat('Binance', f'EXIT_{i}_TARGET_PRICE'))

                exit_prices = []    # store target prices
                # convert percentages into prices
                for i in exit_target_percentages_list:
                    exit_prices.append(entry_price - ((i * entry_price) / 100))

        except Exception as e:
            logger.error(f'FAILED TO PLACE AN ORDER')
            logger.error(f'ERROR INDENTIFIED : {e}')
            print("FAILED TO PLACE AN ORDER")
            print(f'ERROR INDENTIFIED : {e}')
            return
        self.stoplossUpdateQty=quantity.__round__(2)

        for i in range(3):
            try:
                alert_bot = telebot.TeleBot(self.bot_token, parse_mode=None)
                alert_bot.send_message(
                    self.user, f'SELL ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {entry_price}.\nSTOP LOSS PRICE : {stop_loss_price}\nEXIT POINTS : {exit_prices}')
                alert_bot.send_message(
                    self.user, f'STOP LOSS ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {stop_loss_price}.')
                break
            except Exception as e:
                time.sleep(10)
                if i == 2:
                    logger.error(f'FAILED TO SEND TELEGRAM MESSAGE')
                    print("FAILED TO SEND TELEGRAM MESSAGE")
                    logger.error(f'ERROR INDENTIFIED : {e}')
                    print(f'ERROR INDENTIFIED : {e}')
                else:
                    logger.error(
                        f'FAILED TO SEND TELEGRAM MESSAGE. RETRYING...')
                    print("FAILED TO SEND TELEGRAM MESSAGE. RETRYING...")
                    logger.error(f'ERROR INDENTIFIED : {e}')
                    print(f'ERROR INDENTIFIED : {e}')

        item = collections.insert_one({
            'symbol': self.symbol[:-4],
            'stoplossUpdateQty': quantity,
            'entry_price': entry_price,
            'quantity': quantity,
            'state': 'SELL',
            'exit_target_quantity_list': exit_target_quantity_list,
            'stop_loss': stop_loss_price,
            'exit_points': exit_prices,
            'index': 0
        })

        # Monitor the price of the token

        s_thread = threading.Thread(
            target=self.sellMonitor, args=(item.inserted_id, alert_bot,))
        s_thread.daemon = True
        s_thread.start()

# # if __name__ == "__main__":
# #     a = Binance()
# #     a.buy()
