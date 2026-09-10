"""In-memory stand-ins for the injected data sources.

The rules are pure functions over data, so they can be tested with no corpus,
no database and no network. That is the reason the protocols exist.
"""

from __future__ import annotations

from typing import ClassVar

from legalrag.models import Code, ProvisionRef, Relationship

# A small slice, chosen to cover every rule at least once.
# Section numbers here are illustrative and stand in for the reviewed
# correspondence file; nothing in the tests depends on them being the real ones.
_SECTIONS: set[tuple[Code, str]] = {
    (Code.IPC, "302"),
    (Code.IPC, "336"),
    (Code.IPC, "420"),
    (Code.IPC, "378"),
    (Code.IPC, "497"),
    (Code.IPC, "34"),
    (Code.BNS, "302"),
    (Code.BNS, "125"),
    (Code.BNS, "103"),
    (Code.BNS, "318"),
    (Code.BNS, "303"),
    (Code.BNS, "3"),
    (Code.CRPC, "154"),
    (Code.BNSS, "173"),
}


class FakeIndex:
    def exists(self, ref: ProvisionRef) -> bool:
        return (ref.code, ref.section) in _SECTIONS

    def heading_matches(self, text: str, limit: int) -> tuple[ProvisionRef, ...]:
        if "endanger" in text.lower():
            return (ProvisionRef(Code.BNS, "125"),)[:limit]
        return ()


class FakeVocabulary:
    _TERMS: ClassVar[dict[str, tuple[ProvisionRef, ...]]] = {
        "rash and negligent act": (
            ProvisionRef(Code.IPC, "336"),
            ProvisionRef(Code.BNS, "125"),
        ),
        "cheating": (ProvisionRef(Code.IPC, "420"), ProvisionRef(Code.BNS, "318")),
        # Deliberately maps to two unrelated offences, to exercise F3.
        "assault": (ProvisionRef(Code.IPC, "302"), ProvisionRef(Code.IPC, "378")),
        "theft": (ProvisionRef(Code.IPC, "378"),),
    }

    def lookup(self, term: str) -> tuple[ProvisionRef, ...]:
        return self._TERMS.get(term.lower(), ())

    def terms(self) -> tuple[str, ...]:
        return tuple(sorted(self._TERMS, key=len, reverse=True))


class FakeCorrespondence:
    """Correspondence data covering one case of each relationship."""

    _REL: ClassVar[dict[tuple[Code, str], Relationship]] = {
        (Code.IPC, "336"): Relationship.CHANGED,  # material: the worked case
        (Code.IPC, "378"): Relationship.UNCHANGED,  # immaterial
        (Code.IPC, "302"): Relationship.UNCHANGED,
        (Code.IPC, "420"): Relationship.SPLIT,
        (Code.IPC, "497"): Relationship.NO_SUCCESSOR,
        (Code.IPC, "34"): Relationship.DISPUTED,
        (Code.BNS, "125"): Relationship.CHANGED,
        (Code.BNS, "302"): Relationship.UNCHANGED,
    }
    _SUCC: ClassVar[dict[tuple[Code, str], tuple[ProvisionRef, ...]]] = {
        (Code.IPC, "336"): (ProvisionRef(Code.BNS, "125"),),
        (Code.IPC, "378"): (ProvisionRef(Code.BNS, "303"),),
        (Code.IPC, "302"): (ProvisionRef(Code.BNS, "103"),),
        (Code.IPC, "420"): (ProvisionRef(Code.BNS, "318"), ProvisionRef(Code.BNS, "319")),
        (Code.IPC, "497"): (),
        (Code.IPC, "34"): (ProvisionRef(Code.BNS, "3"),),
        (Code.BNS, "125"): (ProvisionRef(Code.IPC, "336"),),
        (Code.BNS, "302"): (ProvisionRef(Code.IPC, "506"),),
    }
    # None means the provision carries no sentencing language at all.
    _MATERIAL: ClassVar[dict[tuple[Code, str], bool | None]] = {
        (Code.IPC, "336"): True,
        (Code.BNS, "125"): True,
        (Code.IPC, "378"): False,
        (Code.IPC, "302"): False,
        (Code.BNS, "302"): False,
        (Code.IPC, "34"): None,
    }

    def relationship(self, ref: ProvisionRef) -> Relationship | None:
        return self._REL.get((ref.code, ref.section))

    def successors(self, ref: ProvisionRef) -> tuple[ProvisionRef, ...]:
        return self._SUCC.get((ref.code, ref.section), ())

    def is_material(self, ref: ProvisionRef) -> bool | None:
        return self._MATERIAL.get((ref.code, ref.section))

    def are_correspondents(self, a: ProvisionRef, b: ProvisionRef) -> bool:
        return b in self.successors(a) or a in self.successors(b)


class FakeSplits:
    """Unpopulated and off, matching what ships."""

    def __init__(self, *, on: bool = False) -> None:
        self._on = on

    def enabled(self) -> bool:
        return self._on

    def matches(self, ref: ProvisionRef) -> tuple[str, ...]:
        if self._on and ref.section == "378":
            return ("whether the article must be movable at the time of taking",)
        return ()
