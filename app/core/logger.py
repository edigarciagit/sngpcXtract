import logging
import sys
import os

def setup_logging():
    """
    Configures the logging for the entire application.
    Logs will be written to stdout and to a file.
    """
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, "app.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger("sngpc")

# Helper to get logger in other modules
def get_logger(name):
    return logging.getLogger(f"sngpc.{name}")
