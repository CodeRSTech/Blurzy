"""Custom exceptions for domain layer validation and error handling."""


class EmptySetGeneratedFromKeysError(Exception):
    """Raised when converting iterable of keys to set results in empty set (all falsy)."""
    def __init__(self, message):
        super().__init__(f"{message}\nEmpty set generated from keys.")