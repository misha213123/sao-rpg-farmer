from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass


LOGGER = logging.getLogger("sao-rpg-farmer.launcher")

# Start the stable runtime chain directly:
# start_guard -> bootstrap -> mode patches -> main.
# manual_control_patch is intentionally bypassed because it depends on brittle
# source-text replacements and was stopping the whole service after refactors.
CHILD_MODULE = "app.start_guard"


@dataclass(frozen=True, slots=True)
class AccountProcess:
    name: str
    session: str


def _required_session(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def _accounts_from_env() -> list[AccountProcess]:
    # Backward compatibility: the first account may continue using the old
    # STRING_SESSION variable. STRING_SESSION_1 takes priority when provided.
    first_session = (
        os.getenv("STRING_SESSION_1", "").strip()
        or os.getenv("STRING_SESSION", "").strip()
    )
    if not first_session:
        raise RuntimeError(
            "Set STRING_SESSION_1 (or keep the existing STRING_SESSION) "
            "for the first Telegram account"
        )

    second_session = _required_session("STRING_SESSION_2")
    if first_session == second_session:
        raise RuntimeError("STRING_SESSION_1 and STRING_SESSION_2 must be different")

    return [
        AccountProcess("account_1", first_session),
        AccountProcess("account_2", second_session),
    ]


def _start_child(account: AccountProcess) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    # Existing application code reads STRING_SESSION. Each child receives its
    # own value and therefore keeps an independent TelegramClient/RuntimeState.
    env["STRING_SESSION"] = account.session
    env["ACCOUNT_NAME"] = account.name

    LOGGER.info("Starting %s", account.name)
    return subprocess.Popen(
        [sys.executable, "-m", CHILD_MODULE],
        env=env,
        start_new_session=True,
    )


def _terminate(children: list[subprocess.Popen[bytes]]) -> None:
    for child in children:
        if child.poll() is not None:
            continue
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    deadline = time.monotonic() + 10
    for child in children:
        if child.poll() is not None:
            continue
        timeout = max(0.0, deadline - time.monotonic())
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def main() -> int:
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    accounts = _accounts_from_env()
    children: list[subprocess.Popen[bytes]] = []
    stopping = False

    def handle_stop(signum: int, _frame: object) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        LOGGER.info("Received signal %s; stopping both accounts", signum)
        _terminate(children)

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    try:
        children.append(_start_child(accounts[0]))

        # Bootstrap still applies idempotent source patches before running.
        # Start accounts sequentially so they never write the same files at once.
        time.sleep(8)
        if children[0].poll() is not None:
            return children[0].returncode or 1

        children.append(_start_child(accounts[1]))
        LOGGER.info("Both Telegram accounts are running")

        while not stopping:
            for index, child in enumerate(children):
                return_code = child.poll()
                if return_code is not None:
                    LOGGER.error(
                        "%s stopped with exit code %s; stopping the other account",
                        accounts[index].name,
                        return_code,
                    )
                    _terminate(children)
                    return return_code or 1
            time.sleep(2)
    finally:
        _terminate(children)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
