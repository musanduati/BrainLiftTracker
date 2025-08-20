import logging
import json
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class LogContext:
    """Thread-local context for correlation tracking"""
    _local = threading.local()
    
    @classmethod
    def set_request_id(cls, request_id: str):
        """Set correlation ID for current request"""
        cls._local.request_id = request_id
    
    @classmethod
    def get_request_id(cls) -> Optional[str]:
        """Get current correlation ID"""
        return getattr(cls._local, 'request_id', None)
    
    @classmethod
    def set_project_id(cls, project_id: str):
        """Set project ID for current operation"""
        cls._local.project_id = project_id
    
    @classmethod
    def get_project_id(cls) -> Optional[str]:
        """Get current project ID"""
        return getattr(cls._local, 'project_id', None)
    
    @classmethod
    def set_project_name(cls, project_name: str):
        """Set project name for current operation"""
        cls._local.project_name = project_name
    
    @classmethod
    def get_project_name(cls) -> Optional[str]:
        """Get current project name"""
        return getattr(cls._local, 'project_name', None)
    
    @classmethod
    def set_operation(cls, operation: str):
        """Set current operation type"""
        cls._local.operation = operation
    
    @classmethod
    def get_operation(cls) -> Optional[str]:
        """Get current operation"""
        return getattr(cls._local, 'operation', None)
    
    @classmethod
    def clear_context(cls):
        """Clear all context variables"""
        cls._local.__dict__.clear()
    
    @classmethod
    def set_project_context(cls, project_id: str, project_name: str):
        """Convenience method to set both project ID and name"""
        cls.set_project_id(project_id)
        cls.set_project_name(project_name)


class JSONFormatter(logging.Formatter):
    """JSON formatter for Lambda CloudWatch logs"""
    
    def format(self, record):
        # Base log entry
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.name
        }
        
        # Add context if available
        if LogContext.get_request_id():
            log_entry['request_id'] = LogContext.get_request_id()
        
        if LogContext.get_project_id():
            log_entry['project_id'] = LogContext.get_project_id()
        
        if LogContext.get_project_name():
            log_entry['project_name'] = LogContext.get_project_name()
        
        if LogContext.get_operation():
            log_entry['operation'] = LogContext.get_operation()
        
        # Add Lambda context if available
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
            log_entry['function_name'] = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
            log_entry['environment'] = os.environ.get('ENVIRONMENT', 'unknown')
        
        # Add any custom fields from the log record
        if hasattr(record, 'custom_fields'):
            log_entry.update(record.custom_fields)
        
        # Add error information if present
        if record.exc_info:
            log_entry['error'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else 'Unknown',
                'message': str(record.exc_info[1]) if record.exc_info[1] else 'Unknown error',
                'traceback': self.formatException(record.exc_info)
            }
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for local development"""
    
    def format(self, record):
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        base_message = f"[{timestamp}] {record.levelname} - {LogContext.get_operation()} - {record.getMessage()}"
        
        # Add custom fields for development
        # if hasattr(record, 'custom_fields') and record.custom_fields:
        #     fields_str = ', '.join(f"{k}={v}" for k, v in record.custom_fields.items())
        #     base_message += f" | {fields_str}"
        
        # Add exception info if present
        if record.exc_info:
            base_message += f"\nError: {record.exc_info[1]}"
            if record.levelname == 'DEBUG':
                base_message += f"\n{self.formatException(record.exc_info)}"
        
        return base_message


class StructuredLogger:
    """Structured logger with operation-based methods"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def _log_operation(self, level: int, operation: str, message: str, error: Optional[Exception] = None, **kwargs):
        """Internal method to log structured operations"""

        if operation:
            LogContext.set_operation(operation)

        # Create custom fields from kwargs
        custom_fields = {}
        if operation:
            custom_fields['operation'] = operation
        custom_fields.update(kwargs)
        
        # Create log record
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn='',
            lno=0,
            msg=message,
            args=(),
            exc_info=sys.exc_info() if error else None
        )
        record.custom_fields = custom_fields
        
        self.logger.handle(record)
    
    def info_operation(self, operation: str, message: str, **kwargs):
        """Log info-level operation"""
        self._log_operation(logging.INFO, operation, message, **kwargs)
    
    def error_operation(self, operation: str, error: Exception, message: str, **kwargs):
        """Log error-level operation with exception details"""
        error_message = f"{message}: {str(error)}"
        self._log_operation(logging.ERROR, operation, error_message, error, **kwargs)
    
    def warning_operation(self, operation: str, message: str, **kwargs):
        """Log warning-level operation"""
        self._log_operation(logging.WARNING, operation, message, **kwargs)
    
    def debug_operation(self, operation: str, message: str, **kwargs):
        """Log debug-level operation"""
        self._log_operation(logging.DEBUG, operation, message, **kwargs)


def is_lambda_environment() -> bool:
    """Check if running in AWS Lambda environment"""
    return bool(os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))


def setup_logger(name: str = "workflowy") -> tuple[logging.Logger, StructuredLogger]:
    """
    Set up environment-aware logging.
    Returns both basic logger (for backward compatibility) and structured logger.
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger, StructuredLogger(logger)
    
    # Create handler
    handler = logging.StreamHandler()
    
    # Configure based on environment
    if is_lambda_environment():
        # Lambda environment: JSON formatting, INFO level
        formatter = JSONFormatter()
        level = logging.INFO
        print(f"✅ Configured JSON logging for Lambda environment: {os.environ.get('AWS_LAMBDA_FUNCTION_NAME')}")
    else:
        # Local environment: Human-readable formatting, DEBUG level  
        formatter = HumanReadableFormatter()
        level = logging.DEBUG
        print("✅ Configured human-readable logging for local development")
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    
    return logger, StructuredLogger(logger)


def reconfigure_logger_for_environment() -> tuple[logging.Logger, StructuredLogger]:
    """Reconfigure logger for current environment (useful for testing)"""
    # Clear existing handlers
    logger = logging.getLogger("workflowy")
    logger.handlers.clear()
    
    # Setup fresh configuration
    return setup_logger("workflowy")


# Global logger instances
logger, structured_logger = setup_logger()


# Legacy compatibility - keep the old function name
def setup_lambda_logger(name: str = "workflowy") -> logging.Logger:
    """Legacy function for backward compatibility"""
    basic_logger, _ = setup_logger(name)
    return basic_logger
