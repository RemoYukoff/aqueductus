import json
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import ClassVar, Type

from aqueductus.runner import Test


class ReporterFactory:
    # TODO: Figure out how we can load the custom reporters before the main call
    # or click will throw an error when using custom reporters
    # we could load from reporters.py on the user dir automatically maybe?
    # or allow the user to set wich file will load their reporters
    _reporters: dict[str, Type["Reporter"]] = {}

    @classmethod
    def register_reporter(cls, name: str, reporter_class: Type["Reporter"]) -> None:
        if not issubclass(reporter_class, Reporter):
            raise TypeError(
                f"Class {reporter_class.__name__} must inherit from Reporter"
            )
        cls._reporters[name] = reporter_class

    @classmethod
    def create_reporter(cls, reporter_type: str) -> "Reporter":
        if reporter_type not in cls._reporters:
            raise ValueError(
                f"Unknown reporter format: {reporter_type}. "
                f"Available formats: {list(cls._reporters.keys())}"
            )
        return cls._reporters[reporter_type]()

    @classmethod
    def list_available_reporters(cls) -> list[str]:
        return list(cls._reporters.keys())


class Reporter(ABC):
    # Class variable to store reporter metadata
    reporter_name: ClassVar[str]

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Automatically register any subclass with the ReporterFactory."""
        super().__init_subclass__(**kwargs)
        if cls.reporter_name is None:
            raise ValueError(f"Subclass {cls.__name__} must define reporter_name")
        ReporterFactory.register_reporter(cls.reporter_name, cls)

    @abstractmethod
    def generate_report(self, tests: list[Test]) -> None:
        pass


class ConsoleReporter(Reporter):
    reporter_name = "console"

    def generate_report(self, tests: list[Test]) -> None:
        for test in tests:
            print(f"Test '{test.name}':")
            for result in test.results:
                print(
                    f"  Test '{result['name']}' [{result['time']}s]: "
                    f"{'PASSED' if result['passed'] else f'FAILED: {result["message"]}'}"
                )
                if not result["passed"]:
                    print(f"    Details: {json.dumps(result['details'], indent=2)}")
            print()


class JsonReporter(Reporter):
    reporter_name = "json"

    def generate_report(self, tests: list[Test]) -> None:
        with open("report.json", "w+") as f:
            json.dump([{test.name: test.results for test in tests}], f, indent=2)


class JUnitReporter(Reporter):
    reporter_name = "junit"

    def generate_report(self, tests: list[Test]) -> None:
        root_suite = ET.Element("testsuite", name="Data Test", tests=str(len(tests)))
        for test in tests:
            testsuite = ET.SubElement(root_suite, "testsuite", name=test.name)
            for result in test.results:
                testcase = ET.SubElement(
                    testsuite,
                    "testcase",
                    name=result["name"],
                    time=f"{result['time']:.3f}",
                )
                if not result["passed"]:
                    failure = ET.SubElement(
                        testcase, "failure", message=result["message"]
                    )
                    failure.text = str(result["details"])
        with open("junit.xml", "w+") as f:
            f.write(ET.tostring(root_suite, encoding="unicode"))


class MarkdownReporter(Reporter):
    reporter_name = "markdown"

    def generate_report(self, tests: list[Test]) -> None:
        report = "# Test Results\n\n"
        for test in tests:
            report += f"## {test.name}\n"
            report += f"**Query**: `{test.query}`\n\n"
            for result in test.results:
                status = "✅ PASSED" if result["passed"] else "❌ FAILED"
                report += f"- **{result["name"]}**: {status}\n"
                if not result["passed"]:
                    report += f"  ```\n  {result["details"]}\n  ```\n"
            report += "\n"
        with open("report.md", "w+") as f:
            f.write(report)
