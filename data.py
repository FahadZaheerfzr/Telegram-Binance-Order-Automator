# Define a class that contains a static array that is global to the program
import time
class Data:
    # Static array that is global to the program
    data = []
    last_processed_time = {}


    # Constructor
    def __init__(self):
        pass

    # Add a value to the array
    def add(self, value):
        self.data.append(value)

    # Get the array
    def get(self):
        return self.data
    
    # Remove a value from the array
    def remove(self, value):
        if value in self.data:
            self.data.remove(value)

    # Get the array size
    def size(self):
        return len(self.data)

    # Clear the array
    def clear(self):
        self.data = []

    # Print the array
    def print(self):
        print(self.data)

    @classmethod
    def update_last_processed_time(cls, symbol):
        current_time_minutes = time.time() / 60  # Convert current time to minutes
        cls.last_processed_time[symbol] = current_time_minutes

    # Get the last processed time for a symbol in minutes
    @classmethod
    def get_last_processed_time(cls, symbol):
        return cls.last_processed_time.get(symbol, 0)


class PriceData:
    # Static array that is global to the program
    price_data = [0] * 202

    # Constructor
    def __init__(self):
        pass

    # Add a value to the array
    def add(self, value):
        self.price_data.append(value)

    # Get the array
    def get(self):
        return self.price_data
    
    # Remove a value from the array
    def remove(self, value):
        if value in self.price_data:
            self.price_data.remove(value)

    # Get the array size
    def size(self):
        return len(self.price_data)

    # Clear the array
    def clear(self):
        self.price_data = []

    # Print the array
    def print(self):
        print(self.price_data)
        
class PositionData:
    # Static array that is global to the program
    position_data = [False] * 202

    # Constructor
    def __init__(self):
        pass

    # Add a value to the array
    def add(self, value):
        self.position_data.append(value)

    # Get the array
    def get(self):
        return self.position_data
    
    # Remove a value from the array
    def remove(self, value):
        if value in self.position_data:
            self.position_data.remove(value)

    # Get the array size
    def size(self):
        return len(self.position_data)

    # Clear the array
    def clear(self):
        self.position_data = []

    # Print the array
    def print(self):
        print(self.position_data)