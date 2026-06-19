import os
import json
import time
import pytest
import threading
import statistics
import hashlib
import hmac
from unittest.mock import patch
import server.auth

@pytest.fixture
def temp_db_path(tmp_path):
    temp_file = tmp_path / "users.json"
    original_path = server.auth.USER_DB_PATH
    server.auth.USER_DB_PATH = str(temp_file)
    yield str(temp_file)
    server.auth.USER_DB_PATH = original_path

def test_simulated_multiprocess_race(temp_db_path):
    """Simulates two processes running create_user concurrently.
    Even when we bypass _db_lock to simulate independent processes, the file-level lock
    ensures both registrations are processed and no data is lost.
    """
    # Initialize empty DB
    with open(temp_db_path, "w") as f:
        json.dump({}, f)

    # We mock _db_lock with a dummy lock that does nothing, simulating
    # two independent processes that don't share the threading Lock.
    class NoOpLock:
        def __enter__(self): pass
        def __exit__(self, exc_type, exc_val, exc_tb): pass

    original_lock = server.auth._db_lock
    server.auth._db_lock = NoOpLock()

    # Thread 1 registers 'user_a', Thread 2 registers 'user_b'
    # We introduce a delay in _load_users to ensure overlap.
    barrier = threading.Barrier(2)
    original_load = server.auth._load_users

    def delayed_load():
        data = original_load()
        try:
            barrier.wait(timeout=2.0)
        except Exception:
            pass
        return data

    try:
        with patch("server.auth._load_users", side_effect=delayed_load):
            t1 = threading.Thread(target=server.auth.create_user, args=("user_a", "pass_a"))
            t2 = threading.Thread(target=server.auth.create_user, args=("user_b", "pass_b"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        # Read database content
        with open(temp_db_path, "r") as f:
            data = json.load(f)

        # Both registrations must succeed due to file lock synchronization
        assert "user_a" in data and "user_b" in data, "Expected both registrations to succeed due to file locking"
        print("\nRace condition prevented: both concurrent registrations succeeded due to file-level locking!")
    finally:
        server.auth._db_lock = original_lock

def test_verify_user_malformed_iterations(temp_db_path):
    """Verify that verify_user handles malformed iterations gracefully by returning False."""
    # Write a record with string iterations and negative iterations
    with open(temp_db_path, "w") as f:
        json.dump({
            "bad_iterations": {
                "salt": "0" * 32,
                "hash": "0" * 64,
                "iterations": "100000", # string instead of int
                "algo": "pbkdf2_sha256"
            },
            "negative_iterations": {
                "salt": "0" * 32,
                "hash": "0" * 64,
                "iterations": -10, # negative int
                "algo": "pbkdf2_sha256"
            }
        }, f)

    # These should return False and not raise exceptions
    assert server.auth.verify_user("bad_iterations", "password") is False
    assert server.auth.verify_user("negative_iterations", "password") is False

def test_create_user_timing_safety(temp_db_path):
    """Verify that create_user timing is uniform for existing vs non-existing users
    to prevent credential harvesting timing leaks.
    """
    # Create an initial user
    server.auth.create_user("existing_user", "password123")

    # Time registration for an existing user (now performs dummy PBKDF2)
    t0 = time.perf_counter()
    res1 = server.auth.create_user("existing_user", "password123")
    t1 = time.perf_counter()
    time_existing = (t1 - t0) * 1000

    # Time registration for a non-existing user (computes PBKDF2)
    t0 = time.perf_counter()
    res2 = server.auth.create_user("new_user", "password123")
    t1 = time.perf_counter()
    time_new = (t1 - t0) * 1000

    assert res1 is False
    assert res2 is True
    
    diff = abs(time_new - time_existing)
    print(f"\nCreate User (Existing): {time_existing:.4f} ms")
    print(f"Create User (New/Non-Existing): {time_new:.4f} ms")
    print(f"Timing Difference: {diff:.4f} ms")
    
    # The difference should be small because both perform PBKDF2 calculation.
    assert diff < 10.0, f"Significant timing difference detected: {diff:.4f} ms"
