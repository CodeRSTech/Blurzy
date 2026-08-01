"""Custom exceptions for domain layer validation and error handling."""


class EmptySetGeneratedFromKeysError(Exception):
    """Raised when converting iterable of keys to set results in empty set (all falsy)."""
    def __init__(self, message):
        # [AUDIT] BUG: String formatting error — literal {message} instead of f-string.
        # This prevents the actual error message from being included in the exception.
        # Fix: Change to f"{message}\nEmpty set generated from keys."
        super().__init__(f"{message}\nEmpty set generated from keys.")