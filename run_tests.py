#!/usr/bin/env python3
"""
Self-contained test runner for Egyptian Deals & Black Friday Telegram Bot.
Discovers and executes all 4 tiers of tests under `tests/` directory.

Usage:
    python run_tests.py
"""

import sys
import os
import time
import unittest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class PrettyTestResult(unittest.TextTestResult):
    """Custom test result recorder for formatted tier reporting."""
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.successes = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test)


def run_test_suite():
    print("=" * 76)
    print("   Egyptian Deals & Black Friday Telegram Bot (@Deals_egy_bot)")
    print("                 Automated Multi-Tier Test Suite")
    print("=" * 76)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Python interpreter: {sys.executable}")
    print("-" * 76)

    start_time = time.time()

    # Discover tests in tests/ directory
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT)
    )

    test_modules = {
        "tests.test_tier1_models_classifier": "Tier 1: Canonical Models & Category Classifier",
        "tests.test_tier1_scrapers": "Tier 1: Store Scraper Parsing & Direct URLs (9 Stores)",
        "tests.test_tier2_boundary_corner": "Tier 2: Boundary & Corner Cases (Adversarial)",
        "tests.test_tier3_deduplication": "Tier 3: Stateful Deduplication & Decision Matrix",
        "tests.test_tier4_e2e_workflow": "Tier 4: End-to-End Pipeline & Telegram Delivery",
    }

    tier_counts = {k: {"passed": 0, "failed": 0, "errors": 0} for k in test_modules}

    # Run tests
    runner = unittest.TextTestRunner(resultclass=PrettyTestResult, verbosity=1)
    result = runner.run(suite)
    duration = time.time() - start_time

    # Categorize test results by tier
    for test in result.successes:
        mod = test.__class__.__module__
        if mod in tier_counts:
            tier_counts[mod]["passed"] += 1

    for test, err in result.failures:
        mod = test.__class__.__module__
        if mod in tier_counts:
            tier_counts[mod]["failed"] += 1

    for test, err in result.errors:
        mod = test.__class__.__module__
        if mod in tier_counts:
            tier_counts[mod]["errors"] += 1

    print("\n" + "=" * 76)
    print("                         TEST EXECUTION SUMMARY")
    print("=" * 76)
    print(f"{'Test Tier / Module':<56} | {'Pass':<5} | {'Fail':<5}")
    print("-" * 76)

    total_passed = 0
    total_failed = 0
    total_errors = 0

    for mod, label in test_modules.items():
        counts = tier_counts[mod]
        p = counts["passed"]
        f = counts["failed"] + counts["errors"]
        total_passed += p
        total_failed += counts["failed"]
        total_errors += counts["errors"]
        status_flag = "PASS" if f == 0 else "FAIL"
        print(f"{label:<56} | {p:<5} | {f:<5} [{status_flag}]")

    print("-" * 76)
    total_tests = result.testsRun
    print(f"Total Tests Executed: {total_tests}")
    print(f"Passed: {total_passed} | Failures: {total_failed} | Errors: {total_errors}")
    print(f"Total Duration: {duration:.3f} seconds")
    print("=" * 76)

    if result.wasSuccessful():
        print(">>> ALL TESTS PASSED SUCCESSFULLY (Exit Code 0) <<<")
        return 0
    else:
        print(">>> TEST SUITE CONTAINED FAILURES (Exit Code 1) <<<")
        return 1


if __name__ == "__main__":
    exit_code = run_test_suite()
    sys.exit(exit_code)
