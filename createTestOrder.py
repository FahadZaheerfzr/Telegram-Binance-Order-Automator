import time
from binance.client import Client
from configparser import ConfigParser
from binance.um_futures import UMFutures
import telebot # pip install pyTelegramBotAPI
from data import Data, PriceData, PositionData
import dotenv
import sys
from utils import setup_logger, setup_monitor_logger
from symbols import cryptocurrencies
import price_precision
from connection import DB
from timer import end_timer
import threading

# Read a variable called CONFIG from dotenv
# This variable will contain the path to the configuration file
SYMBOLS = dotenv.dotenv_values()['SYMBOLS']

time_logger = setup_logger("time-logger")

logger = setup_logger("binance-order")

monitor_logger = setup_monitor_logger("monitor-logger")

collections = DB["collections"]  # Replace with your collection name



class Binance():

    def __init__(self, symbol, binance_client):

        self.price_data = PriceData()
        self.position_data = PositionData()
        try:
            # reading config file
            self.configur = ConfigParser()
            if symbol.upper() in SYMBOLS:
                print("Special Symbol")
                print(f'{symbol.lower()}_config.ini')
                self.configur.read(f'{symbol.lower()}_config.ini')
            else:
                self.configur.read('default_config.ini')
            self.stop_loss_levels = self.configur.getint('Binance','STOP_LOSS_UPDATE_LEVEL')
            self.bot_token = self.configur.get('Telegram','BOT_TOKEN')
            self.user = self.configur.getint('Telegram','MY_USER')
            self.symbol = symbol+"USDT"
            self.data = Data()
            # Replace 'YOUR_API_KEY' and 'YOUR_API_SECRET' with your actual Binance API credentials
            #self.api_key = self.configur.get('Binance','BINANCE_API_KEY')
            #self.api_secret = self.configur.get('Binance','BINANCE_API_SECRET')
            # Initialize the Binance client
            #self.mode = self.configur.get('Binance','MODE')
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
            sys.exit()
        

    def set_leverage(self):
        time_start = time.time()
        try:
            leverage = int(self.configur.get('Binance','LEVERAGE'))
            # self.symbol = self.configur.get('Binance','SYMBOL')
            print(leverage)
            self.client.futures_change_leverage(symbol=self.symbol,leverage=leverage,recvWindow=60000)
            time_end = time.time()
            time_logger.info(f'TIME TAKEN TO SET LEVERAGE : {time_end-time_start}')
            logger.info(f'LEVERAGE SET TO : {leverage}')
        
        except Exception as e:
            logger.error('FAILED TO SET LEVERAGE')
            logger.error(f'ERROR INDENTIFIED : {e}')
            sys.exit()

    def set_margintype(self):
        time_start = time.time()
        try:
            margin_type = self.configur.get('Binance','MARGIN_TYPE')
            # symbol = self.configur.get('Binance','SYMBOL')
            self.client.futures_change_margin_type(symbol=self.symbol,marginType=margin_type,recvWindow=60000)
            time_end = time.time()
            time_logger.info(f'TIME TAKEN TO SET MARGIN TYPE : {time_end-time_start}')
            logger.info(f'MARGIN TYPE SET TO : {margin_type}')
        
        except Exception as e:
            logger.error('FAILED TO SET MARGIN TYPE')
            logger.error(f'ERROR INDENTIFIED : {e}')

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
            logger.error(f'ERROR INDENTIFIED : {e}')
            sys.exit()

    def buyMonitor(self, item_id, alert_bot):
        logger.info('THREAD STARTED')
        item = collections.find_one({"_id": item_id})
        entry_price = item['entry_price']
        quantity = item['quantity']
        exit_prices = item['exit_points']
        stop_loss_price = item['stop_loss']
        exit_target_quantity_list = item['exit_target_quantity_list']
        current_index = item['index']
        stop_loss_index = 0
        while True:
            time.sleep(0.2)
            current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])
            monitor_logger.info("Made a call to binance")
            positionClosed = self.position_data.position_data[cryptocurrencies.index(self.symbol)] # get position data from position_data.py
            
            # positions = PositionData.position_data
            
            if current_index == len(exit_prices):
                logger.info(f'ALL EXIT POINTS ACHIEVED')
                self.data.remove(self.symbol)
                collections.delete_one({"_id": item_id})
                sys.exit()
            if positionClosed == True:
                logger.info(f'POSITION CLOSED BY STOP LOSS ORDER')
                alert_bot.send_message(self.user, f'POSITION CLOSED BY STOP LOSS ORDER')
                collections.delete_one({"_id": item_id})
                self.data.remove(self.symbol)
                sys.exit()

            
            if current_price >= exit_prices[current_index]:
                sell_price = exit_prices[current_index]
                sell_quantity = (int(exit_target_quantity_list[current_index])/100)*quantity

                if sell_quantity > 1:
                    sell_quantity = int(sell_quantity)
                else:
                    sell_quantity = round(sell_quantity,price_precision.quantity_precision[self.symbol])
                try:
                    if current_index == len(exit_prices)-1:
                        positions = next(obj for obj in self.client.futures_account(recvWindow=60000)['positions'] if obj['symbol'] == self.symbol)
                        if positions['positionAmt'][0] == "-":
                            positions['positionAmt'] = positions['positionAmt'][1:]

                        sell_order = self.client.futures_create_order(
                            symbol=self.symbol,
                            side='SELL',
                            type='MARKET',
                            quantity=float(positions['positionAmt']),
                            recvWindow=60000
                        )
                        print(sell_order)
                        current_index += 1
                        cancel_order = self.client.futures_cancel_all_open_orders(symbol=self.symbol,recvWindow=60000)
                    else:
                        sell_order = self.client.futures_create_order(
                            symbol=self.symbol,
                            side='SELL',
                            type='MARKET',
                            quantity=sell_quantity,
                            recvWindow=60000,
                            reduceOnly=True,
                        )
                        print(sell_order)
                        current_index += 1
                except Exception as e:
                    logger.error(f'FAILED TO SELL AT EXIT POINT {current_index+1}')
                    logger.error(f'ERROR INDENTIFIED : {e}')
                    continue  
                
                cancel_order = self.client.futures_cancel_all_open_orders(symbol=self.symbol,recvWindow=60000)
                
                if current_index % self.stop_loss_levels == 0 and current_index != 0:
                    if stop_loss_index == 0:
                        stop_loss_price = entry_price
                        stop_loss_index += 1
                    else:
                        stop_loss_price = exit_prices[stop_loss_index-1]
                
                stop_loss_price = round(stop_loss_price,price_precision.price_precision[self.symbol])

                logger.info(f'EXIT POINT {current_index+1} ACHIEVED')
                try:
                    updated_stop_loss = self.client.futures_create_order(
                        symbol=self.symbol,
                        side='SELL',
                        type='STOP_MARKET',
                        quantity=sell_quantity,
                        stopPrice=stop_loss_price,
                        recvWindow=60000,
                        reduceOnly=True,
                    )
                    collections.update_one({"_id": item_id}, {"$set": {"stop_loss": stop_loss_price}})
                    alert_bot.send_message(self.user, f'STOP LOSS ORDER UPDATED FOR {sell_quantity} {self.symbol} at {stop_loss_price}.')
                    logger.info(f'STOP LOSS ORDER UPDATED FOR {sell_quantity} {self.symbol} at {stop_loss_price}.')
                except Exception as e:
                    logger.error("UNABLE TO PLACE STOPP LOSS ORDER")
                    logger.error(e)
                
                
                collections.update_one({"_id": item_id}, {"$set": {"index": current_index}})

                if sell_order and current_index != len(exit_prices):
                    logger.info(f'EXIT POINT {current_index} ACHIEVED')
                    logger.info(f'SOLD at {current_price}')
                    
                    
                alert_bot.send_message(self.user, f'EXIT POINT {current_index} ACHIEVED. SELLING {sell_quantity} {self.symbol} AT {current_price}')

    def buy(self):
        try:
            # setting desired margin type and leverage 
            #self.set_leverage()
            #self.set_margintype()            
            budget = self.configur.getfloat('Binance','USDT_BUDGET')
            try:
                current_price = self.price_data.price_data[cryptocurrencies.index(self.symbol)]          
            except Exception as e:
                current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])

            logger.info(f'CURRENT PRICE OF {self.symbol} is {current_price}')

            quantity = budget/current_price
            
            if quantity > 1:
                quantity = int(quantity) # if it is 1.14324 return 1
            else:
                quantity = float(round(quantity,price_precision.quantity_precision[self.symbol])) # if it is 0.95435 return 0.954

            

            logger.info(f'ATTEMPTING TO BUY {quantity} {self.symbol} at {current_price}')
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity,
                recvWindow=60000,     
            )
            logger.info(f'ORDER PLACED : {order["orderId"]} at {current_price}')
            time_taken = end_timer()
            
            time_logger.info(f'TIME TAKEN TO PLACE ORDER : {time_taken}')
            self.data.add(self.symbol)

            # Check the response
            if order:
                order_details = self.client.futures_get_order(symbol=self.symbol,orderId=order['orderId'],recvWindow=60000)
                entry_price = float(order_details['avgPrice'])
                stop_loss_percentage = self.configur.getfloat('Binance','STOP_PERCENTAGE')
                stop_loss_price = round(entry_price - ((stop_loss_percentage / 100) * entry_price),price_precision.price_precision[self.symbol])
                logger.info(f'ATTEMPTING TO PLACE STOP LOSS ORDER FOR {quantity} {self.symbol} at {stop_loss_price}')
                time_start = time.time()
                stop_loss_order = self.client.futures_create_order(
                    symbol=self.symbol,
                    side='SELL',
                    type='STOP_MARKET',
                    quantity=quantity,
                    stopPrice=stop_loss_price,
                    recvWindow=60000,
                    reduceOnly=True,
                )
                time_end = time.time()
                time_logger.info(f'TIME TAKEN TO PLACE STOP LOSS ORDER : {time_end-time_start}')

                logger.info(f'ORDER PLACED : {order["orderId"]} at {entry_price}')     
                logger.info(f'STOP LOSS ORDER PLACED : {stop_loss_order["orderId"]} at {stop_loss_price}')

                # getting trade data ready
                exit_points = self.configur.getint('Binance','NUMBER_OF_EXIT_POINTS')
                exit_percentages = self.configur.get('Binance','EXIT_PERCENTAGES')

                
                # Convert a string to a list
                exit_target_quantity_list = exit_percentages.strip('][').split(',')                   


                exit_target_percentages_list = [] # store percentages

                for i in range(1, exit_points+1):                   
                    exit_target_percentages_list.append(self.configur.getfloat('Binance',f'EXIT_{i}_TARGET_PRICE'))

                exit_prices = []    # store target prices
                # convert percentages into prices
                for i in exit_target_percentages_list:
                    exit_prices.append(((i * entry_price) / 100) + entry_price) 

        except Exception as e:
                logger.error(f'FAILED TO PLACE AN ORDER')            
                logger.error(f'ERROR INDENTIFIED : {e}')
                sys.exit()


        alert_bot = telebot.TeleBot(self.bot_token, parse_mode=None)
        alert_bot.send_message(self.user, f'BUY ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {entry_price}.\nSTOP LOSS PRICE : {stop_loss_price}\nEXIT POINTS : {exit_prices}')
        alert_bot.send_message(self.user, f'STOP LOSS ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {stop_loss_price}.')
        
        # Insert the document into the collection
        item = collections.insert_one({
            'symbol': self.symbol[:-4],
            'entry_price': entry_price,
            'quantity': quantity,
            'state': 'BUY',
            'exit_target_quantity_list': exit_target_quantity_list,
            'stop_loss': stop_loss_price,
            'exit_points': exit_prices,
            'index': 0
        })
        
        # Monitor the price of the token     

        s_thread = threading.Thread(target=self.buyMonitor, args=(item.inserted_id, alert_bot,))
        s_thread.daemon = True
        s_thread.start()   


    # Monitor the price of the token        
    def sellMonitor(self, item_id, alert_bot):
        item = collections.find_one({"_id": item_id})
        entry_price = item['entry_price']
        quantity = item['quantity']
        exit_prices = item['exit_points']
        stop_loss_price = item['stop_loss']
        exit_target_quantity_list = item['exit_target_quantity_list']
        current_index = item['index']
        stop_loss_index = 0
        while True:
            time.sleep(0.2)

            positionClosed = self.position_data.position_data[cryptocurrencies.index(self.symbol)] # get position data from position_data.py            
            
            if current_index == len(exit_prices):
                logger.info(f'ALL EXIT POINTS ACHIEVED')
                self.data.remove(self.symbol)
                collections.delete_one({"_id": item_id})
                sys.exit()

            if positionClosed == True:
                logger.info(f'POSITION CLOSED BY STOP LOSS ORDER')
                alert_bot.send_message(self.user, f'POSITION CLOSED BY STOP LOSS ORDER')
                self.data.remove(self.symbol)
                collections.delete_one({"_id": item_id})
                sys.exit()

            current_price = self.price_data.price_data[cryptocurrencies.index(self.symbol)]          
            monitor_logger.info("Made a call to binance")
            
            
            if current_price <= exit_prices[current_index]:
                sell_quantity = (int(exit_target_quantity_list[current_index])/100)*quantity

                if sell_quantity > 1:
                    sell_quantity = int(sell_quantity)
                else:
                    sell_quantity = round(sell_quantity,price_precision.quantity_precision[self.symbol])
                try:
                    if current_index == len(exit_prices)-1:
                        positions = next(obj for obj in self.client.futures_account(recvWindow=60000,)['positions'] if obj['symbol'] == self.symbol)
                        if positions['positionAmt'][0] == "-":
                            sell_quantity = positions['positionAmt'][1:]

                        sell_order = self.client.futures_create_order(
                            symbol=self.symbol,
                            side='BUY',
                            type='MARKET',
                            quantity=float(sell_quantity),
                            recvWindow=60000,
                            reduceOnly=True,
                        )

                        cancel_order = self.client.futures_cancel_all_open_orders(symbol=self.symbol,recvWindow=60000)
                        print(sell_order)
                    else:
                        sell_order = self.client.futures_create_order(
                            symbol=self.symbol,
                            side='BUY',
                            type='MARKET',
                            quantity=sell_quantity,
                            recvWindow=60000
                        )
                        print(sell_order)
                        current_index += 1
                except Exception as e:
                    logger.error(f'FAILED TO SELL AT EXIT POINT {current_index+1}')
                    logger.error(f'ERROR INDENTIFIED : {e}')
                    continue
            
                        

                cancel_order = self.client.futures_cancel_all_open_orders(symbol=self.symbol,recvWindow=60000)               
                if current_index % self.stop_loss_levels == 0 and current_index != 0:
                    if stop_loss_index == 0:
                        stop_loss_price = entry_price
                        stop_loss_index += 1
                    else:
                        stop_loss_price = exit_prices[stop_loss_index-1]
                
                try:
                    updated_stop_loss = self.client.futures_create_order(
                        symbol=self.symbol,
                        side='BUY',
                        type='STOP_MARKET',
                        quantity=sell_quantity,
                        stopPrice=stop_loss_price,
                        recvWindow=60000,
                        reduceOnly=True,
                    )
                    collections.update_one({"_id": item_id}, {"$set": {"stop_loss": stop_loss_price}})
                    alert_bot.send_message(self.user, f'STOP LOSS ORDER UPDATED FOR {sell_quantity} {self.symbol} at {stop_loss_price}.')
                    logger.info(f'STOP LOSS ORDER UPDATED FOR {sell_quantity} {self.symbol} at {stop_loss_price}.')
                except Exception as e:
                    logger.error("UNABLE TO PLACE STOPP LOSS ORDER")
                    logger.error(e)
                
                
                collections.update_one({"_id": item_id}, {"$set": {"index": current_index}})

                if sell_order:
                    logger.info(f'EXIT POINT {current_index} ACHIEVED')
                    logger.info(f'SOLD at {current_price}')
                
                alert_bot.send_message(self.user, f'EXIT POINT {current_index} ACHIEVED. BUYING {sell_quantity} {self.symbol} AT {current_price}.')
                logger.info(f'EXIT POINT {current_index} ACHIEVED')
            
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



    def sell(self):
        try:
            # setting desired margin type and leverage 
            #self.set_leverage()
            #self.set_margintype()            
            budget = self.configur.getfloat('Binance','USDT_BUDGET')
            try:
                current_price = self.price_data.price_data[cryptocurrencies.index(self.symbol)]          
            except Exception as e:
                current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])

            logger.info(f'CURRENT PRICE OF {self.symbol} is {current_price}')

            quantity = budget/current_price
            
            if quantity > 1:
                quantity = int(quantity) # if it is 1.14324 return 1
            else:
                quantity = float(round(quantity,price_precision.quantity_precision[self.symbol])) # if it is 0.95435 return 0.954

            
            logger.info(f'ATTEMPTING TO SELL {quantity} {self.symbol} at {current_price}')
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity,
                recvWindow=60000,     
            )
            time_taken = end_timer()
            time_logger.info(f'TIME TAKEN TO PLACE ORDER : {time_taken}')
            
            self.data.add(self.symbol)

            # Check the response
            if order:
                order_details = self.client.futures_get_order(symbol=self.symbol,orderId=order['orderId'],recvWindow=60000)
                entry_price = float(order_details['avgPrice'])
                
                stop_loss_percentage = self.configur.getfloat('Binance','STOP_PERCENTAGE')
                stop_loss_price = round(entry_price + ((stop_loss_percentage / 100) * entry_price),price_precision.price_precision[self.symbol])


                time_start = time.time()
            
                logger.info(f'ATTEMPTING TO PLACE STOP LOSS ORDER FOR {quantity} {self.symbol} at {stop_loss_price}')
                stop_loss_order = self.client.futures_create_order(
                    symbol=self.symbol,
                    side='BUY',
                    type='STOP_MARKET',
                    quantity=quantity,
                    stopPrice=stop_loss_price,
                    recvWindow=60000,
                    reduceOnly=True,
                )
                time_end = time.time()
                time_logger.info(f'TIME TAKEN TO PLACE STOP LOSS ORDER : {time_end-time_start}')
                
                logger.info(f'ORDER PLACED : {order["orderId"]} at {entry_price}')     
                logger.info(f'STOP LOSS ORDER PLACED : {stop_loss_order["orderId"]} at {stop_loss_price}')

                # getting trade data ready
                exit_points = self.configur.getint('Binance','NUMBER_OF_EXIT_POINTS')
                exit_percentages = self.configur.get('Binance','EXIT_PERCENTAGES')

                
                # Convert a string to a list
                exit_target_quantity_list = exit_percentages.strip('][').split(',')                   


                exit_target_percentages_list = [] # store percentages

                for i in range(1, exit_points+1):                   
                    exit_target_percentages_list.append(self.configur.getfloat('Binance',f'EXIT_{i}_TARGET_PRICE'))

                exit_prices = []    # store target prices
                # convert percentages into prices
                for i in exit_target_percentages_list:
                    exit_prices.append(entry_price - ((i * entry_price) / 100)  ) 

        except Exception as e:
                logger.error(f'FAILED TO PLACE AN ORDER')            
                logger.error(f'ERROR INDENTIFIED : {e}')
                sys.exit()


        alert_bot = telebot.TeleBot(self.bot_token, parse_mode=None)
        alert_bot.send_message(self.user, f'SELL ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {entry_price}.\nSTOP LOSS PRICE : {stop_loss_price}\nEXIT POINTS : {exit_prices}')
        alert_bot.send_message(self.user, f'STOP LOSS ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {stop_loss_price}.')

        item = collections.insert_one({
            'symbol': self.symbol[:-4],
            'entry_price': entry_price,
            'quantity': quantity,
            'state': 'SELL',
            'exit_target_quantity_list': exit_target_quantity_list,
            'stop_loss': stop_loss_price,
            'exit_points': exit_prices,
            'index': 0
        })
        
        # Monitor the price of the token        
        self.sellMonitor(item.inserted_id, alert_bot)
        

# # if __name__ == "__main__":
# #     a = Binance()
# #     a.buy()

