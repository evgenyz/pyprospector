import pathlib
import sys
import argparse
import logging

from pyprospector import Plan, Executor
logger = logging.getLogger(__name__)

def get_options():
    parser = argparse.ArgumentParser(prog='prospector')
    parser.add_argument("plan", type=pathlib.Path)
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
    """
    parser.add_argument("-v", action="count", default=0)
    """
    options = parser.parse_args()
    return options


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info('Started')
    options = get_options()
    with open(options.plan, 'r') as f:
        plan = Plan.create_from_file(f)
    if options.test_id:
        plan.drop_other_tests(options.test_id)
    exe = Executor()
    plan.execute(exe)
    #plan.print_results()
    plan.print_json_results()
    if options.report is not None:
        with open(options.report, 'w') as f:
            plan.write_report(f)
    logger.info('Finished')
    sys.exit(0)


if __name__ == '__main__':
    main()
