from collections import deque

from zendt.errors import RuleNotFound
from zendt.models import RuleEntry
from zendt.rules.catalog import resolve_rule
from zendt.rules.check_jdm import rule_children


def resolve_entries(
    catalog: list[RuleEntry], rules: list[str]
) -> list[RuleEntry]:
    """Resolve each `--rules` name. Missing and ambiguous names fail here."""
    return [resolve_rule(catalog, name) for name in rules]


def load_queued_rules(
    catalog: list[RuleEntry],
    entries: list[RuleEntry],
) -> dict[str | None, dict[str, dict]]:
    """Read `entries` and every decision-node graph they reach, once each."""

    by_key = {(entry.source_id, entry.key): entry for entry in catalog}
    contents: dict[str | None, dict[str, dict]] = {}
    queue: deque[RuleEntry] = deque()
    queued: set[tuple[str | None, str]] = set()

    for entry in entries:
        enqueue(queue, queued, entry)

    while queue:
        entry = queue.popleft()
        source = contents.setdefault(entry.source_id, {})
        if entry.key in source:
            continue
        body = entry.load_content()
        source[entry.key] = body
        for child_key in rule_children(body):
            pair = (entry.source_id, child_key)
            if pair in queued:
                continue
            child = by_key.get(pair)
            if child is None:
                raise RuleNotFound(
                    f"Rule '{child_key}' called by '{entry.ref}' "
                    'was not found.'
                )
            enqueue(queue, queued, child)
    return contents


def enqueue(
    queue: deque[RuleEntry],
    queued: set[tuple[str | None, str]],
    entry: RuleEntry,
) -> None:
    pair = (entry.source_id, entry.key)
    if pair in queued:
        return
    queued.add(pair)
    queue.append(entry)
