"""
sagecli - Command line interface for Sage data downloads.

Commands:
  login     Save your API token to ~/.sage/credentials
  download  Download uploaded files matching a query
"""
import argparse
import getpass
import re
import sys

import pandas as pd

from .auth import CREDENTIALS_PATH, PORTAL_URL, load_credentials, save_credentials
from .downloads import DEFAULT_LAYOUT, DownloadError, DownloadResponse, query_downloads

_BARE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _end_of_day(date_str):
    """Advance a bare date (YYYY-MM-DD) to the start of the next day, making --end inclusive."""
    if _BARE_DATE.match(date_str):
        next_day = pd.to_datetime(date_str) + pd.Timedelta(days=1)
        return next_day.strftime("%Y-%m-%dT%H:%M:%SZ")
    return date_str


def cmd_login(args):
    existing = load_credentials()
    if existing:
        print("Credentials already saved at {}.".format(CREDENTIALS_PATH))
        print("  username: {}".format(existing.get("username", "(not set)")))
        print("  token:    {}".format("*" * 8))
        overwrite = input("Overwrite? [y/N] ").strip().lower()
        if overwrite != "y":
            print("Aborted.")
            return

    print()
    print("To get your Sage credentials:")
    print("  1. Go to {}".format(PORTAL_URL))
    print("  2. Sign in and navigate to your Access Credentials page")
    print("  3. Copy your username and access token")
    print()

    username = input("Username: ").strip()
    if not username:
        print("Error: username cannot be empty.", file=sys.stderr)
        sys.exit(1)

    token = getpass.getpass("Access token: ").strip()
    if not token:
        print("Error: token cannot be empty.", file=sys.stderr)
        sys.exit(1)

    save_credentials(username, token)
    print("Credentials saved to {} (permissions: 600)".format(CREDENTIALS_PATH))


def cmd_download(args):
    # resolve time range
    if args.date:
        start = args.date
        end = _end_of_day(args.date)
    else:
        if not args.start:
            print("Error: --start or --date is required.", file=sys.stderr)
            sys.exit(1)
        start = args.start
        end = _end_of_day(args.end) if args.end else None

    # build filter from named flags + --filter overrides
    filter_dict = {}
    if args.task:
        filter_dict["task"] = args.task
    if args.node:
        filter_dict["node"] = args.node
    if args.filter:
        for kv in args.filter:
            if "=" not in kv:
                print("Error: invalid filter '{}', expected KEY=VALUE".format(kv), file=sys.stderr)
                sys.exit(1)
            k, v = kv.split("=", 1)
            filter_dict[k.strip()] = v.strip()

    # one query per VSN, combined into a single response
    vsns = args.vsn or [None]
    dfs = []
    for vsn in vsns:
        f = dict(filter_dict)
        if vsn:
            f["vsn"] = vsn
        label = "vsn={}, ".format(vsn) if vsn else ""
        print("Querying uploads ({}{} to {})...".format(label, start, end or "now"))
        resp = query_downloads(start=start, end=end, filter=f or None)
        dfs.append(resp.df)

    combined = DownloadResponse(pd.concat(dfs, ignore_index=True))

    if len(combined) == 0:
        print("No files found.")
        return

    print("Found {} file(s).".format(len(combined)))

    if args.dry_run:
        print("\nDry run — files that would be downloaded:")
        for record in combined:
            try:
                path = record.path_for(args.dest, args.layout)
                print("  {} -> {}".format(record.url, path))
            except ValueError as e:
                print("  ERROR: {}".format(e), file=sys.stderr)
        return

    try:
        combined.download_all(
            dest=args.dest,
            layout=args.layout,
            workers=args.workers,
            skip_existing=not args.no_skip,
        )
    except DownloadError as e:
        print("\nError: {}".format(e), file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="sagecli",
        description="Sage data command line interface.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  sagecli login

  # all uploads in the last hour from node W020
  sagecli download --start -1h --vsn W020

  # all uploads on a specific day
  sagecli download --date 2026-07-01 --vsn W020 --dest ./data

  # date range (both endpoints inclusive)
  sagecli download --start 2026-07-01 --end 2026-08-10 --vsn W020 --dest ./data

  # multiple nodes
  sagecli download --date 2026-07-01 --vsn W020 W039 W023 --dest ./data

  # filter by task
  sagecli download --start -6h --vsn W020 --task imagesampler-right

  # custom layout, dry run first
  sagecli download --date 2026-07-01 --vsn W020 --layout "{date}/{vsn}/{task}/{filename}" --dry-run

layout variables:
  {vsn}       node VSN (e.g. W020)
  {node}      node ID (e.g. 000048b02d3ae27a)
  {filename}  original filename (e.g. sample.jpg)
  {date}      date as YYYY-MM-DD
  {datetime}  datetime as YYYY-MM-DDTHH-MM-SS
  {task}      task name, and any other metadata field present on the record
""",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # login
    subparsers.add_parser(
        "login",
        help="Save API token to ~/.sage/credentials",
    )

    # download
    dl = subparsers.add_parser(
        "download",
        help="Download uploaded files matching a query",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    time_group = dl.add_mutually_exclusive_group(required=True)
    time_group.add_argument(
        "--date",
        metavar="DATE",
        help="Download all files for a single day (e.g. 2026-07-01).",
    )
    time_group.add_argument(
        "--start",
        metavar="TIME",
        help='Start of time range. Relative (e.g. "-1h", "-7d") or absolute (e.g. "2026-07-01" or "2026-07-01T12:00:00Z").',
    )

    dl.add_argument(
        "--end",
        metavar="TIME",
        help="End of time range. Same formats as --start. Bare dates are treated as end of that day. Default: now.",
    )
    dl.add_argument(
        "--vsn",
        nargs="+",
        metavar="VSN",
        help="Node VSN(s) to download from (e.g. --vsn W020 or --vsn W020 W021 W039).",
    )
    dl.add_argument(
        "--task",
        metavar="TASK",
        help="Filter by task name (e.g. imagesampler-right).",
    )
    dl.add_argument(
        "--node",
        metavar="NODE",
        help="Filter by node ID.",
    )
    dl.add_argument(
        "--filter",
        action="append",
        metavar="KEY=VALUE",
        help="Additional metadata filter (repeatable). For fields not covered by named flags.",
    )
    dl.add_argument(
        "--dest",
        default=".",
        metavar="DIR",
        help="Output directory. Default: current directory.",
    )
    dl.add_argument(
        "--layout",
        default=DEFAULT_LAYOUT,
        metavar="TEMPLATE",
        help='File layout template. Default: "{vsn}/{filename}". See layout variables above.',
    )
    dl.add_argument(
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Concurrent downloads. Default: 4.",
    )
    dl.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be downloaded without downloading.",
    )
    dl.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-download files that already exist.",
    )

    args = parser.parse_args()

    if args.command == "login":
        cmd_login(args)
    elif args.command == "download":
        cmd_download(args)


if __name__ == "__main__":
    main()
