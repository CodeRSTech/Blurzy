# Domain exceptions

The domain defines a focused validation exception for key-derived sets:

| Exception | Raised when | Typical use |
| --- | --- | --- |
| `EmptySetGeneratedFromKeysError` | Filtering falsy values from an iterable leaves no keys. | Domain helper code rejects an empty result rather than continuing with an unusable set. |

The current use is in `str_iterable_as_set_without_null_values`, which
normalizes and validates a collection of string keys. This exception belongs
to the domain base package; exceptions in the shared layer or in adapters are
separate and are not domain exceptions.

See [domain base types and exceptions](base.md) for package ownership and the
generated API reference for the exception's exact definition.
