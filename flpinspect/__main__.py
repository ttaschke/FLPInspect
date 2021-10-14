import argparse

from .constants import HTIP_MAX, EP_MAX
from .inspector import FLPInspector
from .treeview import Treeview


def main():
    arg_parser = argparse.ArgumentParser(prog="flpinspect", description=__doc__)
    arg_parser.add_argument("--flp", help="The FLP to open in event viewer.")
    arg_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Display verbose logs. Takes significantly more time to parse",
    )
    arg_parser.add_argument(
        "--allow-unsafe",
        action="store_true",
        help=f"This will show tooltips for text of length more than {HTIP_MAX} "
        "and not show a warning when trying to edit cells containing text of "
        f"more than {EP_MAX} characters",
    )
    args = arg_parser.parse_args()
    if args.allow_unsafe:
        Treeview.allow_unsafe = True
    FLPInspector(args.flp, args.verbose)


if __name__ == "__main__":
    main()
