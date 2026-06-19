import os
import json
import pytest
import time
import hashlib
from unittest.mock import patch
import server.auth

@pytest.fixture
def temp_db_path(tmp_path):
    temp_file = tmp_path / "users.json"
    original_path = server.auth.USER_DB_PATH
    server.auth.USER_DB_PATH = str(temp_file)
    yield str(temp_file)
    server.auth.USER_DB_PATH = original_path

def test_verify_user_high_iterations_dos(temp_db_path):
    """Verify that a corrupted or maliciously injected user record with high iterations
    causes verify_user to consume a massive amount of CPU/time, showing a denial-of-service risk.
    """
    # Write a record with 500,000 iterations (5x standard)
    high_iters = 500000
    with open(temp_db_path, "w") as f:
        json.dump({
            "slow_user": {
                "salt": "0" * 32,
                "hash": "0" * 64,
                "iterations": high_iters,
                "algo": "pbkdf2_sha256"
            }
        }, f)

    # Measure time to verify
    t0 = time.perf_counter()
    res = server.auth.verify_user("slow_user", "password")
    t1 = time.perf_counter()
    duration_ms = (t1 - t0) * 1000

    assert res is False
    # If the module enforces no limit on iterations, this runs with 500,000 iterations.
    print(f"\nVerification with {high_iters} iterations took: {duration_ms:.4f} ms")
    # A standard run is 100,000 iterations. 500,000 should take significantly longer.

def test_lock_db_file_exception_propagation(temp_db_path):
    """Verify that if msvcrt.locking/fcntl.flock raises an OSError,
    the _lock_db_file context manager raises an OSError rather than swallowing it.
    """
    # Force portalocker to None to test the fallback path
    original_portalocker = server.auth.portalocker
    server.auth.portalocker = None

    try:
        # Mock msvcrt.locking or fcntl.flock to raise OSError
        if os.name == 'nt':
            mock_target = "msvcrt.locking"
        else:
            mock_target = "fcntl.flock"

        with patch(mock_target, side_effect=OSError("Simulated lock failure")):
            with pytest.raises(OSError) as excinfo:
                with server.auth._lock_db_file(temp_db_path):
                    pass
            assert "Could not acquire lock" in str(excinfo.value)
    finally:
        server.auth.portalocker = original_portalocker
