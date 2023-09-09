import os
import datetime
import logging

def setup_logger(logfile, logdir=os.getcwd() + "/data/log"):
    """
    Configure and return a logger with a specific logfile in the specified directory.
    """
    if not os.path.exists(logdir):
        os.makedirs(logdir)
    
    # Get current date
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Define logfile paths
    current_logfile_path = os.path.join(logdir, logfile + "-" + today + ".log")
    old_logfile_paths = [os.path.join(logdir, fname) for fname in os.listdir(logdir) if fname.startswith(logfile + "-")]
    
    # Delete log files older than 3 days
    for old_path in old_logfile_paths:
        try:
            old_date = datetime.datetime.strptime(old_path[-14:-4], "%Y-%m-%d")
            if (datetime.datetime.now() - old_date).days > 3:
                os.remove(old_path)
        except ValueError:
            pass  # Ignore filenames that don't match the expected pattern
    
    logger = logging.getLogger(logfile)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Add a file handler to write logs to the specified file
    file_handler = logging.FileHandler(current_logfile_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger