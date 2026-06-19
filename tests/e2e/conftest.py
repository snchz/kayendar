import os
import sys
import time
import shutil
import socket
import json
import hashlib
import subprocess
import pytest
from pathlib import Path
from typing import Generator, Dict, Any

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Helper to find a free TCP port
def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

# Server URL fixture
@pytest.fixture(scope="session")
def server_url() -> str:
    """Returns the URL of the target server. Defaults to spawning a local instance."""
    env_url = os.environ.get("KAYENDAR_TEST_URL")
    if env_url:
        return env_url.rstrip("/")
    
    # Otherwise, start a sandboxed local instance of Kayendar
    port = get_free_port()
    url = f"http://127.0.0.1:{port}"
    
    # Set up temporary data directory to isolate tests from dev data
    tmp_data_dir = REPO_ROOT / "tests" / "e2e" / "tmp_data"
    if tmp_data_dir.exists():
        shutil.rmtree(tmp_data_dir)
    tmp_data_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize basic users.json file in the temporary directory
    users_file = tmp_data_dir / "users.json"
    with open(users_file, "w") as f:
        json.dump({}, f)
        
    # Mutate parent process environment to propagate data directory
    os.environ["KAYENDAR_DATA_DIR"] = str(tmp_data_dir)
        
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    env["KAYENDAR_PORT"] = str(port)

    process = subprocess.Popen(
        [sys.executable, "-m", "server"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    # Wait for the port to open
    start_time = time.time()
    while time.time() - start_time < 10:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except (OSError, ConnectionRefusedError):
            if process.poll() is not None:
                raise RuntimeError(
                    f"Kayendar failed to start (exit code {process.returncode})"
                )
            time.sleep(0.1)
    else:
        process.terminate()
        process.wait()
        raise RuntimeError("Timeout waiting for Kayendar server to start")
        
    yield url
    
    # Terminate server
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        
    # Clean up temp data directory
    if tmp_data_dir.exists():
        shutil.rmtree(tmp_data_dir)
        
    # Remove mutated environment variable
    os.environ.pop("KAYENDAR_DATA_DIR", None)

# Fixture to provision a temporary test user
@pytest.fixture(scope="function")
def test_user(server_url) -> Generator[Dict[str, str], None, None]:
    """
    Creates a temporary user in the test user database (KAYENDAR_DATA_DIR/users.json)
    and removes the user and their calendar/contact directories after the test.
    """
    import random
    import string
    from server.auth import _lock_db_file
    
    # Determine the active data directory
    data_dir_env = os.environ.get("KAYENDAR_DATA_DIR")
    data_dir = Path(data_dir_env) if data_dir_env else REPO_ROOT / "data"
    users_json_path = data_dir / "users.json"
    
    # Generate unique credentials
    rand_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    username = f"testuser_{rand_suffix}"
    password = f"password_{rand_suffix}"
    
    # PBKDF2-SHA256 password hashing matching kayendar/auth.py
    salt_bytes = os.urandom(16)
    salt_hex = salt_bytes.hex()
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        100000
    )
    hash_hex = hash_bytes.hex()
    
    # Read existing users, append test user, write back
    users = {}
    with _lock_db_file(str(users_json_path)):
        if users_json_path.exists():
            with open(users_json_path, "r") as f:
                try:
                    users = json.load(f)
                except json.JSONDecodeError:
                    pass
                    
        users[username] = {
            "salt": salt_hex,
            "hash": hash_hex,
            "iterations": 100000,
            "algo": "pbkdf2_sha256",
            "email": f"{username}@example.com"
        }
        
        # Write back
        users_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(users_json_path, "w") as f:
            json.dump(users, f, indent=4)
        
    yield {"username": username, "password": password}
    
    # Teardown: Remove user from users.json
    with _lock_db_file(str(users_json_path)):
        if users_json_path.exists():
            with open(users_json_path, "r") as f:
                try:
                    users = json.load(f)
                except json.JSONDecodeError:
                    users = {}
            if username in users:
                del users[username]
            with open(users_json_path, "w") as f:
                json.dump(users, f, indent=4)
            
    # Teardown: Clean up user collections
    user_folder = data_dir / "collections" / username
    if user_folder.exists():
        shutil.rmtree(user_folder)

# WebDAV client fixture using Basic Auth
@pytest.fixture
def dav_session(server_url, test_user) -> Generator[Any, None, None]:
    """Returns an HTTP session pre-authenticated with Basic Auth for WebDAV calls."""
    import requests
    session = requests.Session()
    session.auth = (test_user["username"], test_user["password"])
    yield session
    session.close()

# SPA client fixture using Session Cookie Auth
@pytest.fixture
def spa_session(server_url, test_user) -> Generator[Any, None, None]:
    """Returns an HTTP session pre-authenticated with Cookie Session for the web client."""
    import requests
    session = requests.Session()
    # Log in to API
    login_resp = session.post(
        f"{server_url}/api/login",
        json={"username": test_user["username"], "password": test_user["password"]}
    )
    assert login_resp.status_code == 200, "Web API session login failed"
    yield session
    # Log out
    session.post(f"{server_url}/api/logout")
    session.close()
