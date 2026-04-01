import argparse


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Local search engine")
    parser.add_argument("--path", help="Root directory")
    parser.add_argument("--print", action="store_true", dest="print_paths", help="Print file paths")
    parser.add_argument("--md", action="store_true", help="Print metadata")
    return parser.parse_args(argv)
