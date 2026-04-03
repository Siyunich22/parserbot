import logging
import sys
from pathlib import Path
from config import LOGS_DIR, LOG_LEVEL

def setup_logger(name: str) -> logging.Logger:
    """Настроить логгер"""
    logger = logging.getLogger(name)
    
    # Очищаем старые handlers
    if logger.handlers:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
    
    logger.setLevel(LOG_LEVEL)
    
    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Логи в файл
    log_file = LOGS_DIR / f"{name}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Логи в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    logger.propagate = False
    
    return logger

logger = setup_logger("parser")
