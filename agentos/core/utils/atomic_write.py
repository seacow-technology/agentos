"""Atomic file write with OK marker.

Ensures file write atomicity and integrity verification for critical artifacts.

The write flow:
1. Write to file.tmp
2. fsync (ensure physical write)
3. rename to final name (atomic operation)
4. Write file.ok marker with hash/size/timestamp
5. fsync the .ok marker

This guarantees that:
- Files are either fully written or not present (no partial writes)
- Corruption can be detected via hash validation
- Interruptions (kill -9, power loss) don't leave corrupted files

Example:
    from agentos.core.utils.atomic_write import atomic_write, verify_atomic_write
from agentos.core.time import utc_now_iso


    # Write file atomically
    metadata = atomic_write("/path/to/file.json", "content")

    # Later, verify integrity
    is_valid, error = verify_atomic_write("/path/to/file.json")
    if not is_valid:
        print(f"File corrupted: {error}")
"""

import os
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Union, Dict, Any, Tuple


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """Compute hash of file content.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, md5, etc.)

    Returns:
        Hex digest of file hash
    """
    hasher = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)

    return hasher.hexdigest()


def atomic_write(
    file_path: Union[str, Path],
    content: Union[str, bytes],
    mode: str = 'w',
    create_ok_marker: bool = True
) -> Dict[str, Any]:
    """Write file atomically with optional .ok marker.

    Flow:
    1. Write to file.tmp
    2. fsync (ensure physical write to disk)
    3. Atomic rename file.tmp → file
    4. Write file.ok marker with sha256/size/timestamp
    5. fsync .ok marker

    Args:
        file_path: Target file path
        content: Content to write
        mode: Write mode ('w' for text, 'wb' for binary)
        create_ok_marker: Create .ok marker file (default: True)

    Returns:
        Dictionary with file metadata:
        - sha256: File hash
        - size: File size in bytes
        - timestamp: Write timestamp (ISO 8601)
        - path: Final file path
        - ok_marker_path: Path to .ok marker (if created)

    Example:
        metadata = atomic_write(
            "/tmp/checkpoint.json",
            json.dumps({"data": "value"}),
            mode='w'
        )
        print(f"Wrote {metadata['size']} bytes, hash={metadata['sha256']}")
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = file_path.with_suffix(file_path.suffix + '.tmp')
    ok_path = file_path.with_suffix(file_path.suffix + '.ok')

    # 1. Write to temporary file
    with open(tmp_path, mode) as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())  # Ensure physical write

    # 2. Compute hash and size
    file_hash = compute_file_hash(tmp_path)
    file_size = tmp_path.stat().st_size

    # 3. Atomic rename (POSIX guarantees atomicity)
    tmp_path.replace(file_path)  # replace() is atomic

    # 4. Create .ok marker (optional)
    metadata = {
        "sha256": file_hash,
        "size": file_size,
        "timestamp": utc_now_iso(),
        "path": str(file_path)
    }

    if create_ok_marker:
        with open(ok_path, 'w') as f:
            json.dump(metadata, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        metadata["ok_marker_path"] = str(ok_path)

    return metadata


def verify_atomic_write(
    file_path: Union[str, Path],
    require_ok_marker: bool = True
) -> Tuple[bool, str]:
    """Verify file was written atomically with .ok marker.

    Checks:
    1. .ok marker exists (if required)
    2. File exists
    3. SHA256 hash matches
    4. File size matches

    Args:
        file_path: File to verify
        require_ok_marker: Require .ok marker to exist (default: True)

    Returns:
        (is_valid, error_message):
        - (True, "OK"): File is valid
        - (False, error): Verification failed with reason

    Example:
        is_valid, error = verify_atomic_write("/tmp/checkpoint.json")
        if not is_valid:
            print(f"Verification failed: {error}")
    """
    file_path = Path(file_path)
    ok_path = file_path.with_suffix(file_path.suffix + '.ok')

    # 1. Check .ok marker exists (if required)
    if require_ok_marker and not ok_path.exists():
        return False, f"OK marker not found: {ok_path}"

    # 2. Check file exists
    if not file_path.exists():
        return False, f"File not found: {file_path}"

    # If .ok marker not required and doesn't exist, just check file exists
    if not require_ok_marker and not ok_path.exists():
        return True, "OK (no marker verification)"

    # 3. Read .ok metadata
    try:
        with open(ok_path) as f:
            metadata = json.load(f)
    except Exception as e:
        return False, f"Failed to read OK marker: {e}"

    # 4. Verify hash
    expected_hash = metadata.get("sha256")
    if not expected_hash:
        return False, "OK marker missing sha256 field"

    try:
        actual_hash = compute_file_hash(file_path)
    except Exception as e:
        return False, f"Failed to compute file hash: {e}"

    if expected_hash != actual_hash:
        return False, f"Hash mismatch: expected {expected_hash[:16]}..., got {actual_hash[:16]}..."

    # 5. Verify size
    expected_size = metadata.get("size")
    if expected_size is not None:
        actual_size = file_path.stat().st_size

        if expected_size != actual_size:
            return False, f"Size mismatch: expected {expected_size}, got {actual_size}"

    return True, "OK"


def atomic_write_json(
    file_path: Union[str, Path],
    data: Dict[str, Any],
    indent: int = 2,
    create_ok_marker: bool = True
) -> Dict[str, Any]:
    """Convenience wrapper for atomic JSON write.

    Args:
        file_path: Target JSON file path
        data: Dictionary to write
        indent: JSON indentation (default: 2)
        create_ok_marker: Create .ok marker (default: True)

    Returns:
        File metadata dictionary
    """
    content = json.dumps(data, indent=indent)
    return atomic_write(file_path, content, mode='w', create_ok_marker=create_ok_marker)


__all__ = [
    'atomic_write',
    'atomic_write_json',
    'verify_atomic_write',
    'compute_file_hash'
]
