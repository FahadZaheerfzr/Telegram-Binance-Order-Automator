import time

class CustomTime:

  start = 0

  def __init__(self):
    pass

  def start_time(self):
    self.start = time.time()

  def end_time(self):
    print(self.start)

    end_time = time.time()
    return end_time - self.start
  
  