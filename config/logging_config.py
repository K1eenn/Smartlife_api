import logging

# Thiết lập log
def setup_logging():
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                       handlers=[logging.StreamHandler()])
    
    # Use specific loggers per module/area if desired, otherwise a root logger is fine
    logger = logging.getLogger('family_assistant_api')
    weather_logger = logging.getLogger('weather_advisor')
    
    return logger, weather_logger

# Create loggers
logger, weather_logger = setup_logging()