"""Exception classes for the Extension system"""


class ExtensionError(Exception):
    """Base exception for all extension-related errors"""
    pass


class ValidationError(ExtensionError):
    """Raised when extension validation fails"""
    pass


class InstallationError(ExtensionError):
    """Raised when extension installation fails"""
    pass


class DownloadError(ExtensionError):
    """Raised when extension download fails"""
    pass


class RegistryError(ExtensionError):
    """Raised when registry operations fail"""
    pass
