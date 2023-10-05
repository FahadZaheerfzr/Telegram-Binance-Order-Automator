import subprocess
import time
import logging
from utils import setup_logger

def run_script():
    monitor_logger = setup_logger("monitor")
    monitor_logger.info("Starting script...")
    print("Starting script...")
    while True:
        # Start the script as a subprocess
        script_process = subprocess.Popen(['python3', 'telegramChannelListener.py'],
                                          stderr=subprocess.PIPE)
        
        # Wait for the script to finish
        script_process.wait()
        print(script_process.returncode)
        # If the script exited normally (return code 0), break the loop
        
        
        # Log the error
        stderr = script_process.stderr
        if stderr is not None:
            error_message = stderr.read().decode('utf-8').strip()
            monitor_logger.error(error_message)
            print(error_message)
        
        print("Script stopped. Restarting...")
        time.sleep(5)  # Wait for 5 seconds before restarting

run_script()