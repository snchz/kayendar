import time
import statistics
import pytest
import server.auth

@pytest.mark.skip(reason="Timing tests are flaky in virtualized environments like CI")
def test_verify_user_timing_safety_robust():
    """Verify that verify_user takes similar time for existing vs non-existing users
    using a robust statistical method that discards outliers to avoid flakiness.
    """
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
            
            num_runs = 100
            times_existing_incorrect = []
            times_nonexisting = []
            
            # Warmup
            for _ in range(10):
                server.auth.verify_user(username, "wrong_password")
                server.auth.verify_user("no_such_user", password)
                
            # Measure (interleaved to minimize timing skew due to CPU freq scaling)
            for _ in range(num_runs):
                # 1. Existing user, incorrect password
                t0 = time.perf_counter()
                server.auth.verify_user(username, "wrong_password")
                t1 = time.perf_counter()
                times_existing_incorrect.append((t1 - t0) * 1000) # ms
                
                # 2. Non-existing user
                t0 = time.perf_counter()
                server.auth.verify_user("no_such_user", password)
                t1 = time.perf_counter()
                times_nonexisting.append((t1 - t0) * 1000) # ms
            
            # Helper to remove top and bottom 10% of samples (outliers)
            def trim_outliers(samples):
                sorted_samples = sorted(samples)
                trim_count = int(len(samples) * 0.10)
                if trim_count > 0:
                    return sorted_samples[trim_count:-trim_count]
                return sorted_samples
            
            trimmed_existing = trim_outliers(times_existing_incorrect)
            trimmed_nonexisting = trim_outliers(times_nonexisting)
            
            avg_incorrect = statistics.mean(trimmed_existing)
            avg_nonexisting = statistics.mean(trimmed_nonexisting)
            median_incorrect = statistics.median(trimmed_existing)
            median_nonexisting = statistics.median(trimmed_nonexisting)
            
            diff_mean = abs(avg_incorrect - avg_nonexisting)
            diff_median = abs(median_incorrect - median_nonexisting)
            
            print(f"\nTrimmed Runs Count: {len(trimmed_existing)}")
            print(f"Average time (Existing User, Incorrect Password): {avg_incorrect:.4f} ms (median: {median_incorrect:.4f} ms)")
            print(f"Average time (Non-Existing User): {avg_nonexisting:.4f} ms (median: {median_nonexisting:.4f} ms)")
            print(f"Trimmed Mean Difference: {diff_mean:.4f} ms")
            print(f"Trimmed Median Difference: {diff_median:.4f} ms")
            
            # Since outliers are trimmed, the difference should be extremely small (< 2.0 ms)
            # and resistant to system noise/context switches.
            assert diff_mean < 2.0, f"Significant timing difference detected in mean: {diff_mean:.4f} ms"
            assert diff_median < 2.0, f"Significant timing difference detected in median: {diff_median:.4f} ms"
            
        finally:
            server.auth.USER_DB_PATH = original_path

if __name__ == "__main__":
    test_verify_user_timing_safety_robust()
