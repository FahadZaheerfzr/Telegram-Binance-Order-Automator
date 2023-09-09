# Define a class that contains a static array that is global to the program

class Data:
    # Static array that is global to the program
    data = []

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