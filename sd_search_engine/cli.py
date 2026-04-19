import argparse


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Local search engine")
    parser.add_argument("--path", help="Root directory")
    parser.add_argument("--print", action="store_true", dest="print_paths", help="Print file paths")
    parser.add_argument("--md", action="store_true", help="Print metadata")
    parser.add_argument(
        "--rank",
        default="relevance",
        choices=["relevance", "alphabetical", "date-accessed"],
        help="Ranking strategy for displaying results",
    )
    return parser.parse_args(argv)
