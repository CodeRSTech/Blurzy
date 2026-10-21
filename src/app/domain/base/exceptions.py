"""Custom exceptions for domain layer validation and error handling.

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""


class EmptySetGeneratedFromKeysError(Exception):
    """Raised when converting iterable of keys to set results in empty set (all falsy).

Layer: Domain.
Context: Represents application concepts without UI or infrastructure dependencies.


    Args:
        message: Message describing the error or condition.
"""
    def __init__(self, message):
        super().__init__(f"{message}\nEmpty set generated from keys.")