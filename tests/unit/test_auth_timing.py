import time
import statistics
import server.auth

def test_verify_user_timing_safety():
    """Verify that verify_user takes similar time for existing vs non-existing users."""
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_file = os.path.join(tmpdir, "users.json")
        original_path = server.auth.USER_DB_PATH
        server.auth.USER_DB_PATH = temp_file
        
        try:
            username = "timing_test_user"
            password = "timing_test_password"
            
            # Ensure user exists
            server.auth.create_user(username, password)
            
            num_runs = 50
            times_existing_incorrect = []
            times_nonexisting = []
            
            # Warmup
            for _ in range(5):
                server.auth.verify_user(username, "wrong_password")
                server.auth.verify_user("no_such_user", password)
                
            # Measure
            for _ in range(num_runs):
                # Existing user, incorrect password
                t0 = time.perf_counter()
                server.auth.verify_user(username, "wrong_password")
                t1 = time.perf_counter()
                times_existing_incorrect.append((t1 - t0) * 1000) # ms
                
                # Non-existing user
                t0 = time.perf_counter()
                server.auth.verify_user("no_such_user", password)
                t1 = time.perf_counter()
                times_nonexisting.append((t1 - t0) * 1000) # ms
                
            avg_incorrect = statistics.mean(times_existing_incorrect)
            avg_nonexisting = statistics.mean(times_nonexisting)
            diff = abs(avg_incorrect - avg_nonexisting)
            
            print(f"\nAverage time (Existing User, Incorrect Password): {avg_incorrect:.4f} ms")
            print(f"Average time (Non-Existing User): {avg_nonexisting:.4f} ms")
            print(f"Timing Difference: {diff:.4f} ms")
            
            # The difference should be extremely small (typically < 0.5 ms locally)
            # compared to the overall PBKDF2 calculation time (~50-100 ms)
            # We assert a conservative threshold of 5 ms to avoid flaky test failures,
            # but the actual difference is usually in microsecond range.
            assert diff < 5.0, f"Significant timing difference detected: {diff:.4f} ms"
        finally:
            server.auth.USER_DB_PATH = original_path

if __name__ == "__main__":
    test_verify_user_timing_safety()
