"""Custom exceptions for domain layer validation and error handling.

See Also:
    - [`new_passes_filter`][app.domain.helpers.functions.new_passes_filter] — raises key-derived validation errors
    - [`DomainException`][app.shared.exceptions.DomainException] — shared base for domain-facing failures

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