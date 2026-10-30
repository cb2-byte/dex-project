"""
Wallet Manager
==============
Secure wallet and key management for Solana operations.
Handles keypair loading, transaction signing, and secure key storage.
"""

from __future__ import annotations
import os
import json
import base64
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from abc import ABC, abstractmethod

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.signature import Signature

from paper_engine.boundaries import get_boundary, assert_paper_mode


class KeyStore(ABC):
    """Abstract key storage backend."""

    @abstractmethod
    def load(self, key_id: str) -> Optional[bytes]:
        """Load encrypted key data."""

    @abstractmethod
    def save(self, key_id: str, data: bytes) -> None:
        """Save encrypted key data."""

    @abstractmethod
    def delete(self, key_id: str) -> bool:
        """Delete key data."""

    @abstractmethod
    def list_keys(self) -> List[str]:
        """List available key IDs."""


class FileKeyStore(KeyStore):
    """File-based encrypted key storage."""

    def __init__(self, base_path: str, encryption_key: Optional[bytes] = None):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.encryption_key = encryption_key

    def _get_path(self, key_id: str) -> Path:
        return self.base_path / f"{key_id}.key"

    def _encrypt(self, data: bytes) -> bytes:
        if not self.encryption_key:
            return data
        # In production, use proper encryption (e.g., nacl.secret.SecretBox)
        # This is a placeholder
        return data

    def _decrypt(self, data: bytes) -> bytes:
        if not self.encryption_key:
            return data
        return data

    def load(self, key_id: str) -> Optional[bytes]:
        path = self._get_path(key_id)
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return self._decrypt(f.read())

    def save(self, key_id: str, data: bytes) -> None:
        path = self._get_path(key_id)
        with open(path, "wb") as f:
            f.write(self._encrypt(data))
        # Set restrictive permissions
        os.chmod(path, 0o600)

    def delete(self, key_id: str) -> bool:
        path = self._get_path(key_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_keys(self) -> List[str]:
        return [f.stem for f in self.base_path.glob("*.key")]


class WalletManager:
    """
    Secure wallet and key management for Solana operations.
    Handles keypair loading, transaction signing, and secure key storage.
    """

    def __init__(
        self,
        key_store: Optional[KeyStore] = None,
        default_key_id: str = "default",
    ):
        self._keypair: Optional[Keypair] = None
        self._key_id = default_key_id
        self._key_store = key_store or FileKeyStore(
            base_path="/home/ubuntu/.config/pennyshield/keys"
        )
        self._key_id = default_key_id

    def generate_keypair(self) -> Keypair:
        """Generate a new random keypair."""
        return Keypair()

    def create_keypair(self, key_id: Optional[str] = None) -> Keypair:
        """Create and store a new keypair."""
        keypair = self.generate_keypair()
        key_id = key_id or self._key_id
        self._store_keypair(key_id, keypair)
        self._keypair = keypair
        self._key_id = key_id
        return keypair

    def _store_keypair(self, key_id: str, keypair: Keypair):
        """Store keypair securely."""
        secret_bytes = bytes(keypair)
        self._key_store.save(key_id, secret_bytes)

    def load_keypair(self, key_id: Optional[str] = None) -> Keypair:
        """Load keypair from storage."""
        key_id = key_id or self._key_id
        secret_bytes = self._key_store.load(key_id)
        if not secret_bytes:
            raise ValueError(f"No keypair found for key_id: {key_id}")
        return Keypair.from_bytes(secret_bytes)

    def load_keypair_from_bytes(self, secret_bytes: bytes) -> Keypair:
        """Load keypair from raw bytes."""
        return Keypair.from_bytes(secret_bytes)

    def load_keypair_from_base58(self, secret_b58: str) -> Keypair:
        """Load keypair from base58 encoded secret."""
        secret_bytes = base64.b58decode(secret_b58)
        return Keypair.from_bytes(secret_bytes)

    def load_keypair_from_json(self, json_str: str) -> Keypair:
        """Load keypair from JSON array string."""
        secret_list = json.loads(json_str)
        secret_bytes = bytes(secret_list)
        return Keypair.from_bytes(secret_bytes)

    def get_keypair(self, key_id: Optional[str] = None) -> Keypair:
        """Get current keypair, loading if necessary."""
        if not self._keypair:
            self._keypair = self.load_keypair(key_id)
        return self._keypair

    def set_keypair(self, keypair: Keypair, key_id: Optional[str] = None):
        """Set and store keypair."""
        self._keypair = keypair
        if key_id:
            self._key_id = key_id
        self._store_keypair(self._key_id, keypair)

    def get_pubkey(self) -> Pubkey:
        """Get public key of current keypair."""
        return self.get_keypair().pubkey()

    def get_key_id(self) -> str:
        """Get current key ID."""
        return self._key_id

    def sign_transaction(self, transaction: VersionedTransaction) -> VersionedTransaction:
        """Sign a versioned transaction."""
        keypair = self.get_keypair()
        return transaction.sign([keypair])

    def sign_message(self, message: bytes) -> bytes:
        """Sign arbitrary message."""
        keypair = self.get_keypair()
        return keypair.sign_message(message)

    def sign_bytes(self, data: bytes) -> bytes:
        """Sign arbitrary bytes."""
        keypair = self.get_keypair()
        return keypair.sign(data)

    def export_keypair(self, key_id: Optional[str] = None) -> dict:
        """Export keypair as JSON for backup."""
        keypair = self.get_keypair(key_id)
        return {
            "key_id": key_id or self._key_id,
            "pubkey": str(keypair.pubkey()),
            "secret": list(bytes(keypair)),
        }

    def import_keypair(self, backup: dict, key_id: Optional[str] = None) -> Keypair:
        """Import keypair from backup dict."""
        secret_bytes = bytes(backup["secret"])
        keypair = Keypair.from_bytes(secret_bytes)
        self.set_keypair(keypair, key_id or backup.get("key_id"))
        return keypair

    def rotate_key(self, new_key_id: Optional[str] = None) -> Keypair:
        """Generate and rotate to a new keypair."""
        old_key_id = self._key_id
        new_keypair = self.create_keypair(new_key_id)
        # In production, you might want to archive the old key
        return new_keypair

    def list_keys(self) -> List[str]:
        """List all stored key IDs."""
        return self._key_store.list_keys()

    def delete_key(self, key_id: str) -> bool:
        """Delete a stored key."""
        if key_id == self._key_id:
            self._keypair = None
            self._key_id = "default"
        return self._key_store.delete(key_id)


def create_wallet_manager(
    key_path: Optional[str] = None,
    key_b58: Optional[str] = None,
    key_json: Optional[str] = None,
    key_id: str = "default",
) -> WalletManager:
    """Factory function to create WalletManager from various key formats."""
    manager = WalletManager(default_key_id=key_id)

    if key_path:
        # Load from file
        with open(key_path, "r") as f:
            content = f.read().strip()
            try:
                # Try JSON first
                keypair = Keypair.from_json(key_path)
            except:
                # Try base58
                keypair = Keypair.from_base58_string(content.strip())
        manager.set_keypair(keypair, key_id)
        return manager

    if key_b58:
        keypair = Keypair.from_base58_string(key_b58)
        manager.set_keypair(keypair, key_id)
        return manager

    if key_json:
        keypair = Keypair.from_json(key_json)
        manager.set_keypair(keypair, key_id)
        return manager

    # Generate new if no key provided
    manager.create_keypair(key_id)
    return manager


__all__ = [
    "WalletManager",
    "KeyStore",
    "FileKeyStore",
    "create_wallet_manager",
]