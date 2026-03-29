from pathlib import Path
import os
import argparse
from datetime import datetime

parser = argparse.ArgumentParser(description='My script description')
parser.add_argument('path', help='Root directory')
parser.add_argument('--md', action='store_true', help='Print metadata')
# parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

args = parser.parse_args()
print(f'Root directory: {args.path}')

root_path = Path(args.path)
for file in root_path.rglob("*"):
    if file.is_file():
        if args.md:
            # Pretty print with metadata
            size = file.stat().st_size
            modified = datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f'{file.name:<50} | Size: {size:>10,} bytes | Modified: {modified}')
        else:
            print(file)
