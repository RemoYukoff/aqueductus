import sys

import click

from aqueductus.reporters import ReporterFactory
from aqueductus.providers import ProviderFactory
from aqueductus.testers import TestFactory
from aqueductus.runner import TestRunner
from pathlib import Path

# Allows click to show custom reporters when using --help
ReporterFactory.load_custom_reporters()


@click.command()
@click.argument("config_files", nargs=-1, required=True, type=click.Path())
@click.option(
    "--format",
    "-f",
    multiple=True,
    default=["console"],
    type=click.Choice(ReporterFactory.list_available_reporters()),
    help="Output format",
)
def main(config_files: tuple[Path], format: tuple[str]) -> None:
    ProviderFactory.load_custom_providers()
    TestFactory.load_custom_testers()

    # Expand glob patterns into a list of file paths
    all_files: set[Path] = set()
    for config_file in config_files:
        path = Path(config_file)
        if "*" in config_file or "?" in config_file or "[" in config_file:
            matched_files = list(Path.cwd().glob(config_file))
            if not matched_files:
                raise click.BadParameter(
                    f"No config files matched pattern: {config_file}"
                )
            all_files.update(matched_files)
        else:
            if not path.exists():
                raise click.BadParameter(f"Config file does not exist: {config_file}")
            all_files.add(path)

    tester = TestRunner([str(file) for file in all_files])
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
