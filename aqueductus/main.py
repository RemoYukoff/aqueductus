import sys

import click

from aqueductus.reporters import ReporterFactory
from aqueductus.runner import TestRunner


@click.command()
@click.argument("config_file", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    multiple=True,
    default=["console"],
    type=click.Choice(ReporterFactory.list_available_reporters()),
    help="Output format",
)
def main(config_file: tuple[str], format: tuple[str]) -> None:
    tester = TestRunner(config_file)
    tests = tester.run_all()
    for fmt in format:
        reporter = ReporterFactory.create_reporter(fmt)
        reporter.generate_report(tests)

    for test in tests:
        for result in test.results:
            if not result["passed"]:
                sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
