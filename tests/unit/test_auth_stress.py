import time
import threading
import statistics
import tempfile
import os
import json
import pytest
import server.auth

def test_verify_user_timing_safety_large_db():
    """Verify timing safety under a larger database to ensure lookup/parsing
    does not introduce significant timing asymmetry.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_file = os.path.join(tmpdir, "users.json")
        original_path = server.auth.USER_DB_PATH
        server.auth.USER_DB_PATH = temp_file
        
        try:
            # Populate DB with 200 dummy users to simulate a larger database
            users = {}
            for i in range(200):
                users[f"dummy_user_{i}"] = {
                    "salt": "a" * 32,
                    "hash": "b" * 64,
                    "iterations": 100000,
                    "algo": "pbkdf2_sha256"
                }
            
            # Add one real user for testing
            username = "real_test_user"
            password = "secure_password"
            
            # Write to file
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=4)
                
            # Create user properly (which will update the DB)
            server.auth.create_user(username, password)
            
            num_runs = 30
            times_existing_incorrect = []
            times_nonexisting = []
            
            # Warmup
            for _ in range(5):
                server.auth.verify_user(username, "wrong_password")
                server.auth.verify_user("nonexistent_user", password)
                
            # Measure
            for _ in range(num_runs):
                # Existing user, incorrect password
                t0 = time.perf_counter()
                server.auth.verify_user(username, "wrong_password")
                t1 = time.perf_counter()
                times_existing_incorrect.append((t1 - t0) * 1000) # ms
                
                # Non-existing user
                t0 = time.perf_counter()
                server.auth.verify_user("nonexistent_user", password)
                t1 = time.perf_counter()
                times_nonexisting.append((t1 - t0) * 1000) # ms
                
            avg_incorrect = statistics.mean(times_existing_incorrect)
            avg_nonexisting = statistics.mean(times_nonexisting)
            diff = abs(avg_incorrect - avg_nonexisting)
            
            print(f"\n[Large DB] Average time (Existing User, Incorrect Password): {avg_incorrect:.4f} ms")
            print(f"[Large DB] Average time (Non-Existing User): {avg_nonexisting:.4f} ms")
            print(f"[Large DB] Timing Difference: {diff:.4f} ms")
            
            # Threshold: 5.0 ms
            assert diff < 5.0, f"Significant timing difference detected on larger DB: {diff:.4f} ms"
        finally:
            server.auth.USER_DB_PATH = original_path

def test_auth_concurrency_stress():
    """Verify that concurrent authentications and creations do not deadlock
    or corrupt database structure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_file = os.path.join(tmpdir, "users.json")
        original_path = server.auth.USER_DB_PATH
        server.auth.USER_DB_PATH = temp_file
        
        try:
            num_threads = 30
            threads = []
            errors = []
            
            # Pre-create half the users
            for i in range(num_threads // 2):
                server.auth.create_user(f"user_{i}", f"password_{i}")
                
            def run_stress(thread_id):
                try:
                    # Alternating read/write operations to stress-test locks
                    if thread_id % 2 == 0:
                        # Write path
                        username = f"user_{thread_id}"
                        password = f"password_{thread_id}"
                        res = server.auth.create_user(username, password)
                        assert res is True
                        assert server.auth.verify_user(username, password) is True
                    else:
                        # Read path (existing and non-existing)
                        existing_user = f"user_{thread_id % (num_threads // 2)}"
                        existing_pass = f"password_{thread_id % (num_threads // 2)}"
                        assert server.auth.verify_user(existing_user, existing_pass) is True
                        assert server.auth.verify_user(existing_user, "wrong_pass") is False
                        assert server.auth.verify_user(f"nonexistent_{thread_id}", "pass") is False
                except Exception as e:
                    errors.append((thread_id, e))
                    
            for i in range(num_threads):
                t = threading.Thread(target=run_stress, args=(i,))
                threads.append(t)
                t.start()
                
            for t in threads:
                t.join()
                
            assert len(errors) == 0, f"Concurrency errors occurred: {errors}"
            
            # Verify DB size
            with open(temp_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Pre-created users (15) + new even users (15) = 30 unique users
            expected_count = (num_threads // 2) + (num_threads - num_threads // 2)
            assert len(data) == expected_count, f"Expected {expected_count} users, got {len(data)}"
        finally:
            server.auth.USER_DB_PATH = original_path

def test_verify_user_extremely_long_password():
    """Verify that verify_user rejects extremely long passwords (>256 chars) with ValueError,
    and handles passwords at the limit (256 chars) correctly and with timing safety.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_file = os.path.join(tmpdir, "users.json")
        original_path = server.auth.USER_DB_PATH
        server.auth.USER_DB_PATH = temp_file
        
        try:
            username = "long_pwd_user"
            # 1 MB password
            extremely_long_password = "a" * 1000000
            
            # Creation should raise ValueError
            with pytest.raises(ValueError):
                server.auth.create_user(username, extremely_long_password)
                
            # Verification should raise ValueError
            with pytest.raises(ValueError):
                server.auth.verify_user(username, extremely_long_password)
                
            # Passwords at the limit (256 characters) should be handled correctly
            limit_password = "a" * 256
            res = server.auth.create_user(username, limit_password)
            assert res is True
            
            # Verification - Correct password
            t0 = time.perf_counter()
            assert server.auth.verify_user(username, limit_password) is True
            t1 = time.perf_counter()
            time_correct = (t1 - t0) * 1000
            
            # Verification - Incorrect password of length 256
            wrong_limit_password = "b" * 256
            t0 = time.perf_counter()
            assert server.auth.verify_user(username, wrong_limit_password) is False
            t1 = time.perf_counter()
            time_incorrect_existing = (t1 - t0) * 1000
            
            # Verification - Non-existent user with password of length 256
            t0 = time.perf_counter()
            assert server.auth.verify_user("nonexistent_user", limit_password) is False
            t1 = time.perf_counter()
            time_nonexistent = (t1 - t0) * 1000
            
            print(f"\n[Limit Password 256 Chars] Correct: {time_correct:.4f} ms")
            print(f"[Limit Password 256 Chars] Incorrect Existing: {time_incorrect_existing:.4f} ms")
            print(f"[Limit Password 256 Chars] Non-existent: {time_nonexistent:.4f} ms")
            
            # Assert timing difference between incorrect existing and non-existent is small
            diff = abs(time_incorrect_existing - time_nonexistent)
            assert diff < 10.0, f"Significant timing difference with limit password: {diff:.4f} ms"
        finally:
            server.auth.USER_DB_PATH = original_path
