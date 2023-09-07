import json
import time
from binance.client import Client
from configparser import ConfigParser
from binance.um_futures import UMFutures
from telethon import TelegramClient
import telebot # pip install pyTelegramBotAPI

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logging.basicConfig(level=logging.ERROR, format='%(levelname)s - %(message)s')

import sys

class Binance():

    def __init__(self, symbol):

        self.logger = logging.getLogger(__name__)
        
        try:
            # reading config file
            self.configur = ConfigParser()
            self.configur.read('config.ini')
            self.bot_token = self.configur.get('Telegram','BOT_TOKEN')
            self.user = self.configur.getint('Telegram','MY_USER')
            self.symbol = symbol
            # Replace 'YOUR_API_KEY' and 'YOUR_API_SECRET' with your actual Binance API credentials
            self.api_key = self.configur.get('Binance','BINANCE_API_KEY')
            self.api_secret = self.configur.get('Binance','BINANCE_API_SECRET')
            # Initialize the Binance client
            self.client = Client(self.api_key, self.api_secret, testnet=True)
           
            # for accessing public api
            self.um_futures_client = UMFutures()

            self.logger.info('CONNECTED TO BINANCE, INITIATING TRADE')

        except Exception as e:
            self.logger.error('FAILED TO INITIATE TRADE')
            self.logger.error(f'ERROR INDENTIFIED : {e}')
            sys.exit()
        

    def set_leverage(self):
        
        try:
            leverage = int(self.configur.get('Binance','LEVERAGE'))
            # self.symbol = self.configur.get('Binance','SYMBOL')

            self.client.futures_change_leverage(symbol=self.symbol,leverage=leverage,recvWindow=60000)

            self.logger.info(f'LEVERAGE SET TO : {leverage}')
        
        except Exception as e:
            self.logger.error('FAILED TO SET LEVERAGE')
            self.logger.error(f'ERROR INDENTIFIED : {e}')
            sys.exit()

    def set_margintype(self):
        
        try:
            margin_type = self.configur.get('Binance','MARGIN_TYPE')
            # symbol = self.configur.get('Binance','SYMBOL')
            self.client.futures_change_margin_type(symbol=self.symbol,marginType=margin_type)

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
            print(self.client.futures_time())
            self.set_leverage()
            self.set_margintype()            

            budget = self.configur.getint('Binance','USDT_BUDGET')

            current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])                                                 
            self.logger.info(f'CURRENT PRICE OF {self.symbol} is {current_price}')

            quantity = budget/current_price
            print(quantity.__round__(2))
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity.__round__(2),
                recvWindow=60000
            )

            # Check the response
            if order:
                self.logger.info(f'ORDER PLACED : {order["orderId"]}')            

                order_details = self.client.futures_get_order(symbol=self.symbol,orderId=order['orderId'],recvWindow=60000)
                entry_price = float(order_details['avgPrice'])

                stop_loss_percentage = self.configur.getint('Binance','STOP_PERCENTAGE')
                print((stop_loss_percentage / 100) * entry_price)
                stop_loss_price = entry_price - ((stop_loss_percentage / 100) * entry_price)

                # getting trade data ready
                exit_points = self.configur.getint('Binance','NUMBER_OF_EXIT_POINTS')
                exit_percentages = self.configur.get('Binance','EXIT_PERCENTAGES')

                
                # Convert a string to a list
                exit_target_quantity_list = exit_percentages.strip('][').split(',')                   
                print(exit_target_quantity_list)


                exit_target_percentages_list = [] # store percentages

                for i in range(1, exit_points+1):                   
                    exit_target_percentages_list.append(self.configur.getint('Binance',f'EXIT_{i}_TARGET_PRICE'))

                exit_prices = []    # store target prices
                # convert percentages into prices
                for i in exit_target_percentages_list:
                    exit_prices.append(((i * entry_price) / 100) + entry_price) 

        except Exception as e:
                self.logger.error(f'FAILED TO PLACE AN ORDER')            
                self.logger.error(f'ERROR INDENTIFIED : {e}')
                sys.exit()
        print(entry_price)
        print(stop_loss_price)
        print(exit_prices)

        alert_bot = telebot.TeleBot(self.bot_token, parse_mode=None)
        alert_bot.send_message(self.user, f'BUY ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {entry_price}.\nSTOP LOSS PRICE : {stop_loss_price}\nEXIT POINTS : {exit_prices}')


        current_index = 0   # index for iterating through loop
        
        # Monitor the price of the token        
        while True:
            current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])
            print(current_price)
            print(current_index)
            
            if current_index == len(exit_prices):
                self.logger.info(f'ALL EXIT POINTS ACHIEVED')
                sys.exit()
            if current_price >= exit_prices[current_index]:
                sell_price = exit_prices[current_index]
                try:
                    sell_order = self.client.futures_create_order(
                        symbol=self.symbol,
                        side='SELL',
                        type='MARKET',
                        quantity=(int(exit_target_quantity_list[current_index])/100)*quantity.__round__(2),
                        recvWindow=60000
                    )
                    alert_bot.send_message(self.user, f'EXIT POINT {current_index+1} ACHIEVED. SELLING {exit_target_quantity_list[current_index]} AT {sell_price}.')
                    self.logger.info(f'EXIT POINT {current_index+1} ACHIEVED')
                    current_index += 1
                except Exception as e:
                    self.logger.error(f'FAILED TO SELL AT EXIT POINT {current_index+1}')
                    self.logger.error(f'ERROR INDENTIFIED : {e}')
                    continue

                if sell_order:
                    self.logger.info(f'EXIT POINT {current_index+1} ACHIEVED')
                    self.logger.info(f'SOLD at {current_price}')
                    
                    if current_index > 1:
                        stop_loss_price = exit_prices[current_index-2]
                    else:
                        stop_loss_price = entry_price

            elif current_price <= stop_loss_price:
                self.logger.info(f'STOP LOSS ACHIEVED')
                # sell all if stop_loss_price is acheived
                try:
                    sell_order = self.client.futures_create_order(
                        symbol=self.symbol,
                        side='SELL',
                        type='MARKET',
                        quantity=quantity.__round__(2),
                        recvWindow=60000
                    )
                    alert_bot.send_message(self.user, f'STOP LOSS ACHIEVED. SELLING {quantity.__round__(2)} AT {current_price}.')
                    sys.exit()
                except Exception as e:
                    self.logger.error(f'FAILED TO SELL AT STOP LOSS')
                    self.logger.error(f'ERROR INDENTIFIED : {e}')
                    continue
    
    def sell(self):
        print('SELLING')
        try:
            # setting desired margin type and leverage 
            self.set_leverage()
            self.set_margintype()            

            budget = self.configur.getint('Binance','USDT_BUDGET')

            current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])                                                 
            self.logger.info(f'CURRENT PRICE OF {self.symbol} is {current_price}')

            quantity = budget/current_price
            print(quantity.__round__(2))
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity.__round__(2),
                recvWindow=60000
            )



            # Check the response
            if order:
                self.logger.info(f'ORDER PLACED : {order["orderId"]}')            

                order_details = self.client.futures_get_order(symbol=self.symbol,orderId=order['orderId'])
                entry_price = float(order_details['avgPrice'])

                stop_loss_percentage = self.configur.getint('Binance','STOP_PERCENTAGE')
                print((stop_loss_percentage / 100) * entry_price)
                stop_loss_price = entry_price + ((stop_loss_percentage / 100) * entry_price)

                # getting trade data ready
                exit_points = self.configur.getint('Binance','NUMBER_OF_EXIT_POINTS')
                exit_percentages = self.configur.get('Binance','EXIT_PERCENTAGES')

                
                # Convert a string to a list
                exit_target_quantity_list = exit_percentages.strip('][').split(',')                   
                print(exit_target_quantity_list)


                exit_target_percentages_list = [] # store percentages

                for i in range(1, exit_points+1):                   
                    exit_target_percentages_list.append(self.configur.getint('Binance',f'EXIT_{i}_TARGET_PRICE'))

                exit_prices = []    # store target prices
                # convert percentages into prices
                for i in exit_target_percentages_list:
                    exit_prices.append(entry_price - ((i * entry_price) / 100) ) 

        except Exception as e:
                self.logger.error(f'FAILED TO PLACE AN ORDER')            
                self.logger.error(f'ERROR INDENTIFIED : {e}')
                sys.exit()
        print(entry_price)
        print(stop_loss_price)
        print(exit_prices)

        alert_bot = telebot.TeleBot(self.bot_token, parse_mode=None)
        alert_bot.send_message(self.user, f'SELL ORDER PLACED FOR {quantity.__round__(2)} {self.symbol} at {entry_price}.\nSTOP LOSS PRICE : {stop_loss_price}\nEXIT POINTS : {exit_prices}')

        current_index = 0   # index for iterating through loop
        
        # Monitor the price of the token        
        while True:
            current_price = float(self.um_futures_client.ticker_price(self.symbol)["price"])
            print(current_price)
            if current_index == len(exit_prices):
                self.logger.info(f'ALL EXIT POINTS ACHIEVED')
                sys.exit()
            if current_price >= exit_prices[current_index]:
                sell_price = exit_prices[current_index]
                try:
                    sell_order = self.client.futures_create_order(
                        symbol=self.symbol,
                        side='BUY',
                        type='MARKET',
                        quantity=(int(exit_target_quantity_list[current_index])/100)*quantity.__round__(2),
                        recvWindow=60000
                    )
                    alert_bot.send_message(self.user, f'EXIT POINT {current_index+1} ACHIEVED. BUYING {exit_target_quantity_list[current_index]} AT {sell_price}.')
                    self.logger.info(f'EXIT POINT {current_index+1} ACHIEVED')
                    current_index += 1
                except Exception as e:
                    self.logger.error(f'FAILED TO SELL AT EXIT POINT {current_index+1}')
                    self.logger.error(f'ERROR INDENTIFIED : {e}')
                    continue

                if sell_order:
                    self.logger.info(f'EXIT POINT {current_index+1} ACHIEVED')
                    self.logger.info(f'BOUGHT at {current_price}')
                    if current_index > 1:
                        stop_loss_price = exit_prices[current_index-2]
                    else:
                        stop_loss_price = entry_price

            elif current_price <= stop_loss_price:
                self.logger.info(f'STOP LOSS ACHIEVED')
                # sell all if stop_loss_price is acheived
                try:
                    sell_order = self.client.futures_create_order(
                        symbol=self.symbol,
                        side='BUY',
                        type='MARKET',
                        quantity=quantity.__round__(2),
                        recvWindow=60000
                    )

                    alert_bot.send_message(self.user, f'STOP LOSS ACHIEVED. BUYING {quantity.__round__(2)} AT {current_price}.')
                    sys.exit()
                except Exception as e:
                    self.logger.error(f'FAILED TO SELL AT STOP LOSS')
                    self.logger.error(f'ERROR INDENTIFIED : {e}')
                    continue


# # if __name__ == "__main__":
# #     a = Binance()
# #     a.buy()