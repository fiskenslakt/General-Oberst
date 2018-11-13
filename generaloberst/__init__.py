import logging

from disco.util.logging import LOG_FORMAT

# Log things to file
file_handler = logging.FileHandler('logs/generaloberst.log')
log = logging.getLogger()
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
log.addHandler(file_handler)
