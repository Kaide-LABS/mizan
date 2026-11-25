"""Regression checks for Phase 1's deliberately narrow implementation scope."""

from pathlib import Path


def test_no_forbidden_implementation_modules_exist_under_mizan() -> None:
    """Phase 1 must not accidentally ship execution or signal implementations."""
    package_root = Path(__file__).parents[1] / "mizan"
    forbidden_fragments = (
        "hft",
        "live_trad",
        "exchange_api",
        "signal_adapter",
    )
    implementation_paths = {
        path.as_posix().lower()
        for path in package_root.rglob("*.py")
        if path.name != "__init__.py"
    }
    assert not {
        path
        for path in implementation_paths
        if any(fragment in path for fragment in forbidden_fragments)
    }


def test_intent_module_has_no_network_or_live_order_capability() -> None:
    """The Phase 1 execution layer contains terminal value objects only."""
    intent_source = (Path(__file__).parents[1] / "mizan/execution/intent.py").read_text(
        encoding="utf-8"
    )
    forbidden_terms = ("httpx", "requests", "socket", "api_key", "cancel(")
    assert not {
        term for term in forbidden_terms if term in intent_source.lower()
    }


def test_forbidden_module_scan_already_walks_into_mizan_crypto() -> None:
    """`package_root.rglob("*.py")` in the test above already recurses into
    `mizan/crypto/`, so no code change was needed there -- this only makes that
    coverage explicit per PHASE_2_SPEC.md §B7 / PHASE_3_SPEC.md A0.10."""
    package_root = Path(__file__).parents[1] / "mizan"
    crypto_paths = {p.as_posix() for p in (package_root / "crypto").rglob("*.py")}
    assert crypto_paths, "mizan/crypto/ must contain a module for this check to mean anything"


def test_crypto_clock_and_models_have_no_network_capability() -> None:
    package_root = Path(__file__).parents[1] / "mizan"
    for name in ("clock.py", "models.py"):
        source = (package_root / "crypto" / name).read_text(encoding="utf-8").lower()
        assert "httpx" not in source
        assert "socket" not in source


def test_crypto_screening_module_has_no_network_or_db_capability() -> None:
    source = (
        Path(__file__).parents[1] / "mizan/crypto/screening.py"
    ).read_text(encoding="utf-8").lower()
    for forbidden in ("httpx", "duckdb", "socket"):
        assert forbidden not in source


def test_crypto_clock_module_never_imports_the_equity_rebalance_clock() -> None:
    package_root = Path(__file__).parents[1] / "mizan" / "crypto"
    forbidden = ("mizan.backtest.clock", "generate_rebalance_dates")
    for path in package_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert not any(term in source for term in forbidden), path


def test_phase2_governing_spec_copy_exists_on_disk() -> None:
    spec_path = Path(__file__).parents[1] / "docs/crypto/PHASE_2_SPEC.md"
    assert spec_path.exists()
    assert spec_path.read_text(encoding="utf-8").splitlines()[0].startswith("# Phase 2")


def test_crypto_backtest_module_has_no_network_capability() -> None:
    """`duckdb` is explicitly PERMITTED in this file (it reads the local `candles` store) --
    unlike `mizan/crypto/screening.py`'s own no-`duckdb` assertion, this test only checks for
    network/process-escape capability, not for `duckdb` itself."""
    source = (
        Path(__file__).parents[1] / "mizan/crypto/backtest.py"
    ).read_text(encoding="utf-8").lower()
    for forbidden in ("httpx", "socket"):
        assert forbidden not in source


def test_phase4_governing_spec_copy_exists_on_disk() -> None:
    spec_path = Path(__file__).parents[1] / "docs/crypto/PHASE_4_SPEC.md"
    assert spec_path.exists()
    assert spec_path.read_text(encoding="utf-8").splitlines()[0].startswith("# Phase 4")


def test_signal_package_has_no_network_or_forecasting_implementation() -> None:
    """Forbids an import of each named dependency, not the bare substring: the gate's own
    typed criteria (§PHASE_5_SPEC.md §B1) legitimately names the ``timesfm_2_5`` baseline as
    an enum value, which a plain substring grep for "timesfm" would also (wrongly) flag."""
    package_root = Path(__file__).parents[1] / "mizan" / "signal"
    forbidden_imports = ("httpx", "requests", "socket", "timesfm", "numpy")
    for path in package_root.rglob("*.py"):
        for line in path.read_text(encoding="utf-8").lower().splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert not any(
                    term in stripped for term in forbidden_imports
                ), (path, stripped)


def test_no_concrete_signal_adapter_implementation_ships_under_mizan() -> None:
    package_root = Path(__file__).parents[1] / "mizan"
    referencing = [
        path
        for path in package_root.rglob("*.py")
        if "SignalAdapter" in path.read_text(encoding="utf-8")
    ]
    assert referencing == [package_root / "signal" / "contract.py"]


def test_require_passing_gate_is_not_yet_called_from_backtest_or_crypto_code() -> None:
    package_root = Path(__file__).parents[1] / "mizan"
    for subdir in ("backtest", "crypto"):
        for path in (package_root / subdir).glob("*.py"):
            assert "require_passing_gate" not in path.read_text(encoding="utf-8"), path


def test_phase5_governing_spec_copy_exists_on_disk() -> None:
    spec_path = Path(__file__).parents[1] / "docs/crypto/PHASE_5_SPEC.md"
    assert spec_path.exists()
    assert spec_path.read_text(encoding="utf-8").splitlines()[0].startswith("# Phase 5")
