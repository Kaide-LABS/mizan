"""End-to-end coverage for the crypto boot gate."""

import pytest

from mizan.config import boot_check
from mizan.config.boot_check import FiqhRegisterError


def test_check_all_runs_crypto_register() -> None:
    boot_check.check_all()


def test_broken_crypto_register_reaches_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> None:
        raise FiqhRegisterError("crypto register source is empty")

    monkeypatch.setattr(boot_check, "check_all", broken)
    assert boot_check.main() == 1
    assert "fiqh register is structurally broken" in capsys.readouterr().err


def test_mizan_boot_check_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert boot_check.main() == 0
    assert "Boot check passed" in capsys.readouterr().out
