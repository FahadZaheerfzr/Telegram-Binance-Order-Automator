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
