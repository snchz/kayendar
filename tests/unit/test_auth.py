import os
import json
import hashlib
import threading
import pytest
from unittest.mock import patch

import server.auth

@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Fixture to isolate the user database file for each test."""
    temp_file = tmp_path / "users.json"
    original_path = server.auth.USER_DB_PATH
    server.auth.USER_DB_PATH = str(temp_file)
    
    yield temp_file
    
    # Restore the original path
    server.auth.USER_DB_PATH = original_path

def test_create_user_success(temp_db):
    """Test successful user creation."""
    res = server.auth.create_user("john_doe", "secret123")
    assert res is True
    
    # Verify file exists and has correct data structure
    assert os.path.exists(temp_db)
    with open(temp_db, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert "john_doe" in data
    user_data = data["john_doe"]
    assert user_data["algo"] == "pbkdf2_sha256"
    assert user_data["iterations"] == 100000
    assert len(user_data["salt"]) == 32  # 16 bytes hex-encoded
    assert len(user_data["hash"]) == 64  # sha256 hex-encoded

def test_create_user_duplicate(temp_db):
    """Test that duplicate user creation returns False and doesn't overwrite."""
    res1 = server.auth.create_user("john_doe", "secret123")
    assert res1 is True
    
    res2 = server.auth.create_user("john_doe", "different_pass")
    assert res2 is False
    
    # Verify the first password is still the valid one
    assert server.auth.verify_user("john_doe", "secret123") is True
    assert server.auth.verify_user("john_doe", "different_pass") is False

def test_create_user_invalid_inputs():
    """Test that create_user raises ValueError on invalid inputs."""
    invalid_cases = [
        (None, "password"),
        ("user", None),
        (123, "password"),
        ("user", 123),
        ("", "password"),
        ("user", ""),
        ("   ", "password"),
        ("user", "   "),
    ]
    for username, password in invalid_cases:
        with pytest.raises(ValueError):
            server.auth.create_user(username, password)

def test_correct_hashes(temp_db):
    """Test that hashes stored in the database are correct pbkdf2_sha256 hashes."""
    username = "hash_test"
    password = "correct_password"
    
    assert server.auth.create_user(username, password) is True
    
    with open(temp_db, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    user_data = data[username]
    salt_bytes = bytes.fromhex(user_data["salt"])
    stored_hash = user_data["hash"]
    
    expected_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        100000
    ).hex()
    
    assert stored_hash == expected_hash

def test_verify_user_success(temp_db):
    """Test that verify_user succeeds with correct credentials."""
    server.auth.create_user("john_doe", "secret123")
    assert server.auth.verify_user("john_doe", "secret123") is True

def test_verify_user_incorrect_password(temp_db):
    """Test that verify_user fails with incorrect password."""
    server.auth.create_user("john_doe", "secret123")
    assert server.auth.verify_user("john_doe", "wrongpassword") is False

def test_verify_user_nonexistent_user(temp_db):
    """Test that verify_user fails for non-existent users."""
    assert server.auth.verify_user("nonexistent", "any_password") is False

def test_verify_user_invalid_inputs():
    """Test that verify_user raises ValueError on invalid inputs."""
    invalid_cases = [
        (None, "password"),
        ("user", None),
        (123, "password"),
        ("user", 123),
        ("", "password"),
        ("user", ""),
        ("   ", "password"),
        ("user", "   "),
    ]
    for username, password in invalid_cases:
        with pytest.raises(ValueError):
            server.auth.verify_user(username, password)

def test_timing_safety_dummy_code_path(temp_db):
    """Test that verify_user runs dummy PBKDF2 calculation for non-existent users."""
    # Ensure database is empty, user definitely doesn't exist
    with patch("hashlib.pbkdf2_hmac", wraps=hashlib.pbkdf2_hmac) as mock_pbkdf2:
        res = server.auth.verify_user("nonexistent", "dummy_pass")
        assert res is False
        # Should be called once with dummy values
        mock_pbkdf2.assert_called_once_with(
            "sha256",
            b"dummy_pass",
            b"\x00" * 16,
            100000
        )

def test_verify_user_existing_calls_pbkdf2_with_correct_args(temp_db):
    """Test that verify_user runs PBKDF2 with correct stored args for existing users."""
    username = "real_user"
    password = "real_password"
    server.auth.create_user(username, password)
    
    with open(temp_db, "r", encoding="utf-8") as f:
        data = json.load(f)
    salt_bytes = bytes.fromhex(data[username]["salt"])
    
    with patch("hashlib.pbkdf2_hmac", wraps=hashlib.pbkdf2_hmac) as mock_pbkdf2:
        res = server.auth.verify_user(username, password)
        assert res is True
        mock_pbkdf2.assert_called_once_with(
            "sha256",
            password.encode("utf-8"),
            salt_bytes,
            100000
        )

def test_verify_user_corrupt_db_records(temp_db):
    """Test that verify_user handles corrupt JSON db entries gracefully by returning False."""
    with open(temp_db, "w", encoding="utf-8") as f:
        json.dump({
            "corrupt_salt": {
                "salt": "invalid-hex-characters-!",
                "hash": "0" * 64,
                "iterations": 100000,
                "algo": "pbkdf2_sha256"
            },
            "missing_fields": {
                "iterations": 100000
            }
        }, f)
        
    assert server.auth.verify_user("corrupt_salt", "password") is False
    assert server.auth.verify_user("missing_fields", "password") is False

def test_thread_safety_create_users(temp_db):
    """Stress test user creation and verification with concurrent threads."""
    threads = []
    errors = []
    num_threads = 20
    
    def worker(i):
        try:
            username = f"user_{i}"
            password = f"pass_{i}"
            res = server.auth.create_user(username, password)
            assert res is True
            assert server.auth.verify_user(username, password) is True
        except Exception as e:
            errors.append(e)
            
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    assert len(errors) == 0, f"Thread errors occurred: {errors}"
    
    with open(temp_db, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert len(data) == num_threads
    for i in range(num_threads):
        assert f"user_{i}" in data

def test_load_corrupt_invalid_json_raises_error(temp_db):
    """Verify that trying to authenticate/create user when the JSON file
    contains corrupt/invalid JSON raises a json.JSONDecodeError or ValueError
    rather than overwriting the DB.
    """
    with open(temp_db, "w", encoding="utf-8") as f:
        f.write("{invalid json: no quotes around key, missing comma")
    
    # Verify raises json.JSONDecodeError or ValueError on create_user
    with pytest.raises((json.JSONDecodeError, ValueError)):
        server.auth.create_user("new_user", "password")
        
    # Verify raises json.JSONDecodeError or ValueError on verify_user
    with pytest.raises((json.JSONDecodeError, ValueError)):
        server.auth.verify_user("new_user", "password")
        
    # Make sure DB was NOT overwritten with empty dictionary
    with open(temp_db, "r", encoding="utf-8") as f:
        content = f.read()
    assert content.strip() == "{invalid json: no quotes around key, missing comma"

def test_load_malformed_type_db_raises_clean_exception(temp_db):
    """Verify that when the database is a malformed type (e.g., a JSON list or string
    instead of a dictionary), functions handle it gracefully or raise a clean exception (ValueError).
    """
    # Test with a JSON list
    with open(temp_db, "w", encoding="utf-8") as f:
        json.dump(["user1", "user2"], f)
        
    with pytest.raises(ValueError) as excinfo:
        server.auth.create_user("new_user", "password")
    assert "Database root must be a dictionary" in str(excinfo.value)
    
    with pytest.raises(ValueError) as excinfo:
        server.auth.verify_user("new_user", "password")
    assert "Database root must be a dictionary" in str(excinfo.value)
    
    # Test with a JSON string
    with open(temp_db, "w", encoding="utf-8") as f:
        json.dump("just a string", f)
        
    with pytest.raises(ValueError) as excinfo:
        server.auth.create_user("new_user", "password")
    assert "Database root must be a dictionary" in str(excinfo.value)
    
    with pytest.raises(ValueError) as excinfo:
        server.auth.verify_user("new_user", "password")
    assert "Database root must be a dictionary" in str(excinfo.value)

def test_verify_user_malformed_user_record_handled_gracefully(temp_db):
    """Verify that when a user record is not a dictionary, verify_user handles it
    gracefully (returning False via dummy verification) without throwing AttributeError or TypeError.
    """
    with open(temp_db, "w", encoding="utf-8") as f:
        json.dump({
            "string_record": "not a dictionary",
            "list_record": ["still not a dictionary"],
            "none_record": None
        }, f)
        
    # verify_user should return False and not raise AttributeError/TypeError
    assert server.auth.verify_user("string_record", "password") is False
    assert server.auth.verify_user("list_record", "password") is False
    assert server.auth.verify_user("none_record", "password") is False

def test_dynamic_kayendar_data_dir_resolution(tmp_path, monkeypatch):
    """Verify that KAYENDAR_DATA_DIR changes dynamically modify the path used by
    _load_users / _save_users without needing to reload the module.
    """
    import server.auth
    
    # Save original USER_DB_PATH and set to None to force dynamic path resolution
    original_db_path = server.auth.USER_DB_PATH
    server.auth.USER_DB_PATH = None
    
    try:
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        
        # Test 1: Set to dir1
        monkeypatch.setenv("KAYENDAR_DATA_DIR", str(dir1))
        assert server.auth._get_db_path() == os.path.join(str(dir1), "users.json")
        
        res1 = server.auth.create_user("user_in_dir1", "pass123")
        assert res1 is True
        
        # Check that the file was created in dir1
        file1 = dir1 / "users.json"
        assert file1.exists()
        with open(file1, "r", encoding="utf-8") as f:
            data1 = json.load(f)
        assert "user_in_dir1" in data1
        
        # Test 2: Set to dir2 (change environment dynamically)
        monkeypatch.setenv("KAYENDAR_DATA_DIR", str(dir2))
        assert server.auth._get_db_path() == os.path.join(str(dir2), "users.json")
        
        res2 = server.auth.create_user("user_in_dir2", "pass456")
        assert res2 is True
        
        # Check that the file was created in dir2
        file2 = dir2 / "users.json"
        assert file2.exists()
        with open(file2, "r", encoding="utf-8") as f:
            data2 = json.load(f)
        assert "user_in_dir2" in data2
        
        # Verify that dir1's file does NOT contain the new user (no cross-contamination)
        with open(file1, "r", encoding="utf-8") as f:
            data1_again = json.load(f)
        assert "user_in_dir2" not in data1_again
        
    finally:
        # Restore the original USER_DB_PATH
        server.auth.USER_DB_PATH = original_db_path


def test_create_user_duplicate_does_compute_dummy_hash(temp_db):
    """Verify that calling create_user for an existing user performs a dummy PBKDF2 hash."""
    # First, create the user
    assert server.auth.create_user("existing_user", "password123") is True
    
    # Now, attempt to create the user again, mocking pbkdf2_hmac to assert it is called once
    with patch("hashlib.pbkdf2_hmac") as mock_pbkdf2:
        res = server.auth.create_user("existing_user", "different_password")
        assert res is False
        mock_pbkdf2.assert_called_once()


def test_create_user_race_condition(temp_db):
    """Verify that if another thread creates the user while PBKDF2 is running,
    create_user detects it in the second check and returns False.
    """
    username = "race_user"
    password = "password123"
    
    # We mock pbkdf2_hmac. Its side effect will be to write the user directly to the DB
    # (simulating another thread registering the user in the meantime)
    # and then return a dummy hash.
    original_pbkdf2 = hashlib.pbkdf2_hmac
    
    def side_effect(*args, **kwargs):
        # Write the user to DB directly (bypassing create_user lock because we are not in it)
        with server.auth._db_lock:
            with server.auth._lock_db_file(server.auth._get_db_path()):
                users = server.auth._load_users()
                users[username] = {
                    "salt": "dummysalt",
                    "hash": "dummyhash",
                    "iterations": 100000,
                    "algo": "pbkdf2_sha256"
                }
                server.auth._save_users(users)
        return original_pbkdf2(*args, **kwargs)
        
    with patch("hashlib.pbkdf2_hmac", side_effect=side_effect):
        res = server.auth.create_user(username, password)
        # It should return False because of the race condition check
        assert res is False


def test_username_validation(temp_db):
    """Test valid and invalid usernames."""
    # Valid usernames: alphanumeric, dots, underscores, dashes, @ symbols
    valid_usernames = ["john.doe", "john_doe", "john-doe", "john@doe", "john123", "j.o_h-n@1"]
    for u in valid_usernames:
        assert server.auth.create_user(u, "password123") is True
        assert server.auth.verify_user(u, "password123") is True
        
    # Invalid usernames: contains characters outside the allowed set, or path traversal
    invalid_usernames = [
        "john/doe", "john\\doe", "john..doe", "john/../doe",
        "john$", "john#", "john!", "john%", "john&", "john*", "john(",
        " john", "john ", " john ", " "
    ]
    for u in invalid_usernames:
        with pytest.raises(ValueError):
            server.auth.create_user(u, "password123")
        with pytest.raises(ValueError):
            server.auth.verify_user(u, "password123")


def test_password_length_limit(temp_db):
    """Test that passwords longer than 256 characters are rejected with ValueError."""
    username = "limit_test_user"
    too_long_password = "p" * 257
    just_right_password = "p" * 256
    
    # 256 characters should be accepted
    assert server.auth.create_user(username, just_right_password) is True
    assert server.auth.verify_user(username, just_right_password) is True
    
    # 257 characters should raise ValueError
    with pytest.raises(ValueError):
        server.auth.create_user("limit_user_2", too_long_password)
    with pytest.raises(ValueError):
        server.auth.verify_user(username, too_long_password)


def test_username_length_limit(temp_db):
    """Test that usernames longer than 128 characters are rejected with ValueError."""
    too_long_username = "u" * 129
    limit_username = "u" * 128
    
    # 128 characters should be accepted
    assert server.auth.create_user(limit_username, "password123") is True
    assert server.auth.verify_user(limit_username, "password123") is True
    
    # 129 characters should raise ValueError
    with pytest.raises(ValueError):
        server.auth.create_user(too_long_username, "password123")
    with pytest.raises(ValueError):
        server.auth.verify_user(too_long_username, "password123")


def test_windows_reserved_usernames(temp_db):
    """Test that Windows reserved names (CON, PRN, AUX, NUL, COM1-COM9, LPT1-LPT9) are rejected case-insensitively."""
    reserved_names = [
        "CON", "PRN", "AUX", "NUL",
        "com1", "com9", "lpt1", "lpt9",
        "Con", "Prn", "Aux", "Nul",
        "CON.txt", "prn.vcf", "COM1.tar.gz",
        "con.TXT", "PRN.Vcf", "Com1.Tar.Gz",
        "AUX.json", "Nul.zip", "lpt9.log",
        "con .txt", "AUX .json", " COM1.tar.gz"
    ]
    for rname in reserved_names:
        with pytest.raises(ValueError):
            server.auth.create_user(rname, "password123")
        with pytest.raises(ValueError):
            server.auth.verify_user(rname, "password123")


def test_verify_user_high_iterations_dummy_routing(temp_db):
    """Verify that a user record with >100000 iterations is treated as malformed,
    routing to the dummy timing path and running with 100,000 iterations to prevent CPU DoS.
    """
    # Write a record with 150,000 iterations
    with open(temp_db, "w", encoding="utf-8") as f:
        json.dump({
            "dos_user": {
                "salt": "a" * 32,
                "hash": "b" * 64,
                "iterations": 150000,
                "algo": "pbkdf2_sha256"
            }
        }, f)
        
    with patch("hashlib.pbkdf2_hmac", wraps=hashlib.pbkdf2_hmac) as mock_pbkdf2:
        res = server.auth.verify_user("dos_user", "password123")
        assert res is False
        # Should be routed to dummy timing path with 100,000 iterations
        mock_pbkdf2.assert_called_once_with(
            "sha256",
            b"password123",
            b"\x00" * 16,
            100000
        )


def test_lock_db_file_exception_propagation_to_caller(temp_db):
    """Verify that exceptions raised within the caller block of _lock_db_file propagate normally
    and do not get swallowed by the context manager.
    """
    class CustomCallerException(Exception):
        pass

    with pytest.raises(CustomCallerException):
        with server.auth._lock_db_file(str(temp_db)):
            raise CustomCallerException("Exception in caller")


