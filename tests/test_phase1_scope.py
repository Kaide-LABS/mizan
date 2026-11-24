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
