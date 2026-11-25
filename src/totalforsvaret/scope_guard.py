"""Säkerhetsskydds- och avgränsningsfilter enligt SECURITY_AND_SCOPE.md.

Säkerställer att pipelinen ENDAST släpper igenom normativ, organisatorisk och
utbildande information (struktur, roller, formella krav) och aktivt filtrerar bort
uppfyllnadsbedömningar, brister, tillsynsbeslut och risk- och sårbarhetsanalyser (RSA).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
import yaml


DEFAULT_BLOCKED_PATTERNS: tuple[str, ...] = (
    "risk- och sårbarhetsanalys",
    "risk-och-sarbarhetsanalys",
    "rsa-",
    "förmågebedömning",
    "mognadsbedömning",
    "tillsynsbeslut",
    "brister i beredskapen",
    "uppföljning av beredskapsförmåga",
    "återrapportering",
    "skyddsobjekt",
)


class ScopeGuard:
    """Kontrollerar URL:er, titlar och dokumentmetadata mot exkluderingsreglerna."""

    def __init__(self, blocked_patterns: Iterable[str] = DEFAULT_BLOCKED_PATTERNS) -> None:
        self.blocked_patterns = tuple(p.lower().strip() for p in blocked_patterns if p.strip())

    @classmethod
    def from_sources_yaml(cls, yaml_path: Path) -> "ScopeGuard":
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        rules = data.get("exclusion_rules", {}) or {}
        patterns = rules.get("blocked_doc_patterns", list(DEFAULT_BLOCKED_PATTERNS))
        return cls(blocked_patterns=patterns)

    def is_allowed(self, *, title: str = "", url: str = "", summary: str = "") -> tuple[bool, str | None]:
        """Returnerar (True, None) om källan är tillåten, annars (False, orsak)."""
        haystack = f"{title} {url} {summary}".lower()
        for pattern in self.blocked_patterns:
            if pattern in haystack:
                return False, f"Blockerad enligt SECURITY_AND_SCOPE.md (träff på mönster: '{pattern}')"
        return True, None
