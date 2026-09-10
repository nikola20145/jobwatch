"""jobwatch command-line interface.

    jobwatch add-source --ats greenhouse --token adyen --name Adyen
    jobwatch add-keyword --field title intern "software engineer"
    jobwatch seed          # ingest current postings, mark matches as seen (no alerts)
    jobwatch run           # one fetch -> ingest -> match -> alert pass
    jobwatch run --loop    # poll forever at POLL_INTERVAL_SECONDS
    jobwatch status        # row counts and pending-alert count
"""

import argparse
import logging
import sys
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobwatch.alerts.base import Alerter
from jobwatch.alerts.telegram import TelegramAlerter
from jobwatch.config import Settings
from jobwatch.db.models import KEYWORD_FIELDS, AlertSent, Keyword, Posting, Source
from jobwatch.db.session import make_engine, make_session_factory
from jobwatch.pipeline import pending_alerts, run_once

log = logging.getLogger("jobwatch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobwatch", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-source", help="register a career board to poll")
    p.add_argument("--name", required=True, help="display name, e.g. Adyen")
    p.add_argument("--ats", required=True, choices=["greenhouse", "lever"], help="ATS type")
    p.add_argument("--token", required=True, help="board token, e.g. adyen")

    p = sub.add_parser("add-keyword", help="save match terms")
    p.add_argument("--field", required=True, choices=list(KEYWORD_FIELDS))
    p.add_argument("terms", nargs="+", help="one or more terms (case-insensitive substring match)")

    sub.add_parser(
        "seed",
        help="ingest current postings and mark matches as already-seen, so only future postings alert",
    )

    p = sub.add_parser("run", help="run the fetch -> ingest -> match -> alert pipeline")
    p.add_argument("--loop", action="store_true", help="keep polling at POLL_INTERVAL_SECONDS")

    sub.add_parser("status", help="show row counts and pending alerts")

    p = sub.add_parser("serve", help="run the web dashboard and JSON API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)

    return parser


def make_alerter(settings: Settings) -> Alerter | None:
    if not settings.telegram_configured:
        log.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — alerts are disabled")
        return None
    return TelegramAlerter(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        timeout=settings.request_timeout_seconds,
    )


def cmd_add_source(session: Session, args: argparse.Namespace) -> int:
    existing = session.scalar(
        select(Source).where(Source.ats_type == args.ats, Source.board_token == args.token)
    )
    if existing:
        existing.name = args.name
        existing.enabled = True
        print(f"source already registered, refreshed: {existing.name}")
    else:
        session.add(Source(name=args.name, ats_type=args.ats, board_token=args.token))
        print(f"added source {args.name} ({args.ats}:{args.token})")
    session.commit()
    return 0


def cmd_add_keyword(session: Session, args: argparse.Namespace) -> int:
    for term in args.terms:
        term = term.strip().lower()
        if not term:
            continue
        exists = session.scalar(
            select(Keyword).where(Keyword.field == args.field, Keyword.term == term)
        )
        if exists:
            print(f"already saved: {args.field}:{term}")
            continue
        session.add(Keyword(field=args.field, term=term))
        print(f"added keyword {args.field}:{term}")
    session.commit()
    return 0


def cmd_seed(session: Session, settings: Settings) -> int:
    report = run_once(session, alerter=make_alerter(settings), suppress_alerts=True)
    print(f"seeded: {report.summary()}")
    for error in report.errors:
        print(f"  error: {error}", file=sys.stderr)
    return 1 if report.errors else 0


def cmd_run(session_factory, settings: Settings, loop: bool) -> int:
    alerter = make_alerter(settings)
    while True:
        with session_factory() as session:
            report = run_once(session, alerter=alerter)
        print(report.summary())
        for error in report.errors:
            print(f"  error: {error}", file=sys.stderr)
        if not loop:
            return 1 if report.errors else 0
        log.info("sleeping %ds", settings.poll_interval_seconds)
        time.sleep(settings.poll_interval_seconds)


def cmd_status(session: Session) -> int:
    counts = {
        "sources": session.scalar(select(func.count()).select_from(Source)),
        "postings": session.scalar(select(func.count()).select_from(Posting)),
        "keywords": session.scalar(select(func.count()).select_from(Keyword)),
        "alerts_sent": session.scalar(
            select(func.count()).select_from(AlertSent).where(~AlertSent.suppressed)
        ),
        "alerts_suppressed": session.scalar(
            select(func.count()).select_from(AlertSent).where(AlertSent.suppressed)
        ),
    }
    for name, value in counts.items():
        print(f"{name:18} {value}")
    keywords = session.scalars(select(Keyword)).all()
    pending = pending_alerts(session, keywords, "telegram") if keywords else []
    print(f"{'pending_alerts':18} {len(pending)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    args = build_parser().parse_args(argv)
    settings = Settings()
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)

    if args.command == "run":
        return cmd_run(session_factory, settings, loop=args.loop)

    if args.command == "serve":
        import uvicorn

        from jobwatch.web import create_app

        uvicorn.run(create_app(session_factory), host=args.host, port=args.port)
        return 0

    with session_factory() as session:
        if args.command == "add-source":
            return cmd_add_source(session, args)
        if args.command == "add-keyword":
            return cmd_add_keyword(session, args)
        if args.command == "seed":
            return cmd_seed(session, settings)
        if args.command == "status":
            return cmd_status(session)
    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
