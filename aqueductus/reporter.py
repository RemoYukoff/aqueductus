import json
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Any, Type


class Reporter(ABC):

    @abstractmethod
    def generate_report(self, test_results: list[dict[str, Any]]) -> None:
        pass


class ConsoleReporter(Reporter):

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

    def generate_report(self, test_results: list[dict[str, Any]]) -> None:
        with open("report.json", "w+") as f:
            json.dump(test_results, f, indent=2)


class JUnitReporter(Reporter):

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


class ReporterFactory:

    reporters: dict[str, Type[Reporter]] = {
        "console": ConsoleReporter,
        "json": JsonReporter,
        "junit": JUnitReporter,
        "markdown": MarkdownReporter,
    }

    @classmethod
    def get_reporter(cls, reporter_type: str) -> Reporter:
        if reporter_type not in cls.reporters:
            raise ValueError(
                f"Unknown reporter format: {reporter_type}. "
                f"Available formats: {list(cls.reporters.keys())}"
            )
        return cls.reporters[reporter_type]()
