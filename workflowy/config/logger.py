import logging

def setup_lambda_logger(name: str = "workflowy") -> logging.Logger:
    """
    Set up standardized logging for Lambda environment.
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Lambda-optimized configuration
    # level = logging.INFO if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') else logging.DEBUG
    level = logging.DEBUG
    
    # Create handler with Lambda-friendly format
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    
    return logger

# Global logger instance
logger = setup_lambda_logger()
