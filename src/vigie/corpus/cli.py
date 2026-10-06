"""`vigie-ingest`: download, check against the lock, parse, write one JSONL per regulation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from vigie.config import Settings, get_settings
from vigie.corpus.fetch import CellarClient, FetchError
from vigie.corpus.jsonl import write_chunks
from vigie.corpus.lock import (
    CorpusLock,
    LockEntry,
    LockMismatchError,
    read_lock,
    sha256_hex,
    verify,
    write_lock,
)
from vigie.corpus.models import Chunk
from vigie.corpus.parse import article_numbers, parse_regulation
from vigie.corpus.remote import RemoteCorpusError, fetch_published_corpus
from vigie.corpus.sources import REGULATIONS, Regulation, get_regulation

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


@dataclass(frozen=True)
class Report:
    regulation: Regulation
    chunks: list[Chunk]
    sha256: str | None

    def line(self) -> str:
        annexes = len({c.article for c in self.chunks if c.kind == "annex"})
        digest = self.sha256[:12] if self.sha256 else "published-jsonl"
        return (
            f"{self.regulation.code:<6} {self.regulation.celex}  "
            f"articles={len(article_numbers(self.chunks)):<4} annexes={annexes:<3} "
            f"chunks={len(self.chunks):<4} sha256={digest}"
        )


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vigie-ingest", description="Build the Vigie corpus from the official EUR-Lex texts."
    )
    parser.add_argument("--out", type=Path, default=settings.corpus_dir)
    parser.add_argument("--lock", type=Path, default=settings.corpus_lock_path)
    parser.add_argument(
        "--only", action="append", metavar="CODE", help="limit to one regulation (repeatable)"
    )
    parser.add_argument("--recitals", action="store_true", help="also index the recitals")
    parser.add_argument(
        "--update-lock",
        action="store_true",
        help="record what was downloaded in the lock file instead of checking against it",
    )
    parser.add_argument(
        "--from-url", metavar="URL", help="read a published corpus JSONL instead of Cellar"
    )
    return parser


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    args = build_parser(settings).parse_args(argv)
    try:
        selected = [get_regulation(code) for code in args.only] if args.only else list(REGULATIONS)
    except KeyError as exc:
        print(f"error: {exc.args[0]}", file=sys.stderr)
        return EXIT_USAGE
    if args.from_url and args.update_lock:
        print("error: a published corpus cannot rewrite the lock file", file=sys.stderr)
        return EXIT_USAGE
    lock = read_lock(args.lock) if args.lock.is_file() else None
    if lock is None and not args.update_lock:
        print(f"error: {args.lock} is missing, run once with --update-lock", file=sys.stderr)
        return EXIT_USAGE
    try:
        if args.from_url:
            reports = _from_published(args.from_url, selected, settings, lock or CorpusLock())
        else:
            reports = _from_cellar(selected, settings, lock, args)
    except (FetchError, LockMismatchError, RemoteCorpusError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED
    for report in reports:
        write_chunks(args.out / f"{report.regulation.code}.jsonl", report.chunks)
        print(report.line())
    return EXIT_OK


def _from_cellar(
    selected: list[Regulation],
    settings: Settings,
    lock: CorpusLock | None,
    args: argparse.Namespace,
) -> list[Report]:
    client = CellarClient(settings)
    updated = CorpusLock(texts=dict(lock.texts) if lock else {})
    reports: list[Report] = []
    try:
        for regulation in selected:
            xhtml = client.fetch(regulation)
            digest = sha256_hex(xhtml)
            pinned = updated.texts.get(regulation.code)
            # When checking, the date shown next to citations is the one the lock vouches
            # for, not the day this machine happened to refill its cache.
            if pinned is not None and not args.update_lock:
                downloaded_at = pinned.downloaded_at
            else:
                downloaded_at = _file_date(client.cache_path(regulation))
            chunks = parse_regulation(
                xhtml,
                regulation,
                settings,
                retrieved_on=downloaded_at,
                include_recitals=args.recitals,
            )
            articles = len(article_numbers(chunks))
            if args.update_lock:
                updated.texts[regulation.code] = LockEntry(
                    celex=regulation.celex,
                    sha256=digest,
                    articles=articles,
                    downloaded_at=downloaded_at,
                )
            else:
                verify(
                    updated,
                    regulation.code,
                    celex=regulation.celex,
                    articles=articles,
                    sha256=digest,
                )
            reports.append(Report(regulation, chunks, digest))
    finally:
        client.close()
    if args.update_lock:
        write_lock(args.lock, updated)
    return reports


def _from_published(
    url: str, selected: list[Regulation], settings: Settings, lock: CorpusLock
) -> list[Report]:
    chunks = fetch_published_corpus(url, settings)
    reports: list[Report] = []
    for regulation in selected:
        own = [c for c in chunks if c.regulation == regulation.code]
        verify(
            lock,
            regulation.code,
            celex=regulation.celex,
            articles=len(article_numbers(own)),
            sha256=None,
        )
        reports.append(Report(regulation, own, None))
    return reports


def _file_date(path: Path) -> str:
    """The day the XHTML actually landed on disk, which is what a citation should show."""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date().isoformat()
