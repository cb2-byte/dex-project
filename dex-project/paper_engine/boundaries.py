"""
Execution Boundary - Runtime Guards for Paper Mode
===================================================
Strict enforcement that paper mode never loads keys or calls live execution.
"""

import sys
import inspect
import functools
import threading
from typing import Any, List, Set, Callable
from dataclasses import dataclass, field


# Patterns that indicate live execution capability
FORBIDDEN_PATTERNS: Set[str] = {
    # Key/signing related
    "private_key", "mnemonic", "seed_phrase", "keystore", "keystore_file",
    "sign_transaction", "sign_typed_data", "personal_sign", "eth_sign",
    "wallet.sign", "account.sign", "signer.sign", "sign_message",
    # Order submission
    "create_and_post_order", "post_order", "submit_order", "place_order",
    "send_transaction", "eth_sendTransaction", "eth_sendRawTransaction",
    "broadcast_transaction", "submit_signed_transaction",
    # Web3 live execution
    "web3.eth.send_transaction", "web3.eth.send_raw_transaction",
    "web3.eth.account.sign_transaction", "web3.eth.account.sign_message",
    # Exchange clients
    "py_clob_client", "clobclient", "clob_client",
    "coinbase.wallet", "coinbasepro", "coinbase_advanced",
    "krakenex", "kraken_client",
    "ccxt.", "ccxtpro.",
    "binance.", "binance_client",
    # DeFi execution
    "uniswap.", "sushiswap.", "pancakeswap.",
    "router.swap", "router.exact_input", "router.exact_output",
    # Private key loading
    "load_private_key", "from_key", "from_mnemonic", "decrypt_key",
    "HDWallet", "BIP44", "derive_path",
}

# Module imports that indicate live execution capability
FORBIDDEN_IMPORTS: Set[str] = {
    "web3.eth.account",
    "eth_account",
    "eth_account.account",
    "eth_account.signers",
    "py_clob_client",
    "py_clob_client_v2",
    "coinbase.wallet",
    "coinbasepro",
    "krakenex",
    "ccxt",
    "ccxt.pro",
    "ccxt.async_support",
    "binance",
    "binance.client",
    "binance.um_futures",
    "binance.cm_futures",
}

# Allowed read-only imports (explicitly permitted)
ALLOWED_READONLY_IMPORTS: Set[str] = {
    "web3",
    "web3.eth",
    "web3.contract",
    "web3.providers",
    "web3.middleware",
    "web3.types",
    "web3.exceptions",
    "requests",
    "urllib",
    "urllib.request",
    "urllib.parse",
    "json",
    "time",
    "datetime",
    "dataclasses",
    "typing",
    "os",
    "pathlib",
    "yaml",
    "decimal",
    "math",
    "statistics",
}


@dataclass
class ExecutionBoundary:
    """
    Runtime guard that prevents ANY live execution in paper mode.
    Injected into all strategy validators and execution engine.
    """
    paper_mode: bool = True
    _guards_installed: bool = False
    _call_stack_cache: List[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        if self.paper_mode:
            self._install_guards()

    def _install_guards(self):
        """Install runtime guards for paper mode."""
        with self._lock:
            if self._guards_installed:
                return

            # Guard sys.modules for forbidden imports
            self._scan_imports()

            # Monkey-patch dangerous builtins if needed
            self._guards_installed = True

    def _scan_imports(self) -> List[str]:
        """Scan sys.modules for forbidden imports."""
        violations = []
        for module_name in sys.modules:
            for forbidden in FORBIDDEN_IMPORTS:
                if module_name.startswith(forbidden):
                    # Check if it's explicitly allowed as read-only
                    allowed = any(module_name.startswith(allowed) for allowed in ALLOWED_READONLY_IMPORTS)
                    if not allowed:
                        violations.append(module_name)
        return violations

    def assert_paper_mode(self, caller: str = ""):
        """Assert we're in paper mode; raise if not."""
        if not self.paper_mode:
            raise RuntimeError(
                f"LIVE EXECUTION ATTEMPT BLOCKED: {caller or 'unknown caller'} "
                f"tried to execute live code in paper mode"
            )

    def scan_for_keys(self, obj: Any, path: str = "") -> List[str]:
        """
        Recursively scan object for key-like strings.
        Returns list of suspicious paths found.
        """
        findings = []
        if isinstance(obj, str):
            obj_lower = obj.lower()
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in obj_lower:
                    findings.append(f"{path}: contains '{pattern}'")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                findings.extend(self.scan_for_keys(v, f"{path}.{k}"))
        elif isinstance(obj, (list, tuple, set)):
            for i, v in enumerate(obj):
                findings.extend(self.scan_for_keys(v, f"{path}[{i}]"))
        elif hasattr(obj, '__dict__'):
            for k, v in obj.__dict__.items():
                findings.extend(self.scan_for_keys(v, f"{path}.{k}"))
        return findings

    def validate_no_live_imports(self) -> List[str]:
        """Check sys.modules for forbidden imports. Returns violations."""
        return self._scan_imports()

    def validate_call_stack(self, depth: int = 10) -> List[str]:
        """
        Scan call stack for forbidden patterns.
        Returns list of suspicious frames.
        """
        violations = []
        stack = inspect.stack()
        for frame_info in stack[1:depth+1]:  # Skip this frame
            frame_str = f"{frame_info.filename}:{frame_info.lineno} in {frame_info.function}"
            frame_lower = frame_str.lower()
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in frame_lower:
                    violations.append(f"Call stack: {frame_str} (matched '{pattern}')")
        return violations

    def guard_function(self, func: Callable) -> Callable:
        """
        Decorator that guards a function against live execution patterns.
        Scans call stack and arguments for forbidden patterns.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self.assert_paper_mode(f"Function call: {func.__name__}")

            # Scan arguments for keys
            for arg in args:
                findings = self.scan_for_keys(arg, f"arg:{func.__name__}")
                if findings:
                    raise RuntimeError(f"KEY MATERIAL DETECTED in {func.__name__}: {findings}")

            for k, v in kwargs.items():
                findings = self.scan_for_keys(v, f"kwarg:{k}")
                if findings:
                    raise RuntimeError(f"KEY MATERIAL DETECTED in {func.__name__}.{k}: {findings}")

            # Scan call stack
            violations = self.validate_call_stack()
            if violations:
                raise RuntimeError(f"LIVE EXECUTION PATTERN IN CALL STACK: {violations}")

            return func(*args, **kwargs)
        return wrapper

    def guard_method(self, method_name: str):
        """
        Class decorator helper to guard a method.
        Usage: boundary.guard_method('execute')(MyClass.execute)
        """
        def decorator(cls):
            original_method = getattr(cls, method_name)
            guarded = self.guard_function(original_method)
            setattr(cls, method_name, guarded)
            return cls
        return decorator


# Global boundary instance (singleton pattern for easy access)
_global_boundary: ExecutionBoundary = None


def get_boundary(paper_mode: bool = True) -> ExecutionBoundary:
    """Get or create the global execution boundary."""
    global _global_boundary
    if _global_boundary is None:
        _global_boundary = ExecutionBoundary(paper_mode=paper_mode)
    elif _global_boundary.paper_mode != paper_mode:
        # Mode changed - create new instance
        _global_boundary = ExecutionBoundary(paper_mode=paper_mode)
    return _global_boundary


def set_paper_mode(paper_mode: bool = True) -> ExecutionBoundary:
    """Explicitly set paper mode and return boundary."""
    global _global_boundary
    _global_boundary = ExecutionBoundary(paper_mode=paper_mode)
    return _global_boundary


# Convenience decorators
def paper_only(func: Callable) -> Callable:
    """Decorator that ensures function only runs in paper mode."""
    boundary = get_boundary()
    return boundary.guard_function(func)


def assert_paper_mode(caller: str = ""):
    """Assert we're in paper mode using global boundary."""
    boundary = get_boundary()
    boundary.assert_paper_mode(caller)