"""Exceptions for capability execution"""


class CapabilityError(Exception):
    """Base exception for capability-related errors"""
    pass


class ExecutionError(CapabilityError):
    """Error during capability execution"""
    pass


class ToolNotFoundError(CapabilityError):
    """Tool executable not found"""
    pass


class TimeoutError(CapabilityError):
    """Execution timeout"""
    pass


class SecurityError(CapabilityError):
    """Security policy violation"""
    pass
