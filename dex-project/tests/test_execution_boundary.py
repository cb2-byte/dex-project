"""
Tests for Execution Boundary
=============================
Tests that paper mode cannot load keys, call live functions, or import live modules.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
from paper_engine.boundaries import (
    ExecutionBoundary,
    get_boundary,
    set_paper_mode,
    paper_only,
    assert_paper_mode,
    FORBIDDEN_PATTERNS,
    FORBIDDEN_IMPORTS,
    ALLOWED_READONLY_IMPORTS,
)
from paper_engine.config import PaperConfig


class TestExecutionBoundary:
    """Test the ExecutionBoundary class."""

    @pytest.fixture
    def boundary(self):
        return ExecutionBoundary(paper_mode=True)

    def test_paper_mode_enabled(self, boundary):
        """Boundary should be in paper mode."""
        assert boundary.paper_mode is True

    def test_assert_paper_mode_passes_in_paper_mode(self, boundary):
        """assert_paper_mode should pass in paper mode."""
        boundary.assert_paper_mode("test caller")

    def test_assert_paper_mode_raises_in_live_mode(self):
        """assert_paper_mode should raise in live mode."""
        live_boundary = ExecutionBoundary(paper_mode=False)
        with pytest.raises(RuntimeError, match="LIVE EXECUTION ATTEMPT BLOCKED"):
            live_boundary.assert_paper_mode("test caller")

    def test_scan_for_keys_detects_private_key(self, boundary):
        """Should detect private key in string."""
        obj = "private_key=0x123..."
        findings = boundary.scan_for_keys(obj)
        assert len(findings) > 0
        assert any("private_key" in f for f in findings)

    def test_scan_for_keys_detects_mnemonic(self, boundary):
        """Should detect mnemonic phrase."""
        obj = {"wallet": {"mnemonic": "word1 word2 word3..."}}
        findings = boundary.scan_for_keys(obj)
        assert len(findings) > 0
        assert any("mnemonic" in f for f in findings)

    def test_scan_for_keys_detects_sign_transaction(self, boundary):
        """Should detect sign_transaction pattern."""
        obj = "def sign_transaction(tx): ..."
        findings = boundary.scan_for_keys(obj)
        assert len(findings) > 0
        assert any("sign_transaction" in f for f in findings)

    def test_scan_for_keys_detects_create_and_post_order(self, boundary):
        """Should detect create_and_post_order pattern."""
        obj = "client.create_and_post_order(params)"
        findings = boundary.scan_for_keys(obj)
        assert len(findings) > 0
        assert any("create_and_post_order" in f for f in findings)

    def test_scan_for_keys_recursive_dict(self, boundary):
        """Should scan nested dicts recursively."""
        obj = {
            "config": {
                "api": {
                    "private_key": "0xabc..."
                }
            }
        }
        findings = boundary.scan_for_keys(obj)
        assert len(findings) > 0
        assert any("private_key" in f for f in findings)

    def test_scan_for_keys_recursive_list(self, boundary):
        """Should scan lists recursively."""
        obj = ["normal", "private_key=0x123"]
        findings = boundary.scan_for_keys(obj)
        assert len(findings) > 0

    def test_guard_function_blocks_key_in_args(self, boundary):
        """Guarded function should block if args contain keys."""
        @boundary.guard_function
        def test_func(arg):
            return arg

        with pytest.raises(RuntimeError, match="KEY MATERIAL DETECTED"):
            test_func("private_key=0x123")

    def test_guard_function_blocks_key_in_kwargs(self, boundary):
        """Guarded function should block if kwargs contain keys."""
        @boundary.guard_function
        def test_func(param=None):
            return param

        with pytest.raises(RuntimeError, match="KEY MATERIAL DETECTED"):
            test_func(param="mnemonic=word1 word2")

    def test_guard_function_allows_clean_args(self, boundary):
        """Guarded function should allow clean arguments."""
        @boundary.guard_function
        def test_func(arg):
            return arg * 2

        result = test_func("clean_string")
        assert result == "clean_stringclean_string"

    def test_validate_no_live_imports(self, boundary):
        """Should detect forbidden imports in sys.modules."""
        # Add a mock forbidden module
        sys.modules['py_clob_client'] = MagicMock()
        try:
            violations = boundary.validate_no_live_imports()
            assert 'py_clob_client' in violations
        finally:
            del sys.modules['py_clob_client']

    def test_validate_no_live_imports_allows_readonly(self, boundary):
        """Should allow read-only imports like web3.eth."""
        sys.modules['web3.eth'] = MagicMock()
        try:
            violations = boundary.validate_no_live_imports()
            # web3.eth is in ALLOWED_READONLY_IMPORTS
            assert 'web3.eth' not in violations
        finally:
            del sys.modules['web3.eth']


class TestPaperOnlyDecorator:
    """Test the paper_only decorator."""

    def test_paper_only_allows_in_paper_mode(self):
        """paper_only should allow execution in paper mode."""
        set_paper_mode(True)
        boundary = get_boundary()

        @paper_only
        def test_func():
            return "ok"

        result = test_func()
        assert result == "ok"

    def test_paper_only_blocks_in_live_mode(self):
        """paper_only should block in live mode."""
        set_paper_mode(False)
        boundary = get_boundary()

        @paper_only
        def test_func():
            return "ok"

        with pytest.raises(RuntimeError, match="LIVE EXECUTION ATTEMPT BLOCKED"):
            test_func()

        # Restore paper mode for other tests
        set_paper_mode(True)


class TestAssertPaperMode:
    """Test assert_paper_mode function."""

    def test_assert_paper_mode_passes(self):
        """Should pass in paper mode."""
        set_paper_mode(True)
        assert_paper_mode("test")  # Should not raise

    def test_assert_paper_mode_raises(self):
        """Should raise in live mode."""
        set_paper_mode(False)
        with pytest.raises(RuntimeError):
            assert_paper_mode("test")
        set_paper_mode(True)


class TestForbiddenPatterns:
    """Test that forbidden patterns are comprehensive."""

    def test_forbidden_patterns_include_key_patterns(self):
        """Should include key-related patterns."""
        assert "private_key" in FORBIDDEN_PATTERNS
        assert "mnemonic" in FORBIDDEN_PATTERNS
        assert "keystore" in FORBIDDEN_PATTERNS

    def test_forbidden_patterns_include_execution_patterns(self):
        """Should include order execution patterns."""
        assert "create_and_post_order" in FORBIDDEN_PATTERNS
        assert "send_transaction" in FORBIDDEN_PATTERNS
        assert "sign_transaction" in FORBIDDEN_PATTERNS

    def test_forbidden_patterns_include_client_imports(self):
        """Should include exchange client patterns."""
        assert "py_clob_client" in FORBIDDEN_PATTERNS
        assert "coinbase" in FORBIDDEN_PATTERNS
        assert "krakenex" in FORBIDDEN_PATTERNS
        assert "ccxt" in FORBIDDEN_PATTERNS

    def test_forbidden_imports_include_dangerous_modules(self):
        """Forbidden imports should include dangerous modules."""
        assert "eth_account" in FORBIDDEN_IMPORTS
        assert "py_clob_client" in FORBIDDEN_IMPORTS
        assert "coinbase.wallet" in FORBIDDEN_IMPORTS
        assert "ccxt" in FORBIDDEN_IMPORTS

    def test_allowed_readonly_includes_safe_modules(self):
        """Allowed imports should include safe read-only modules."""
        assert "web3" in ALLOWED_READONLY_IMPORTS
        assert "requests" in ALLOWED_READONLY_IMPORTS
        assert "json" in ALLOWED_READONLY_IMPORTS


class TestBoundarySingleton:
    """Test global boundary singleton behavior."""

    def test_get_boundary_returns_same_instance(self):
        """get_boundary should return same instance."""
        set_paper_mode(True)
        b1 = get_boundary()
        b2 = get_boundary()
        assert b1 is b2

    def test_set_paper_mode_creates_new_instance(self):
        """set_paper_mode should create new instance when mode changes."""
        set_paper_mode(True)
        b1 = get_boundary()
        set_paper_mode(False)
        b2 = get_boundary()
        assert b1 is not b2
        assert b2.paper_mode is False
        set_paper_mode(True)  # Restore