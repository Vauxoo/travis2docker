"""Exception classes raised by various operations within travis2docker."""


class InvalidRepoBranchError(Exception):
    """Raised when a repo branch is wrong."""
