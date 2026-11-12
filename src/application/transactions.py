import collections.abc
import hashlib
import json
import typing
import uuid


class KeyConflict(ValueError):
    pass


class Transaction[Writer](typing.Protocol):
    def run(
        self,
        key: uuid.UUID,
        command: str,
        fingerprint: str,
        write: collections.abc.Callable[[Writer], int],
    ) -> int: ...


def fingerprint(*arguments: int | str | None) -> str:
    payload = json.dumps(arguments, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()
