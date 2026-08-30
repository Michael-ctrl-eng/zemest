"""End-to-end tests with Playwright.

These tests drive a real browser against a running server instance to
simulate real user journeys. They are SLOW — only run them when the
server is up and Playwright browsers are installed.

Setup:
    pip install pytest-playwright
    playwright install chromium
    uvicorn app.main:app --port 8000

Run:
    pytest tests/e2e/ -v -m "e2e"
"""
