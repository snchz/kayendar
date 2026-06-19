import os
import json
import hashlib
import hmac
import threading
import re
import sys
import contextlib

try:
    import portalocker
except ImportError:
    portalocker = None

# Configurable database path
USER_DB_PATH = None


def _get_db_path() -> str:
    if USER_DB_PATH is not None:
        return USER_DB_PATH
    return os.path.join(os.environ.get("KAYENDAR_DATA_DIR", "data"), "users.json")


@contextlib.contextmanager
def _lock_db_file(db_path: str):
    lock_path = db_path + ".lock"
    db_dir = os.path.dirname(lock_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
        
    import time
    attempts = 10
    sleep_time = 0.05
    lf = None
    locked = False
    last_err = None

    for attempt in range(attempts):
        try:
            lf = open(lock_path, "w")
            if portalocker is not None:
                portalocker.lock(lf, portalocker.LOCK_EX)
            elif sys.platform.startswith("win"):
                import msvcrt
                lf.seek(0)
                msvcrt.locking(lf.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            locked = True
            break
        except Exception as e:
            last_err = e
            if lf is not None:
                try:
                    lf.close()
                except Exception:
                    pass
                lf = None
            if attempt < attempts - 1:
                time.sleep(sleep_time)

    if not locked:
        raise OSError(f"Could not acquire lock on {lock_path} after 10 attempts") from last_err

    try:
        yield
    finally:
        try:
            if portalocker is not None:
                portalocker.unlock(lf)
            elif sys.platform.startswith("win"):
                import msvcrt
                lf.seek(0)
                msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        finally:
            try:
                lf.close()
            except Exception:
                pass


# Lock to synchronize reads and writes to the users database
_db_lock = threading.Lock()

def _load_users() -> dict:
    """Load the users dictionary from the JSON database file.
    Must be called while holding _db_lock.
    """
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return {}
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    
    if not isinstance(data, dict):
        raise ValueError("Database root must be a dictionary")
    return data

def _save_users(users: dict) -> None:
    """Save the users dictionary atomically to the JSON database file.
    Must be called while holding _db_lock.
    """
    db_path = _get_db_path()
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    tmp_path = db_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4)
        os.replace(tmp_path, db_path)
    except Exception as e:
        # Clean up temporary file if it was created
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise e

def validate_username(username: str) -> bool:
    """Validate username according to the strict constraints.
    
    Raises:
        ValueError on validation failure.
    """
    if not isinstance(username, str):
        raise ValueError("Username must be a string")
    if not username:
        raise ValueError("Username cannot be empty")
    if username != username.strip():
        raise ValueError("Username cannot contain leading or trailing whitespace")
    if not username.strip():
        raise ValueError("Username cannot be empty or whitespace only")
    if len(username) > 128:
        raise ValueError("Username is too long (max 128 characters)")
    if username in (".", ".."):
        raise ValueError("Username cannot be . or ..")
    if ".." in username or "/" in username or "\\" in username:
        raise ValueError("Username contains path traversal characters")
    if not re.match(r"^[a-zA-Z0-9_\-\.\@]+$", username):
        raise ValueError("Username contains invalid characters")
        
    # Windows reserved names validation
    clean_id = username.strip().rstrip(".")
    first_part = clean_id.split(".")[0].strip().upper()
    reserved_names = {
        "CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
    }
    if first_part in reserved_names:
        raise ValueError("Username is a reserved name")
            
    return True


def create_user(username: str, password: str) -> bool:
    """Create a new user with the given username and password.
    
    Returns:
        bool: True if user was created successfully, False if user already exists.
        
    Raises:
        ValueError: If username or password are not non-empty strings, or if validation fails.
    """
    if not isinstance(username, str) or not isinstance(password, str):
        raise ValueError("Username and password must be strings")
    if not username.strip() or not password.strip():
        raise ValueError("Username and password cannot be empty or whitespace only")
    
    # Reject . and .. explicitly
    if username in (".", ".."):
        raise ValueError("Username cannot be . or ..")
        
    validate_username(username)

    # Password length limit
    if len(password) > 256:
        raise ValueError("Password is too long (max 256 characters)")
        
    # Check if user already exists
    user_exists = False
    with _db_lock:
        with _lock_db_file(_get_db_path()):
            users = _load_users()
            if username in users:
                user_exists = True

    if user_exists:
        # Perform dummy PBKDF2 calculation to make registration response times uniform
        dummy_salt = b"\x00" * 16
        _ = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            dummy_salt,
            100000
        )
        return False
            
    # Salt: cryptographically secure 16 random bytes (hex-encoded)
    salt_bytes = os.urandom(16)
    salt_hex = salt_bytes.hex()
    
    # Hash: hashlib.pbkdf2_hmac with sha256 and 100,000 iterations
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        100000
    )
    hash_hex = hash_bytes.hex()
    
    with _db_lock:
        with _lock_db_file(_get_db_path()):
            # Re-check existence to prevent race condition
            users = _load_users()
            if username in users:
                return False
            
            users[username] = {
                "salt": salt_hex,
                "hash": hash_hex,
                "iterations": 100000,
                "algo": "pbkdf2_sha256"
            }
            
            _save_users(users)
            return True


def verify_user(username: str, password: str) -> bool:
    """Verify the username and password credentials.
    
    Returns:
        bool: True if credentials are valid, False otherwise.
        
    Raises:
        ValueError: If username or password are not non-empty strings, or if validation fails.
    """
    if not isinstance(username, str) or not isinstance(password, str):
        raise ValueError("Username and password must be strings")
    if not username.strip() or not password.strip():
        raise ValueError("Username and password cannot be empty or whitespace only")
    
    # Reject . and .. explicitly
    if username in (".", ".."):
        raise ValueError("Username cannot be . or ..")
        
    validate_username(username)

    # Password length limit
    if len(password) > 256:
        raise ValueError("Password is too long (max 256 characters)")

    # Read the user information under lock to prevent race conditions
    with _db_lock:
        with _lock_db_file(_get_db_path()):
            users = _load_users()
            user_info = users.get(username)
    
    # Timing attack mitigation: Run PBKDF2 in all cases.
    if user_info is not None and isinstance(user_info, dict):
        salt_hex = user_info.get("salt")
        stored_hash_hex = user_info.get("hash")
        iterations = user_info.get("iterations")
        algo = user_info.get("algo", "pbkdf2_sha256")
        
        # Check if iterations is positive integer and within safe range (<= 100000)
        if (isinstance(iterations, int) and 0 < iterations <= 100000 and 
            isinstance(salt_hex, str) and isinstance(stored_hash_hex, str)):
            try:
                salt_bytes = bytes.fromhex(salt_hex)
                hash_name = "sha256" if algo == "pbkdf2_sha256" else "sha256"
                
                computed_hash_bytes = hashlib.pbkdf2_hmac(
                    hash_name,
                    password.encode("utf-8"),
                    salt_bytes,
                    iterations
                )
                computed_hash_hex = computed_hash_bytes.hex()
                return hmac.compare_digest(computed_hash_hex, stored_hash_hex)
            except Exception:
                # If anything fails (like fromhex), fall through to dummy timing path
                pass

    # Dummy timing path (for missing user or malformed record)
    dummy_salt = b"\x00" * 16
    dummy_hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        dummy_salt,
        100000
    )
    dummy_hash_hex = dummy_hash_bytes.hex()
    
    # Compare with dummy string to consume time in digest comparison
    hmac.compare_digest(dummy_hash_hex, "0" * 64)
    return False


def delete_user(username: str) -> bool:
    """Remove a user from the database. Returns False if the user does not exist."""
    if not isinstance(username, str):
        raise ValueError("Username must be a string")
    validate_username(username)

    with _db_lock:
        with _lock_db_file(_get_db_path()):
            users = _load_users()
            if username not in users:
                return False
            del users[username]
            _save_users(users)
    return True


def list_users() -> list[str]:
    """Return sorted usernames from the database."""
    with _db_lock:
        with _lock_db_file(_get_db_path()):
            users = _load_users()
    return sorted(users)
