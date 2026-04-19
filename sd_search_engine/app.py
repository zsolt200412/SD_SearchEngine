from .cli import parse_args
from .db import init_db
from .indexer import crawl_and_index
from .search import search_as_you_type


def run(argv=None):
    conn, cursor = init_db()
    args = parse_args(argv)
    print(f"Root directory: {args.path}")
    print(f"Ranking strategy: {args.rank}")
    crawl_and_index(cursor, conn, args.path, print_paths=args.print_paths, md=args.md)
    search_as_you_type(cursor, ranking_strategy=args.rank)
    conn.close()
