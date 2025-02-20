import json
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Any, Type, ClassVar


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
    reporter_name: ClassVar[str] = None

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Automatically register any subclass with the ReporterFactory."""
        super().__init_subclass__(**kwargs)
        if cls.reporter_name is not None:
            ReporterFactory.register_reporter(cls.reporter_name, cls)

    @abstractmethod
    def generate_report(self, test_results: list[dict[str, Any]]) -> None:
        pass


class ConsoleReporter(Reporter):
    reporter_name = "console"

    def generate_report(self, test_results: list[dict[str, Any]]) -> None:
        for test_result in test_results:
            print(f"Test '{test_result['name']}':")
            for result in test_result["results"]:
                print(
                    f"  Test '{result['test_type']}': "
                    f"{'PASSED' if result['result']['passed'] else 'FAILED'}"
                )
                if not result["result"]["passed"]:
                    print(f"    Details: {json.dumps(result['result'], indent=2)}")
            print()


class JsonReporter(Reporter):
    reporter_name = "json"

    def generate_report(self, test_results: list[dict[str, Any]]) -> None:
        with open("report.json", "w+") as f:
            json.dump(test_results, f, indent=2)


class JUnitReporter(Reporter):
    reporter_name = "junit"

    def generate_report(self, test_results: list[dict[str, Any]]) -> None:
        # TODO: Generated with AI, needs to be refined to actually use the JUnit format,
        # should use junit library
        testsuites = ET.Element("testsuites")
        for test_result in test_results:
            testsuite = ET.SubElement(testsuites, "testsuite", name=test_result["name"])
            for result in test_result["results"]:
                testcase = ET.SubElement(
                    testsuite, "testcase", name=result["test_type"]
                )
                if not result["result"]["passed"]:
                    failure = ET.SubElement(testcase, "failure", message="Test failed")
                    failure.text = str(result["result"])
        with open("junit.xml", "w+") as f:
            f.write(ET.tostring(testsuites, encoding="unicode"))


class MarkdownReporter(Reporter):
    reporter_name = "markdown"

    def generate_report(self, test_results: list[dict[str, Any]]) -> None:
        report = "# Test Results\n\n"
        for test_result in test_results:
            report += f"## {test_result['name']}\n"
            report += f"**Query**: `{test_result['query']}`\n\n"
            for result in test_result["results"]:
                status = "✅ PASSED" if result["result"]["passed"] else "❌ FAILED"
                report += f"- **{result['test_type']}**: {status}\n"
                if not result["result"]["passed"]:
                    report += f"  ```\n  {result['result']}\n  ```\n"
            report += "\n"
        with open("report.md", "w+") as f:
            f.write(report)
