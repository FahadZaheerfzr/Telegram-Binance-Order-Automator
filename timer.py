import time

start = 0

def start_timer():
    global start
    start = time.time()

def end_timer():
    global start
    time_taken = time.time() - start
    start = 0
    return time_taken

