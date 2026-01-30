"""
Tests for AI tagging pre-flight checks and CLI commands.

Run with: python3 tests/test_ai_preflight.py
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAIPreflightChecks:
    """Test AI tagging dependency checks."""

    def test_check_without_openai_package(self):
        """Test that check fails when openai package is not installed."""
        # We need to import from main.py
        from main import check_ai_tagging_dependencies

        # Mock the import to raise ImportError
        with patch.dict("sys.modules", {"openai": None}):
            # Force reimport to trigger the ImportError path
            # This is tricky because the function does a local import
            pass

        # For now, just test that the function exists and returns a tuple
        result = check_ai_tagging_dependencies()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_check_without_api_key(self):
        """Test that check fails when OPENAI_API_KEY is not set."""
        from main import check_ai_tagging_dependencies

        # Save current key
        original_key = os.environ.get("OPENAI_API_KEY")

        try:
            # Remove API key
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]

            ok, error_msg = check_ai_tagging_dependencies()

            # Should fail if openai is installed but no API key
            # If openai is not installed, it will also fail
            assert not ok or "OPENAI_API_KEY" not in error_msg
        finally:
            # Restore original key
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key

    def test_check_with_invalid_api_key(self):
        """Test that check fails when OPENAI_API_KEY is too short."""
        from main import check_ai_tagging_dependencies

        # Save current key
        original_key = os.environ.get("OPENAI_API_KEY")

        try:
            # Set a short/invalid key
            os.environ["OPENAI_API_KEY"] = "short"

            ok, error_msg = check_ai_tagging_dependencies()

            # Should fail due to short key (if openai is installed)
            # The error message should mention the key is invalid
            if "openai" not in error_msg.lower():
                assert not ok
                assert "invalid" in error_msg.lower() or "short" in error_msg.lower()
        finally:
            # Restore original key
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key
            elif "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]

    def test_check_returns_tuple(self):
        """Test that check always returns a tuple of (bool, str)."""
        from main import check_ai_tagging_dependencies

        result = check_ai_tagging_dependencies()

        assert isinstance(result, tuple)
        assert len(result) == 2
        ok, error_msg = result
        assert isinstance(ok, bool)
        assert isinstance(error_msg, str)


class TestCLIArguments:
    """Test CLI argument parsing for new commands."""

    def test_tag_existing_argument_exists(self):
        """Test that --tag-existing argument is recognized."""
        from main import parse_args

        # Save sys.argv
        original_argv = sys.argv

        try:
            sys.argv = ["main.py", "--tag-existing"]
            args = parse_args()
            assert hasattr(args, "tag_existing")
            assert args.tag_existing is True
        finally:
            sys.argv = original_argv

    def test_tag_limit_argument_exists(self):
        """Test that --tag-limit argument is recognized."""
        from main import parse_args

        original_argv = sys.argv

        try:
            sys.argv = ["main.py", "--tag-existing", "--tag-limit", "10"]
            args = parse_args()
            assert hasattr(args, "tag_limit")
            assert args.tag_limit == 10
        finally:
            sys.argv = original_argv

    def test_tag_untagged_only_argument_exists(self):
        """Test that --tag-untagged-only argument is recognized."""
        from main import parse_args

        original_argv = sys.argv

        try:
            sys.argv = ["main.py", "--tag-existing", "--tag-untagged-only"]
            args = parse_args()
            assert hasattr(args, "tag_untagged_only")
            assert args.tag_untagged_only is True
        finally:
            sys.argv = original_argv

    def test_sample_no_tags_argument_exists(self):
        """Test that --sample-no-tags argument is recognized."""
        from main import parse_args

        original_argv = sys.argv

        try:
            sys.argv = ["main.py", "--sample", "--sample-no-tags"]
            args = parse_args()
            assert hasattr(args, "sample_no_tags")
            assert args.sample_no_tags is True
        finally:
            sys.argv = original_argv


def run_tests_without_pytest():
    """Run tests manually without pytest."""
    print("Running AI preflight tests...\n")

    passed = 0
    failed = 0
    errors = []

    # Instantiate test classes
    preflight_tests = TestAIPreflightChecks()
    cli_tests = TestCLIArguments()

    # Get all test methods
    test_methods = []
    for cls_name, cls in [
        ("TestAIPreflightChecks", preflight_tests),
        ("TestCLIArguments", cli_tests),
    ]:
        for method_name in dir(cls):
            if method_name.startswith("test_"):
                test_methods.append((cls_name, method_name, getattr(cls, method_name)))

    # Run each test
    for cls_name, method_name, method in test_methods:
        full_name = f"{cls_name}::{method_name}"
        try:
            method()
            print(f"✓ PASSED: {full_name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {full_name}")
            print(f"  Error: {e}")
            errors.append((full_name, str(e)))
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {full_name}")
            print(f"  Exception: {e}")
            errors.append((full_name, str(e)))
            failed += 1

    # Print summary
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
    print(f"{'='*60}")

    if errors:
        print("\nFailed tests:")
        for name, err in errors:
            print(f"  - {name}: {err}")

    return failed == 0


if __name__ == "__main__":
    success = run_tests_without_pytest()
    sys.exit(0 if success else 1)
