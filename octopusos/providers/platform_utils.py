"""
Cross-platform utility module for AgentOS providers.

This module provides platform detection, path management, and executable detection
utilities for Windows, macOS, and Linux environments.

Features:
- Platform detection (Windows/macOS/Linux)
- Configuration directory management (cross-platform)
- Executable file detection with standard path support
- Executable validation (existence, permissions, extensions)

Sprint B+ Provider Architecture - Cross-platform Compatibility
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple


def get_platform() -> str:
    """
    Detect the current operating system platform.

    Returns:
        str: Platform identifier - 'windows', 'macos', or 'linux'

    Examples:
        >>> get_platform()
        'macos'  # On macOS
        'windows'  # On Windows
        'linux'  # On Linux
    """
    system = platform.system()
    if system == 'Windows':
        return 'windows'
    elif system == 'Darwin':
        return 'macos'
    else:
        return 'linux'


def get_config_dir() -> Path:
    """
    Get the AgentOS configuration directory for the current platform.

    Returns:
        Path: Configuration directory path
            - Windows: %APPDATA%\\agentos (e.g., C:\\Users\\User\\AppData\\Roaming\\agentos)
            - macOS/Linux: ~/.agentos

    Examples:
        >>> get_config_dir()
        Path('/Users/username/.agentos')  # macOS
        Path('C:/Users/username/AppData/Roaming/agentos')  # Windows
    """
    if get_platform() == 'windows':
        # Windows: Use AppData/Roaming directory
        appdata = os.environ.get('APPDATA')
        if appdata:
            return Path(appdata) / 'agentos'
        else:
            # Fallback if APPDATA is not set
            return Path.home() / 'AppData' / 'Roaming' / 'agentos'
    else:
        # macOS and Linux: Use hidden directory in home
        return Path.home() / '.agentos'


def _get_brew_prefix() -> Optional[Path]:
    """
    Get homebrew prefix by running 'brew --prefix'.

    Returns:
        Optional[Path]: Homebrew prefix path, or None if brew is not available

    Note:
        This function caches the result to avoid repeated subprocess calls.
        Supports both Intel (/usr/local) and Apple Silicon (/opt/homebrew) Macs.
    """
    # Check if brew is available
    if not shutil.which('brew'):
        return None

    try:
        result = subprocess.run(
            ['brew', '--prefix'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            prefix = result.stdout.strip()
            if prefix:
                return Path(prefix)
    except (subprocess.TimeoutExpired, Exception):
        pass

    return None


def get_run_dir() -> Path:
    """
    Get the directory for process PID files.

    Returns:
        Path: Run directory path (config_dir/run)

    Note:
        This directory is used to store PID files for running provider processes.
        The directory will be created automatically if it doesn't exist when needed.

    Examples:
        >>> get_run_dir()
        Path('/Users/username/.agentos/run')
    """
    return get_config_dir() / 'run'


def get_log_dir() -> Path:
    """
    Get the directory for log files.

    Returns:
        Path: Log directory path (config_dir/logs)

    Note:
        This directory is used to store provider service logs.
        The directory will be created automatically if it doesn't exist when needed.

    Examples:
        >>> get_log_dir()
        Path('/Users/username/.agentos/logs')
    """
    return get_config_dir() / 'logs'


def get_standard_paths(name: str) -> list[Path]:
    """
    Get standard installation paths for a provider executable.

    Args:
        name: Provider name - 'ollama', 'llama-server', or 'lmstudio'

    Returns:
        list[Path]: List of standard installation paths for the current platform

    Note:
        Paths are returned in priority order (most common first).
        The function returns platform-specific paths based on typical installation locations.
        Now includes extended search paths including homebrew locations.

    Examples:
        >>> get_standard_paths('ollama')  # On macOS
        [Path('/Applications/Ollama.app/Contents/MacOS/ollama'), Path('/usr/local/bin/ollama'), ...]
    """
    platform_type = get_platform()

    if name == 'ollama':
        if platform_type == 'windows':
            return [
                Path.home() / 'AppData' / 'Local' / 'Programs' / 'Ollama' / 'ollama.exe',
                Path('C:/Program Files/Ollama/ollama.exe'),
                Path.home() / 'AppData' / 'Local' / 'Ollama' / 'ollama.exe',
            ]
        elif platform_type == 'macos':
            paths = [
                Path('/Applications/Ollama.app/Contents/MacOS/ollama'),
                Path('/usr/local/bin/ollama'),
                Path('/opt/homebrew/bin/ollama'),
                Path.home() / 'Applications' / 'Ollama.app' / 'Contents' / 'MacOS' / 'ollama',
            ]
            # Try to add brew --prefix path if brew is available
            brew_prefix = _get_brew_prefix()
            if brew_prefix:
                brew_path = brew_prefix / 'bin' / 'ollama'
                if brew_path not in paths:
                    paths.insert(2, brew_path)
            return paths
        else:  # linux
            return [
                Path('/usr/local/bin/ollama'),
                Path('/usr/bin/ollama'),
                Path.home() / '.local' / 'bin' / 'ollama',
            ]

    elif name == 'llama-server':
        if platform_type == 'windows':
            return [
                Path.home() / 'AppData' / 'Local' / 'llama.cpp' / 'llama-server.exe',
                Path('C:/Program Files/llama.cpp/llama-server.exe'),
                Path('bin') / 'llama-server.exe',  # Project local bin
            ]
        elif platform_type == 'macos':
            paths = [
                Path('/usr/local/bin/llama-server'),
                Path('/opt/homebrew/bin/llama-server'),
            ]
            # Try to add brew --prefix path if brew is available
            brew_prefix = _get_brew_prefix()
            if brew_prefix:
                brew_path = brew_prefix / 'bin' / 'llama-server'
                if brew_path not in paths:
                    paths.insert(1, brew_path)
            # Add project local bin
            paths.append(Path('bin') / 'llama-server')
            return paths
        else:  # linux
            return [
                Path('/usr/local/bin/llama-server'),
                Path('/usr/bin/llama-server'),
                Path.home() / '.local' / 'bin' / 'llama-server',
                Path('bin') / 'llama-server',  # Project local bin
            ]

    elif name == 'lmstudio':
        if platform_type == 'windows':
            return [
                Path.home() / 'AppData' / 'Local' / 'Programs' / 'LM Studio' / 'LM Studio.exe',
                Path('C:/Program Files/LM Studio/LM Studio.exe'),
                Path(os.environ.get('USERPROFILE', str(Path.home()))) / 'AppData' / 'Local' / 'Programs' / 'LM Studio' / 'LM Studio.exe',
            ]
        elif platform_type == 'macos':
            return [
                Path('/Applications/LM Studio.app'),
                Path.home() / 'Applications' / 'LM Studio.app',
            ]
        else:  # linux
            return [
                Path.home() / '.local' / 'share' / 'lm-studio' / 'LM Studio.AppImage',
                Path('/opt/lm-studio/lm-studio'),
                Path.home() / 'lm-studio' / 'lm-studio',
                Path.home() / 'Downloads' / 'LM Studio.AppImage',  # Common download location
            ]

    # Unknown provider name
    return []


def find_in_path(name: str) -> Optional[Path]:
    """
    Find an executable in the PATH environment variable.

    This function searches for executables in the system PATH with cross-platform support:
    - Windows: Automatically tries .exe, .cmd, .bat extensions
    - Unix (macOS/Linux): Direct search without extension

    Args:
        name: Executable name (without extension on Windows)

    Returns:
        Optional[Path]: Path to the executable if found, None otherwise

    Priority:
        1. Use shutil.which() for standard lookup
        2. If not found, manually scan PATH directories (fallback)

    Examples:
        >>> find_in_path('ollama')  # macOS/Linux
        Path('/usr/local/bin/ollama')

        >>> find_in_path('ollama')  # Windows
        Path('C:/Program Files/Ollama/ollama.exe')

    Note:
        On Windows, this function will try multiple extensions in order:
        .exe, .cmd, .bat
    """
    platform_type = get_platform()

    # Step 1: Try shutil.which() first (standard approach)
    if platform_type == 'windows':
        # On Windows, try with different extensions
        for ext in ['.exe', '.cmd', '.bat', '']:
            exe_name = f"{name}{ext}" if ext else name
            path_str = shutil.which(exe_name)
            if path_str:
                path = Path(path_str)
                if validate_executable(path):
                    return path
    else:
        # Unix: search without extension
        path_str = shutil.which(name)
        if path_str:
            path = Path(path_str)
            if validate_executable(path):
                return path

    # Step 2: Manual PATH scanning (fallback)
    # This handles edge cases where shutil.which() might fail
    path_env = os.environ.get('PATH', '')
    if not path_env:
        return None

    path_dirs = path_env.split(os.pathsep)

    for dir_str in path_dirs:
        try:
            dir_path = Path(dir_str)
            if not dir_path.exists() or not dir_path.is_dir():
                continue

            if platform_type == 'windows':
                # Try with extensions
                for ext in ['.exe', '.cmd', '.bat']:
                    exe_path = dir_path / f"{name}{ext}"
                    if validate_executable(exe_path):
                        return exe_path
            else:
                # Unix: direct lookup
                exe_path = dir_path / name
                if validate_executable(exe_path):
                    return exe_path
        except (PermissionError, OSError):
            # Skip directories we can't access
            continue

    return None


def validate_executable(path: Path) -> bool:
    """
    Validate that a path points to a valid executable file.

    Args:
        path: Path to the executable file

    Returns:
        bool: True if the file is a valid executable, False otherwise

    Validation checks:
        - File exists
        - Windows: Has .exe extension (for standard executables)
        - Unix (macOS/Linux): Has executable permission (os.X_OK)

    Note:
        On Windows, .bat and .cmd files are also considered valid executables
        even without .exe extension.

    Examples:
        >>> validate_executable(Path('/usr/local/bin/ollama'))
        True  # On Unix with executable permission
        >>> validate_executable(Path('C:/Program Files/Ollama/ollama.exe'))
        True  # On Windows with .exe extension
    """
    # Check if file exists
    if not path.exists():
        return False

    # Check if it's a file (not a directory)
    if not path.is_file():
        # Special case: macOS .app bundles are directories
        if get_platform() == 'macos' and path.suffix == '.app':
            return True
        return False

    platform_type = get_platform()

    if platform_type == 'windows':
        # Windows: Check for executable extensions
        valid_extensions = {'.exe', '.bat', '.cmd'}
        return path.suffix.lower() in valid_extensions
    else:
        # Unix (macOS/Linux): Check executable permission
        return os.access(path, os.X_OK)


def get_executable_version(path: Path, timeout: float = 5.0) -> Optional[str]:
    """
    Get version of an executable by running --version command.

    Args:
        path: Path to the executable
        timeout: Command timeout in seconds (default: 5.0)

    Returns:
        Optional[str]: Version string if successful, None otherwise

    Note:
        Executes '{executable} --version' and captures output.
        Handles timeout and errors gracefully.
        Some executables might return version on stderr instead of stdout.

    Examples:
        >>> get_executable_version(Path('/usr/local/bin/ollama'))
        'ollama version 0.1.26'
    """
    try:
        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            # Return stdout stripped of whitespace
            output = result.stdout.strip()
            if output:
                return output
            # Some executables return version on stderr
            stderr_output = result.stderr.strip()
            if stderr_output:
                return stderr_output
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def validate_executable_detailed(path: Path) -> Dict[str, Any]:
    """
    Validate an executable file with detailed results.

    Args:
        path: Path to the executable file

    Returns:
        dict: Detailed validation results containing:
            - is_valid (bool): Overall validation result
            - exists (bool): Whether the file exists
            - is_executable (bool): Whether the file has executable permissions
            - version (Optional[str]): Version information if available
            - error (Optional[str]): Error message if validation failed

    Validation checks:
        - File exists
        - Windows: Has .exe/.bat/.cmd extension or is a recognized executable
        - Unix (macOS/Linux): Has executable permission (os.X_OK)
        - macOS: Special handling for .app bundles

    Examples:
        >>> validate_executable_detailed(Path('/usr/local/bin/ollama'))
        {
            'is_valid': True,
            'exists': True,
            'is_executable': True,
            'version': 'ollama version 0.1.26',
            'error': None
        }

        >>> validate_executable_detailed(Path('/nonexistent'))
        {
            'is_valid': False,
            'exists': False,
            'is_executable': False,
            'version': None,
            'error': 'File does not exist'
        }
    """
    result = {
        'is_valid': False,
        'exists': False,
        'is_executable': False,
        'version': None,
        'error': None
    }

    # Check if file exists
    if not path.exists():
        result['error'] = f'File does not exist: {path}'
        return result

    result['exists'] = True

    # Check if it's a file (not a directory)
    if not path.is_file():
        # Special case: macOS .app bundles are directories
        if get_platform() == 'macos' and path.suffix == '.app':
            result['is_executable'] = True
            result['is_valid'] = True
            return result
        else:
            result['error'] = f'Path is not a file: {path}'
            return result

    platform_type = get_platform()

    if platform_type == 'windows':
        # Windows: Check for executable extensions
        valid_extensions = {'.exe', '.bat', '.cmd'}
        if path.suffix.lower() in valid_extensions:
            result['is_executable'] = True
            result['is_valid'] = True
            # Try to get version
            result['version'] = get_executable_version(path)
        else:
            result['error'] = f'File must have .exe, .bat, or .cmd extension on Windows: {path}'
    else:
        # Unix (macOS/Linux): Check executable permission
        if os.access(path, os.X_OK):
            result['is_executable'] = True
            result['is_valid'] = True
            # Try to get version
            result['version'] = get_executable_version(path)
        else:
            result['error'] = f'File is not executable. Run "chmod +x {path}" to fix permissions.'

    return result


def find_executable(name: str, custom_paths: Optional[list[str]] = None) -> Optional[Path]:
    """
    Cross-platform executable file finder with enhanced search strategy.

    Search for provider executables with the following priority:
    1. User-provided custom paths (if specified) - highest priority
    2. Platform-specific standard installation paths
    3. System PATH environment variable

    Args:
        name: Provider name - 'ollama', 'llama-server', or 'lmstudio'
        custom_paths: Optional list of custom search paths to check first

    Returns:
        Optional[Path]: Path to the executable if found, None otherwise

    Priority Order:
        Priority 1: User Configuration (custom_paths parameter)
            - Explicitly provided paths take absolute precedence
            - Allows users to override auto-detection

        Priority 2: Standard Installation Paths
            - Platform-specific default locations
            - Includes homebrew paths on macOS (via brew --prefix)
            - Common installation directories on all platforms

        Priority 3: System PATH Environment Variable
            - Uses find_in_path() for robust PATH scanning
            - Windows: Auto-tries .exe, .cmd, .bat extensions
            - Unix: Direct executable lookup

    Notes:
        - All found executables are validated using validate_executable()
        - Returns the first valid executable found in priority order
        - Windows paths support both forward and backslashes

    Examples:
        >>> find_executable('ollama')
        Path('/Applications/Ollama.app/Contents/MacOS/ollama')  # macOS standard path

        >>> find_executable('ollama', custom_paths=['/opt/custom/ollama'])
        Path('/opt/custom/ollama')  # Custom path takes precedence

        >>> find_executable('llama-server')
        Path('/opt/homebrew/bin/llama-server')  # Found via brew --prefix

        >>> find_executable('nonexistent')
        None  # Not found in any location
    """
    # Priority 1: Check user-provided custom paths first
    if custom_paths:
        for path_str in custom_paths:
            path = Path(path_str)
            if validate_executable(path):
                return path

    # Priority 2: Check platform-specific standard installation paths
    standard_paths = get_standard_paths(name)
    for path in standard_paths:
        if validate_executable(path):
            return path

    # Priority 3: Check system PATH environment variable
    # Use the new find_in_path() function for robust PATH searching
    path_result = find_in_path(name)
    if path_result:
        return path_result

    # Not found in any location
    return None


def normalize_path(path_str: str) -> Path:
    r"""
    Normalize a path string to a pathlib.Path object with proper handling.

    This function handles:
    - Environment variable expansion (e.g., %USERPROFILE%, $HOME)
    - User home directory expansion (~)
    - Path separators (automatically handled by pathlib.Path)
    - UNC paths on Windows (\\server\share)
    - Drive letters on Windows (C:\Users\...)

    Args:
        path_str: Path string to normalize

    Returns:
        Path: Normalized pathlib.Path object

    Examples:
        >>> normalize_path('%USERPROFILE%\\Documents')  # Windows
        Path('C:/Users/username/Documents')

        >>> normalize_path('~/models')  # Unix
        Path('/Users/username/models')

        >>> normalize_path('\\\\server\\share\\models')  # UNC path
        Path('//server/share/models')
    """
    # Expand environment variables
    expanded = os.path.expandvars(path_str)

    # Create Path object (handles backslash/forward slash automatically)
    path_obj = Path(expanded)

    # Expand user home directory
    path_obj = path_obj.expanduser()

    return path_obj


def expand_user_path(path_str: str) -> Path:
    """
    Expand user home directory and resolve symlinks.

    This function:
    - Expands ~ to user home directory
    - Resolves symbolic links to real paths
    - Returns absolute path

    Args:
        path_str: Path string potentially containing ~ or symlinks

    Returns:
        Path: Resolved absolute path

    Examples:
        >>> expand_user_path('~/.ollama/models')
        Path('/Users/username/.ollama/models')

        >>> expand_user_path('/usr/local/bin/linked')
        Path('/opt/homebrew/bin/actual')  # If it's a symlink
    """
    # First normalize the path
    path_obj = normalize_path(path_str)

    # Resolve symlinks and make absolute
    try:
        resolved = path_obj.resolve()
        return resolved
    except (OSError, RuntimeError):
        # If resolve fails, return the expanded path without resolving
        return path_obj.absolute()


def get_models_dir(provider_name: str) -> Optional[Path]:
    """
    Get the default models directory for a specific provider.

    Args:
        provider_name: Provider name - 'ollama', 'llamacpp', or 'lmstudio'

    Returns:
        Optional[Path]: Default models directory for the provider, or None if cannot be determined

    Note:
        This function provides default locations. Users can override these
        in the providers configuration file.

        For Ollama on Windows, it checks multiple locations in priority order.

    Examples:
        >>> get_models_dir('ollama')
        Path('/Users/username/.ollama/models')  # macOS/Linux
        Path('C:/Users/username/.ollama/models')  # Windows (primary)
        Path('C:/Users/username/AppData/Local/Ollama/models')  # Windows (fallback)
    """
    platform_type = get_platform()

    if provider_name == 'ollama':
        if platform_type == 'windows':
            # Windows: Check two locations in priority order
            # 1. %USERPROFILE%\.ollama\models
            primary = Path.home() / '.ollama' / 'models'
            if primary.exists():
                return primary

            # 2. %LOCALAPPDATA%\Ollama\models
            local_appdata = os.environ.get('LOCALAPPDATA')
            if local_appdata:
                fallback = Path(local_appdata) / 'Ollama' / 'models'
                if fallback.exists():
                    return fallback

            # Return primary path as default even if it doesn't exist yet
            return primary
        else:
            # macOS/Linux: ~/.ollama/models
            return Path.home() / '.ollama' / 'models'

    elif provider_name == 'lmstudio':
        if platform_type == 'windows':
            # Windows: %LOCALAPPDATA%\lm-studio\models
            local_appdata = os.environ.get('LOCALAPPDATA')
            if local_appdata:
                return Path(local_appdata) / 'lm-studio' / 'models'
            # Fallback
            return Path.home() / 'AppData' / 'Local' / 'lm-studio' / 'models'
        else:
            # macOS/Linux: ~/.cache/lm-studio/models
            return Path.home() / '.cache' / 'lm-studio' / 'models'

    elif provider_name == 'llamacpp':
        # LlamaCpp doesn't have a standard location - encourage user configuration
        # Return None to indicate user should configure this
        return None

    # Unknown provider, return None
    return None


# Convenience function for backward compatibility with existing code
def get_models_dir_legacy(provider_name: str) -> Path:
    """
    Legacy version of get_models_dir that always returns a Path (never None).

    Deprecated: Use get_models_dir() instead, which can return None for llamacpp.

    Args:
        provider_name: Provider name - 'ollama', 'llamacpp', or 'lmstudio'

    Returns:
        Path: Default models directory for the provider

    Examples:
        >>> get_models_dir_legacy('ollama')
        Path('/Users/username/.ollama/models')
    """
    result = get_models_dir(provider_name)
    if result is not None:
        return result

    # Fallback for llamacpp and unknown providers
    platform_type = get_platform()
    if provider_name == 'llamacpp':
        # Suggest Documents/AI Models as a reasonable default
        if platform_type == 'windows':
            return Path.home() / 'Documents' / 'AI Models'
        else:
            # Use underscores on Linux to avoid space issues
            if platform_type == 'linux':
                return Path.home() / 'Documents' / 'AI_Models'
            else:  # macOS
                return Path.home() / 'Documents' / 'AI Models'

    # Unknown provider, return a generic location
    return get_config_dir() / 'models' / provider_name
