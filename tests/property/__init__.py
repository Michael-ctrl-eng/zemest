"""Property-based tests directory.

These tests use Hypothesis to generate hundreds of random inputs and
verify our validators/parsers never crash on edge cases.

Run independently:
    pytest tests/property/ -v
"""
