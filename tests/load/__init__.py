"""Locust load tests.

These tests are NOT run by pytest — they're run by the `locust` CLI:

    locust -f tests/load/locustfile.py --host=http://localhost:8000

Then open http://localhost:8089 to configure number of users and spawn rate.

For headless runs:

    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
        --headless -u 1000 -r 50 --run-time 5m
"""
