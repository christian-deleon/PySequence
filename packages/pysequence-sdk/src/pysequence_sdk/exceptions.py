
class SequenceError(Exception):
    """Base exception for SDK errors."""


class AuthenticationError(SequenceError):
    """Failed to authenticate with GetSequence."""


class GraphQLError(SequenceError):
    """GraphQL query/mutation returned errors."""

    def __init__(self, errors: list[dict], query: str = ""):
        self.errors = errors
        self.query = query
        super().__init__(f"GraphQL errors: {errors}")


class TokenExpiredError(SequenceError):
    """Access token has expired and refresh failed."""
