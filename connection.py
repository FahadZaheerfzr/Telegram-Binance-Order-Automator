from pymongo import MongoClient

client = MongoClient("mongodb+srv://wally24_7:zNWf4C3HVfptIybQ@cluster0.vwc9dpy.mongodb.net/?retryWrites=true&w=majority")
DB = client["binance"]