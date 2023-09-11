import time
from binance.client import Client
from configparser import ConfigParser
from binance.um_futures import UMFutures
import telebot # pip install pyTelegramBotAPI
from data import Data, PriceData
import dotenv
import sys
from utils import setup_logger
from symbols import cryptocurrencies
import price_precision
# Read a variable called CONFIG from dotenv
# This variable will contain the path to the configuration file
SYMBOLS = dotenv.dotenv_values()['SYMBOLS']

time_logger = setup_logger("time-logger")


class Binance():

    def __init__(self, symbol, binance_client):

        self.logger = setup_logger("binance-order")
        self.price_data = PriceData()
        try:
            # reading config file
            self.configur = ConfigParser()
            if symbol.upper() in SYMBOLS:
                print("Special Symbol")
                print(f'{symbol.lower()}_config.ini')
                self.configur.read(f'{symbol.lower()}_config.ini')
            else:
                self.configur.read('default_config.ini')
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

            self.logger.info('CONNECTED TO BINANCE, INITIATING TRADE')

        except Exception as e:
            self.logger.error('FAILED TO INITIATE TRADE')
            self.logger.error(f'ERROR INDENTIFIED : {e}')
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
            self.logger.info(f'LEVERAGE SET TO : {leverage}')
        
        except Exception as e:
            self.logger.error('FAILED TO SET LEVERAGE')
            self.logger.error(f'ERROR INDENTIFIED : {e}')
            sys.exit()

    def set_margintype(self):
        time_start = time.time()
        try:
            margin_type = self.configur.get('Binance','MARGIN_TYPE')
            # symbol = self.configur.get('Binance','SYMBOL')
            self.client.futures_change_margin_type(symbol=self.symbol,marginType=margin_type,recvWindow=60000)
            time_end = time.time()
            time_logger.info(f'TIME TAKEN TO SET MARGIN TYPE : {time_end-time_start}')
            self.logger.info(f'MARGIN TYPE SET TO : {margin_type}')
        
        except Exception as e:
            self.logger.error('FAILED TO SET MARGIN TYPE')
            self.logger.error(f'ERROR INDENTIFIED : {e}')

    # def get_quantity(self):
        
    #     try:
    #         pass
    #     except Exception as e:
    #         pass
    

    async def buy(self):
        
        try:
            # setting desired margin type and leverage 
            #self.set_leverage()
            #self.set_margintype()            
            time_start = time.time()
            budget = self.configur.getfloat('Binance','USDT_BUDGET')
            try:
                current_price = self.price_data.price_data[cryptocurrencies.index(self.symbol)]          
            except Exception as e:
                current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])

            self.logger.info(f'CURRENT PRICE OF {self.symbol} is {current_price}')

            quantity = budget/current_price
            
            if quantity > 1:
                quantity = int(quantity) # if it is 1.14324 return 1
            else:
                quantity = float(round(quantity,price_precision.quantity_precision[self.symbol])) # if it is 0.95435 return 0.954

            stop_loss_percentage = self.configur.getfloat('Binance','STOP_PERCENTAGE')
            stop_loss_price = round(current_price - ((stop_loss_percentage / 100) * current_price),price_precision.price_precision[self.symbol])

            self.logger.info(f'ATTEMPTING TO BUY {quantity} {self.symbol} at {current_price}')
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity,
                recvWindow=60000,     
            )
            time_end = time.time()
            time_logger.info(f'TIME TAKEN TO PLACE ORDER : {time_end-time_start}')

            self.logger.info(f'ATTEMPTING TO PLACE STOP LOSS ORDER FOR {quantity} {self.symbol} at {stop_loss_price}')
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
            
            self.data.add(self.symbol)

            # Check the response
            if order:
                order_details = self.client.futures_get_order(symbol=self.symbol,orderId=order['orderId'],recvWindow=60000)
                entry_price = float(order_details['avgPrice'])

                self.logger.info(f'ORDER PLACED : {order["orderId"]} at {entry_price}')     
                self.logger.info(f'STOP LOSS ORDER PLACED : {stop_loss_order["orderId"]} at {stop_loss_price}')

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
                self.logger.error(f'FAILED TO PLACE AN ORDER')            
                self.logger.error(f'ERROR INDENTIFIED : {e}')
                sys.exit()


        alert_bot = telebot.TeleBot(self.bot_token, parse_mode=None)
        alert_bot.send_message(self.user, f'BUY ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {entry_price}.\nSTOP LOSS PRICE : {stop_loss_price}\nEXIT POINTS : {exit_prices}')
        alert_bot.send_message(self.user, f'STOP LOSS ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {stop_loss_price}.')

        current_index = 0   # index for iterating through loop
        
        # Monitor the price of the token        
        while True:
            positions = next(obj for obj in self.client.futures_account(recvWindow=60000)['positions'] if obj['symbol'] == self.symbol)
            
            if current_index == len(exit_prices):
                self.logger.info(f'ALL EXIT POINTS ACHIEVED')
                self.data.remove(self.symbol)
                sys.exit()
            if float(positions['positionAmt']) == 0.0:
                self.logger.info(f'POSITION CLOSED BY STOP LOSS ORDER')
                alert_bot.send_message(self.user, f'POSITION CLOSED BY STOP LOSS ORDER')
                self.data.remove(self.symbol)
                sys.exit()

            current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])

            
            if current_price >= exit_prices[current_index]:
                sell_price = exit_prices[current_index]
                sell_quantity = (int(exit_target_quantity_list[current_index])/100)*quantity

                if sell_quantity > 1:
                    sell_quantity = int(sell_quantity)
                else:
                    sell_quantity = round(sell_quantity,price_precision.quantity_precision[self.symbol])
                try:
                    if current_index == len(exit_prices)-1:
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
                except Exception as e:
                    self.logger.error(f'FAILED TO SELL AT EXIT POINT {current_index+1}')
                    self.logger.error(f'ERROR INDENTIFIED : {e}')
                    continue  
                
                cancel_order = self.client.futures_cancel_all_open_orders(symbol=self.symbol,recvWindow=60000)
                if current_index > 1:
                    stop_loss_price = exit_prices[current_index-1]
                else:
                    stop_loss_price = entry_price
                
                stop_loss_price = round(stop_loss_price,price_precision.price_precision[self.symbol])

                self.logger.info(f'EXIT POINT {current_index+1} ACHIEVED')
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
                    alert_bot.send_message(self.user, f'STOP LOSS ORDER UPDATED FOR {sell_quantity} {self.symbol} at {stop_loss_price}.')
                    self.logger.info(f'STOP LOSS ORDER UPDATED FOR {sell_quantity} {self.symbol} at {stop_loss_price}.')
                except Exception as e:
                    self.logger.error("UNABLE TO PLACE STOPP LOSS ORDER")
                    self.logger.error(e)
                
                current_index += 1

                if sell_order and current_index != len(exit_prices):
                    self.logger.info(f'EXIT POINT {current_index} ACHIEVED')
                    self.logger.info(f'SOLD at {current_price}')
                    
                    
                alert_bot.send_message(self.user, f'EXIT POINT {current_index} ACHIEVED. SELLING {sell_quantity} {self.symbol} AT {current_price}')

            # elif current_price <= stop_loss_price:
            #     self.logger.info(f'STOP LOSS ACHIEVED')
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
            #         self.logger.error(f'FAILED TO SELL AT STOP LOSS')
            #         self.logger.error(f'ERROR INDENTIFIED : {e}')
            #         continue
    
    def sell(self):
        
        try:
            time_start = time.time()
            # setting desired margin type and leverage 
            #self.set_leverage()
            #self.set_margintype()            
            budget = self.configur.getfloat('Binance','USDT_BUDGET')
            try:
                current_price = self.price_data.price_data[cryptocurrencies.index(self.symbol)]          
            except Exception as e:
                current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])

            self.logger.info(f'CURRENT PRICE OF {self.symbol} is {current_price}')

            quantity = budget/current_price
            
            if quantity > 1:
                quantity = int(quantity) # if it is 1.14324 return 1
            else:
                quantity = float(round(quantity,price_precision.quantity_precision[self.symbol])) # if it is 0.95435 return 0.954

            stop_loss_percentage = self.configur.getfloat('Binance','STOP_PERCENTAGE')
            stop_loss_price = round(current_price + ((stop_loss_percentage / 100) * current_price),price_precision.price_precision[self.symbol])

            self.logger.info(f'ATTEMPTING TO SELL {quantity} {self.symbol} at {current_price}')
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity,
                recvWindow=60000,     
            )
            time_end = time.time()
            time_logger.info(f'TIME TAKEN TO PLACE ORDER : {time_end-time_start}')

            time_start = time.time()
            
            self.logger.info(f'ATTEMPTING TO PLACE STOP LOSS ORDER FOR {quantity} {self.symbol} at {stop_loss_price}')
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
            
            self.data.add(self.symbol)

            # Check the response
            if order:
                order_details = self.client.futures_get_order(symbol=self.symbol,orderId=order['orderId'],recvWindow=60000)
                entry_price = float(order_details['avgPrice'])

                self.logger.info(f'ORDER PLACED : {order["orderId"]} at {entry_price}')     
                self.logger.info(f'STOP LOSS ORDER PLACED : {stop_loss_order["orderId"]} at {stop_loss_price}')

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
                self.logger.error(f'FAILED TO PLACE AN ORDER')            
                self.logger.error(f'ERROR INDENTIFIED : {e}')
                sys.exit()


        alert_bot = telebot.TeleBot(self.bot_token, parse_mode=None)
        alert_bot.send_message(self.user, f'SELL ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {entry_price}.\nSTOP LOSS PRICE : {stop_loss_price}\nEXIT POINTS : {exit_prices}')
        alert_bot.send_message(self.user, f'STOP LOSS ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {stop_loss_price}.')

        current_index = 0   # index for iterating through loop
        
        # Monitor the price of the token        
        while True:
            positions = next(obj for obj in self.client.futures_account(recvWindow=60000,)['positions'] if obj['symbol'] == self.symbol)
            
            if current_index == len(exit_prices):
                self.logger.info(f'ALL EXIT POINTS ACHIEVED')
                self.data.remove(self.symbol)
                sys.exit()

            if float(positions['positionAmt']) == 0.0:
                self.logger.info(f'POSITION CLOSED BY STOP LOSS ORDER')
                alert_bot.send_message(self.user, f'POSITION CLOSED BY STOP LOSS ORDER')
                self.data.remove(self.symbol)
                sys.exit()

            current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])


            
            if current_price <= exit_prices[current_index]:
                sell_quantity = (int(exit_target_quantity_list[current_index])/100)*quantity

                if sell_quantity > 1:
                    sell_quantity = int(sell_quantity)
                else:
                    sell_quantity = round(sell_quantity,price_precision.quantity_precision[self.symbol])
                try:
                    if current_index == len(exit_prices)-1:
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
                except Exception as e:
                    self.logger.error(f'FAILED TO SELL AT EXIT POINT {current_index+1}')
                    self.logger.error(f'ERROR INDENTIFIED : {e}')
                    continue
            
                        

                cancel_order = self.client.futures_cancel_all_open_orders(symbol=self.symbol,recvWindow=60000)
                if current_index > 1:
                    stop_loss_price = exit_prices[current_index-1]
                else:
                    stop_loss_price = entry_price
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
                    alert_bot.send_message(self.user, f'STOP LOSS ORDER UPDATED FOR {sell_quantity} {self.symbol} at {stop_loss_price}.')
                    self.logger.info(f'STOP LOSS ORDER UPDATED FOR {sell_quantity} {self.symbol} at {stop_loss_price}.')
                except Exception as e:
                    self.logger.error("UNABLE TO PLACE STOPP LOSS ORDER")
                    self.logger.error(e)
                
                current_index += 1
                

                if sell_order:
                    self.logger.info(f'EXIT POINT {current_index} ACHIEVED')
                    self.logger.info(f'SOLD at {current_price}')
                
                alert_bot.send_message(self.user, f'EXIT POINT {current_index} ACHIEVED. BUYING {sell_quantity} {self.symbol} AT {current_price}.')
                self.logger.info(f'EXIT POINT {current_index} ACHIEVED')
            
            # elif current_price <= stop_loss_price:
            #     self.logger.info(f'STOP LOSS ACHIEVED')
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
            #         self.logger.error(f'FAILED TO SELL AT STOP LOSS')
            #         self.logger.error(f'ERROR INDENTIFIED : {e}')
            #         continue


# # if __name__ == "__main__":
# #     a = Binance()
# #     a.buy()