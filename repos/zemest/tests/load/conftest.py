"""Shared configuration for load tests.

Provides environment-variable-driven settings so the same locustfile
can target different environments (local, staging, prod).
"""
import os

# Base URL of the server under test.
TARGET_HOST = os.getenv("LOCUST_HOST", "http://localhost:8000")

# Default credentials for the load-test merchant account.
# These must be provisioned on the target environment BEFORE running load tests.
LOAD_TEST_EMAIL = os.getenv("LOAD_TEST_EMAIL", "loadtest@zemest.test")
LOAD_TEST_PASSWORD = os.getenv("LOAD_TEST_PASSWORD", "LoadTest123!")

# Tenant ID to exercise (must be owned by LOAD_TEST_EMAIL).
LOAD_TEST_TENANT_ID = os.getenv("LOAD_TEST_TENANT_ID", "")

# Spawn rate (users per second).
DEFAULT_SPAWN_RATE = int(os.getenv("LOCUST_SPAWN_RATE", "10"))

# Total users to simulate.
DEFAULT_USERS = int(os.getenv("LOCUST_USERS", "100"))
