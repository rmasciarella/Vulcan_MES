"""
Field-Level Encryption for Sensitive Data

This module provides encryption for sensitive fields in the database,
including PII and confidential business data.
"""

import base64
import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TypeVar

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from pydantic import Field
from sqlalchemy import event
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EncryptionManager:
    """Manages field-level encryption for sensitive data."""

    def __init__(self, master_key: str | None = None):
        """Initialize encryption manager with master key.

        Args:
            master_key: Base64 encoded master key or None to generate
        """
        if master_key:
            self.master_key = base64.b64decode(master_key)
        else:
            # Generate a new master key (store this securely!)
            self.master_key = Fernet.generate_key()
            logger.warning(
                f"Generated new master key: {base64.b64encode(self.master_key).decode()}"
                " - Store this securely in environment variables!"
            )

        self.cipher = Fernet(self.master_key)

        # Cache for derived keys (key derivation is expensive)
        self._key_cache = {}

    def derive_key(self, context: str, salt: bytes = None) -> Fernet:
        """Derive a context-specific key from master key.

        Args:
            context: Context string for key derivation (e.g., "user_data", "job_data")
            salt: Optional salt for key derivation

        Returns:
            Fernet cipher with derived key
        """
        cache_key = f"{context}:{salt.hex() if salt else 'default'}"

        if cache_key in self._key_cache:
            return self._key_cache[cache_key]

        if salt is None:
            salt = context.encode()[:16].ljust(16, b"\0")

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        derived_key = base64.urlsafe_b64encode(
            kdf.derive(self.master_key + context.encode())
        )
        cipher = Fernet(derived_key)

        # Cache the derived cipher
        self._key_cache[cache_key] = cipher

        return cipher

    def encrypt(self, value: Any, context: str = "default") -> str:
        """Encrypt a value.

        Args:
            value: Value to encrypt (will be JSON serialized)
            context: Encryption context

        Returns:
            Base64 encoded encrypted value
        """
        if value is None:
            return None

        # Serialize complex types
        if isinstance(value, datetime | date):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        elif isinstance(value, Enum):
            value = value.value

        # Convert to JSON for consistent serialization
        json_value = json.dumps(value)

        # Get context-specific cipher
        cipher = self.derive_key(context)

        # Encrypt
        encrypted = cipher.encrypt(json_value.encode())

        # Return base64 encoded for storage
        return base64.b64encode(encrypted).decode()

    def decrypt(self, encrypted_value: str, context: str = "default") -> Any:
        """Decrypt a value.

        Args:
            encrypted_value: Base64 encoded encrypted value
            context: Encryption context

        Returns:
            Decrypted value
        """
        if encrypted_value is None:
            return None

        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted_value)

            # Get context-specific cipher
            cipher = self.derive_key(context)

            # Decrypt
            decrypted = cipher.decrypt(encrypted_bytes)

            # Parse JSON
            return json.loads(decrypted.decode())

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt value")

    def encrypt_dict(
        self, data: dict, fields_to_encrypt: list[str], context: str = "default"
    ) -> dict:
        """Encrypt specific fields in a dictionary.

        Args:
            data: Dictionary containing data
            fields_to_encrypt: List of field names to encrypt
            context: Encryption context

        Returns:
            Dictionary with encrypted fields
        """
        encrypted_data = data.copy()

        for field in fields_to_encrypt:
            if field in encrypted_data and encrypted_data[field] is not None:
                encrypted_data[field] = self.encrypt(
                    encrypted_data[field], context=f"{context}:{field}"
                )

        return encrypted_data

    def decrypt_dict(
        self, data: dict, fields_to_decrypt: list[str], context: str = "default"
    ) -> dict:
        """Decrypt specific fields in a dictionary.

        Args:
            data: Dictionary containing encrypted data
            fields_to_decrypt: List of field names to decrypt
            context: Encryption context

        Returns:
            Dictionary with decrypted fields
        """
        decrypted_data = data.copy()

        for field in fields_to_decrypt:
            if field in decrypted_data and decrypted_data[field] is not None:
                decrypted_data[field] = self.decrypt(
                    decrypted_data[field], context=f"{context}:{field}"
                )

        return decrypted_data


# Global encryption manager instance
# In production, load key from secure environment variable or key management service
ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY")
encryption_manager = EncryptionManager(ENCRYPTION_KEY)


class EncryptedField:
    """Descriptor for encrypted fields in SQLModel."""

    def __init__(self, field_type: type = str, context: str = "default"):
        """Initialize encrypted field.

        Args:
            field_type: Type of the field when decrypted
            context: Encryption context for this field
        """
        self.field_type = field_type
        self.context = context
        self.private_name = None

    def __set_name__(self, owner, name):
        """Set the field name when attached to a class."""
        self.private_name = f"_{name}_encrypted"
        self.public_name = name

    def __get__(self, obj, objtype=None):
        """Get decrypted value."""
        if obj is None:
            return self

        encrypted_value = getattr(obj, self.private_name, None)
        if encrypted_value is None:
            return None

        return encryption_manager.decrypt(encrypted_value, self.context)

    def __set__(self, obj, value):
        """Set encrypted value."""
        if value is None:
            setattr(obj, self.private_name, None)
        else:
            encrypted_value = encryption_manager.encrypt(value, self.context)
            setattr(obj, self.private_name, encrypted_value)


class EncryptedMixin:
    """Mixin for models with encrypted fields."""

    # Override in subclass to specify which fields to encrypt
    __encrypted_fields__ = []
    __encryption_context__ = "default"

    def encrypt_fields(self):
        """Encrypt sensitive fields before saving."""
        for field_name in self.__encrypted_fields__:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                if value is not None:
                    encrypted = encryption_manager.encrypt(
                        value, context=f"{self.__encryption_context__}:{field_name}"
                    )
                    setattr(self, f"_{field_name}_encrypted", encrypted)
                    # Clear plain text value
                    setattr(self, field_name, None)

    def decrypt_fields(self):
        """Decrypt sensitive fields after loading."""
        for field_name in self.__encrypted_fields__:
            encrypted_attr = f"_{field_name}_encrypted"
            if hasattr(self, encrypted_attr):
                encrypted_value = getattr(self, encrypted_attr)
                if encrypted_value is not None:
                    decrypted = encryption_manager.decrypt(
                        encrypted_value,
                        context=f"{self.__encryption_context__}:{field_name}",
                    )
                    setattr(self, field_name, decrypted)


# SQLAlchemy event listeners for automatic encryption/decryption
def setup_encryption_listeners(model_class: type[SQLModel]):
    """Setup SQLAlchemy event listeners for automatic encryption.

    Args:
        model_class: SQLModel class with EncryptedMixin
    """
    if not issubclass(model_class, EncryptedMixin):
        return

    @event.listens_for(model_class, "before_insert")
    @event.listens_for(model_class, "before_update")
    def encrypt_before_save(mapper, connection, target):
        """Encrypt fields before saving to database."""
        target.encrypt_fields()

    @event.listens_for(model_class, "load")
    def decrypt_after_load(target, context):
        """Decrypt fields after loading from database."""
        target.decrypt_fields()


# Example encrypted models
class EncryptedOperatorData(SQLModel, EncryptedMixin, table=True):
    """Example model with encrypted operator PII."""

    __tablename__ = "encrypted_operators"
    __encrypted_fields__ = ["ssn", "phone", "address", "salary"]
    __encryption_context__ = "operator_pii"

    id: int = Field(primary_key=True)
    employee_id: str = Field(index=True, unique=True)
    name: str  # Not encrypted - needed for display
    email: str  # Not encrypted - needed for login

    # Encrypted PII fields (stored as text in DB)
    _ssn_encrypted: str | None = Field(default=None, alias="ssn_encrypted")
    _phone_encrypted: str | None = Field(default=None, alias="phone_encrypted")
    _address_encrypted: str | None = Field(default=None, alias="address_encrypted")
    _salary_encrypted: str | None = Field(default=None, alias="salary_encrypted")

    # Virtual properties for accessing decrypted values
    @property
    def ssn(self) -> str | None:
        if self._ssn_encrypted:
            return encryption_manager.decrypt(
                self._ssn_encrypted, context=f"{self.__encryption_context__}:ssn"
            )
        return None

    @ssn.setter
    def ssn(self, value: str | None):
        if value:
            self._ssn_encrypted = encryption_manager.encrypt(
                value, context=f"{self.__encryption_context__}:ssn"
            )
        else:
            self._ssn_encrypted = None

    @property
    def phone(self) -> str | None:
        if self._phone_encrypted:
            return encryption_manager.decrypt(
                self._phone_encrypted, context=f"{self.__encryption_context__}:phone"
            )
        return None

    @phone.setter
    def phone(self, value: str | None):
        if value:
            self._phone_encrypted = encryption_manager.encrypt(
                value, context=f"{self.__encryption_context__}:phone"
            )
        else:
            self._phone_encrypted = None


class EncryptedJobData(SQLModel, EncryptedMixin, table=True):
    """Example model with encrypted sensitive job data."""

    __tablename__ = "encrypted_jobs"
    __encrypted_fields__ = ["customer_details", "special_instructions", "cost_data"]
    __encryption_context__ = "job_sensitive"

    id: int = Field(primary_key=True)
    job_number: str = Field(index=True, unique=True)
    description: str  # Not encrypted - needed for display

    # Encrypted sensitive fields
    _customer_details_encrypted: str | None = Field(
        default=None, alias="customer_details_encrypted"
    )
    _special_instructions_encrypted: str | None = Field(
        default=None, alias="special_instructions_encrypted"
    )
    _cost_data_encrypted: str | None = Field(default=None, alias="cost_data_encrypted")

    @property
    def customer_details(self) -> dict | None:
        if self._customer_details_encrypted:
            return encryption_manager.decrypt(
                self._customer_details_encrypted,
                context=f"{self.__encryption_context__}:customer_details",
            )
        return None

    @customer_details.setter
    def customer_details(self, value: dict | None):
        if value:
            self._customer_details_encrypted = encryption_manager.encrypt(
                value, context=f"{self.__encryption_context__}:customer_details"
            )
        else:
            self._customer_details_encrypted = None


# Utility functions for encrypting data in transit
def encrypt_response_fields(
    response_data: dict, fields_to_encrypt: list[str], context: str = "api_response"
) -> dict:
    """Encrypt specific fields in API response.

    Args:
        response_data: Response data dictionary
        fields_to_encrypt: Fields to encrypt
        context: Encryption context

    Returns:
        Response with encrypted fields
    """
    return encryption_manager.encrypt_dict(response_data, fields_to_encrypt, context)


def decrypt_request_fields(
    request_data: dict, fields_to_decrypt: list[str], context: str = "api_request"
) -> dict:
    """Decrypt specific fields in API request.

    Args:
        request_data: Request data dictionary
        fields_to_decrypt: Fields to decrypt
        context: Encryption context

    Returns:
        Request with decrypted fields
    """
    return encryption_manager.decrypt_dict(request_data, fields_to_decrypt, context)
