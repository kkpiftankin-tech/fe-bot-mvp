"""Taxonomy migration CLI (SETUP-12 / S8).

Использование:

    python -m fe_bot.taxonomy.migration v0_to_v1 [--apply] [--setup-job SID]

Команда:
- ``v0_to_v1`` — backfill legacy ParsedSection.section_type →
  ClassificationState и RAGCard.front_matter → taxonomy_*.

Флаги:
- ``--apply`` — действительно применить изменения. По умолчанию
  dry-run (только counter'ы).
- ``--setup-job SID`` — ограничить миграцию одним setup_job.
- ``--no-cards`` — пропустить миграцию RAGCard.
- ``--no-sections`` — пропустить миграцию ParsedSection.

MVP: миграция работает с in-memory репозиториями из dependencies.py.
Для production-storage (PG) interface ``_SectionRepoLike`` остаётся
тот же; нужны лишь реальные репозитории.
"""

from __future__ import annotations

import argparse
import logging
import sys

from fe_bot.api.dependencies import (
    _card_registry,
    _parsed_section_repo,
    get_taxonomy_registry,
)
from fe_bot.taxonomy.migration.v0_to_v1 import (
    migrate_cards,
    migrate_sections,
)

logger = logging.getLogger("fe_bot.taxonomy.migration")


def _print_report(label: str, report) -> None:  # noqa: ANN001 — for printing
    print(f"\n== {label} ==")
    print(f"  total:    {report.total}")
    print(f"  migrated: {report.migrated}")
    print(f"  skipped:  {report.skipped}")
    print(f"  unknown:  {report.unknown}")
    if report.errors:
        print(f"  errors ({len(report.errors)}):")
        for err in report.errors[:20]:
            print(f"    - {err}")
        if len(report.errors) > 20:
            print(f"    ... +{len(report.errors) - 20} more")


class _RepoAdapter:
    """Адаптирует InMemoryParsedSectionRepository под
    _SectionRepoLike protocol."""

    def __init__(self, repo, setup_job_id: str | None) -> None:
        self._repo = repo
        self._setup_job_id = setup_job_id

    def list_all(self):
        sections = self._repo.list_all()
        if self._setup_job_id is not None:
            sections = [
                s
                for s in sections
                if getattr(s, "parse_job_id", "").startswith(self._setup_job_id)
                or getattr(s, "setup_job_id", "") == self._setup_job_id
            ]
        return sections

    def upsert(self, section) -> None:
        self._repo.upsert(section)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fe_bot.taxonomy.migration",
        description="Migrate legacy classifier data to SETUP-12 hierarchical taxonomy",
    )
    parser.add_argument(
        "command", choices=["v0_to_v1"], help="Migration command"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default: dry-run)",
    )
    parser.add_argument(
        "--setup-job",
        dest="setup_job_id",
        default=None,
        help="Limit migration to specific setup_job_id",
    )
    parser.add_argument("--no-sections", action="store_true")
    parser.add_argument("--no-cards", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    registry = get_taxonomy_registry()
    if args.command != "v0_to_v1":
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 2

    dry_run = not args.apply
    print(
        f"Migration v0 → v1 (dry_run={dry_run}, setup_job={args.setup_job_id})"
    )

    section_report = None
    card_report = None

    if not args.no_sections:
        adapter = _RepoAdapter(_parsed_section_repo, args.setup_job_id)
        section_report = migrate_sections(
            adapter, registry=registry, dry_run=dry_run
        )
        _print_report("Sections", section_report)

    if not args.no_cards:
        cards = _card_registry.list_all() if hasattr(_card_registry, "list_all") else []
        sections = list(_parsed_section_repo.list_all())
        sections_by_id = {s.section_id: s for s in sections}
        card_report = migrate_cards(
            cards,
            sections_by_id=sections_by_id,
            registry=registry,
            dry_run=dry_run,
        )
        _print_report("RAGCards", card_report)

    has_errors = (
        bool(section_report and section_report.errors)
        or bool(card_report and card_report.errors)
    )
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
