from enum import StrEnum


class TransferStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Direction(StrEnum):
    INTERNAL = "INTERNAL"
    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"


class ActivityType(StrEnum):
    ONE_TIME_TRANSFER = "ONE_TIME_TRANSFER"
    RULE = "RULE"
    DIRECT_DEPOSIT = "DIRECT_DEPOSIT"
    ACH = "ACH"


class AccountType(StrEnum):
    POD = "POD"
    PORT = "PORT"
    ACCOUNT = "ACCOUNT"
