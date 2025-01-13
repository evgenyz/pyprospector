import pathlib
import sys
import argparse
import logging

from pyprospector import Plan, Executor
logger = logging.getLogger(__name__)

def get_options():
    parser = argparse.ArgumentParser(prog='prospector')
    parser.add_argument("plan", nargs='+', type=pathlib.Path)
    parser.add_argument(
        "-r",
        "--report",
        type=pathlib.Path,
        help="Filename for the report",
        required=False,
    )
    parser.add_argument(
        "-t",
        "--test-id",
        action="store",
        help="Test ID to execute",
        required=False,
    )
    parser.add_argument(
        "-T",
        "--target",
        action="store",
        help="Target, supported: '' (default, local), 'container://container_name', 'ssh://user@hostname'",
        default="",
        required=False,
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output only JSON",
        required=False,
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, required=False)
    options = parser.parse_args()
    return options


def main():
    options = get_options()
    logging.basicConfig(level=logging.INFO - options.verbose * 10)
    logger.debug('Started')
    plan = Plan.create_from_files(options.plan)
    if options.test_id:
        plan.drop_other_tests(options.test_id)
    exe = Executor(options.target, options.json)
    plan.execute(exe)
    if options.json:
        plan.print_json_results()
    #else:
    #    plan.print_results()
    if options.report is not None:
        with open(options.report, 'w') as f:
            plan.write_report(f)
    logger.debug('Finished')
    sys.exit(0)


if __name__ == '__main__':
    main()
