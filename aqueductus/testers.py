import csv
import re
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Type, TypedDict
import inspect
from aqueductus.providers import Provider
from pathlib import Path
import importlib.util


class TestFactory:
    _tests: dict[str, Type["DataTest"]] = {}

    @classmethod
    def load_custom_testers(cls, file_path: str = "testers.py"):
        path = Path(file_path)

        if path.is_file() and path.suffix == ".py":
            module_name = path.stem
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

    @classmethod
    def create_test(
        cls,
        test_type: str,
        test_config: Any,
        query_results: list[dict[str, Any]],
        providers: dict[str, Provider],
    ) -> "DataTest":
        if test_type not in cls._tests:
            raise ValueError(
                f"Unknown test type: {test_type}. "
                f"Available formats: {list(cls._tests.keys())}"
            )
        return cls._tests[test_type](
            query_results=query_results, config=test_config, providers=providers
        )

    @classmethod
    def register_test(cls, name: str, test_class: Type["DataTest"]) -> None:
        if not issubclass(test_class, DataTest):
            raise TypeError(f"Class {test_class.__name__} must inherit from DataTest")
        cls._tests[name] = test_class

    @classmethod
    def list_available_tests(cls) -> list[str]:
        return list(cls._tests.keys())


class RowLoader(ABC):
    @abstractmethod
    def load_rows(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        pass


class CsvRowLoader(RowLoader):
    def load_rows(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        with open(config["path"], mode="r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                rows.append(row)
        return rows


class ProviderRowLoader(RowLoader):
    def __init__(self, providers: dict[str, Provider]):
        self.providers = providers

    def load_rows(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        provider = self.providers[config["provider"]]
        result = provider.execute_query(config["query"])

        column_map = config.get("map", {})
        return [{column_map.get(k, k): v for k, v in row.items()} for row in result]


class InlineRowLoader(RowLoader):
    def load_rows(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return config["rows"]


class RowLoaderFactory:
    # TODO: Should we move this to a factory and implement the same logic we have for custom
    # reporters, providers, etc.?
    def __init__(self, providers: dict[str, Provider]):
        self._loaders = {
            "csv": CsvRowLoader(),
            "provider": ProviderRowLoader(providers),
            "inline": InlineRowLoader(),
        }

    def get_loader(self, source: str) -> RowLoader:
        if source not in self._loaders:
            raise ValueError(f"Unknown source type: {source}")
        return self._loaders[source]


class TestResultCore(TypedDict):
    passed: bool
    message: str
    details: dict[str, Any]


class TestResult(TestResultCore):
    name: str
    time: float


class DataTest(ABC):
    test_name: ClassVar[str]

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Automatically register any subclass with the TestFactory."""
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        if cls.test_name is None:
            raise ValueError(f"Subclass {cls.__name__} must define test_name")
        TestFactory.register_test(cls.test_name, cls)

    def __init__(
        self,
        query_results: list[dict[str, Any]],
        config: Any,
        providers: dict[str, Provider],
    ):
        self.query_results = query_results
        self.config = config
        self.providers = providers

    @abstractmethod
    def _run_test(self) -> TestResultCore:
        pass

    def run(self) -> TestResult:
        start_time = time.time()
        result = self._run_test()
        end_time = time.time()
        return {
            "name": self.test_name,
            "passed": result["passed"],
            "message": result["message"],
            "details": result["details"],
            "time": end_time - start_time,
        }


class BaseRowTest(DataTest, ABC):
    def __init__(
        self,
        query_results: list[dict[str, Any]],
        config: Any,
        providers: dict[str, Provider],
    ):
        super().__init__(query_results, config, providers)
        source = config.get("source", "inline")
        loader = RowLoaderFactory(providers).get_loader(source)
        rows = loader.load_rows(config)
        self.ignore_columns = set(config.get("ignore_columns", []))
        self.actual_rows = [
            {k: v for k, v in row.items() if k not in self.ignore_columns}
            for row in self.query_results
        ]
        self.config_rows = [
            {k: v for k, v in row.items() if k not in self.ignore_columns}
            for row in rows
        ]

    def _compare_values(self, expected: dict[str, Any] | Any, actual: Any) -> bool:
        # Handle simple exact match case
        if not isinstance(expected, dict):
            return expected == actual

        # TODO: Should we move this to a factory and implement the same logic we have for custom
        # reporters, providers, etc.?
        # Handle comparison operators
        operator, value = next(iter(expected.items()))
        match operator:
            case "less_than":
                try:
                    return actual < float(value)
                except (ValueError, TypeError):
                    return False
            case "greater_than":
                try:
                    return actual > float(value)
                except (ValueError, TypeError):
                    return False
            case "regex":
                try:
                    return bool(re.match(str(value), str(actual)))
                except (re.error, TypeError):
                    return False
            case "equals":
                return actual == value
            case _:
                raise ValueError(f"Unknown comparison operator: {operator}")

    def _row_matches(self, expected_row: dict, actual_row: dict) -> bool:
        if set(actual_row.keys()) != set(expected_row.keys()):
            return False

        return all(
            self._compare_values(expected_row[k], actual_row[k])
            for k in expected_row.keys()
        )

    def row_contained(self, row: dict, row_list: list[dict]) -> bool:
        return any(self._row_matches(row, other_row) for other_row in row_list)


class ContainsRowsTest(BaseRowTest):
    test_name = "contains_rows"

    def _run_test(self) -> TestResultCore:
        missing = [
            row
            for row in self.config_rows
            if not self.row_contained(row, self.actual_rows)
        ]
        passed = not missing
        message = (
            "All expected rows were found in the actual results."
            if passed
            else f"Missing {len(missing)} expected rows."
        )
        details = {
            "missing_rows": missing,
            "total_expected": len(self.config_rows),
            "total_actual": len(self.query_results),
            "ignored_columns": list(self.ignore_columns),
        }

        return {
            "passed": passed,
            "message": message,
            "details": details,
        }


class NotContainsRowsTest(BaseRowTest):
    test_name = "not_contains_rows"

    def _run_test(self) -> TestResultCore:
        found = [
            row for row in self.config_rows if self.row_contained(row, self.actual_rows)
        ]

        passed = not found
        message = (
            "No unexpected rows were found in the actual results."
            if passed
            else f"Found {len(found)} unexpected rows."
        )
        details = {
            "found_rows": found,
            "total_unexpected": len(self.config_rows),
            "total_actual": len(self.query_results),
            "ignored_columns": list(self.ignore_columns),
        }
        return {
            "passed": passed,
            "message": message,
            "details": details,
        }


class RowCountTest(DataTest):
    test_name = "row_count"

    def _run_test(self) -> TestResultCore:
        expected_count = self.config
        actual_count = len(self.query_results)
        passed = actual_count == expected_count
        message = (
            f"Row count matches: {actual_count} == {expected_count}"
            if passed
            else f"Row count mismatch: expected {expected_count}, got {actual_count}"
        )
        details = {
            "actual_count": actual_count,
            "expected_count": expected_count,
        }
        return {
            "passed": passed,
            "message": message,
            "details": details,
        }


class ColumnsExistsTest(DataTest):
    test_name = "columns_exists"

    def _run_test(self) -> TestResultCore:
        columns = set(self.query_results[0].keys())
        expected_columns = set(self.config)
        missing = expected_columns - columns
        passed = not missing
        message = (
            "All expected columns exist in the results."
            if passed
            else f"Missing {len(missing)} expected columns."
        )
        details = {
            "missing_columns": list(missing),
            "expected_columns": list(expected_columns),
            "actual_columns": list(columns),
        }
        return {
            "passed": passed,
            "message": message,
            "details": details,
        }


class ColumnRatioTest(DataTest):
    test_name = "column_ratio"

    def _run_test(self) -> TestResultCore:
        configs = self.config if isinstance(self.config, list) else [self.config]
        total_rows = len(self.query_results)
        results = []
        for config in configs:
            column = config["column"]
            target_value = config["value"]
            min_ratio = float(config.get("min_ratio", 0.0))
            max_ratio = float(config.get("max_ratio", 1.0))

            matching_rows = sum(
                1
                for row in self.query_results
                if (row.get(column) is None and target_value is None)
                or (
                    row.get(column) is not None
                    and target_value is not None
                    and str(row.get(column)) == str(target_value)
                )
            )
            actual_ratio = matching_rows / total_rows
            results.append(
                {
                    "column": column,
                    "value": target_value,
                    "passed": min_ratio <= actual_ratio <= max_ratio,
                    "actual_ratio": actual_ratio,
                    "min_ratio": min_ratio,
                    "max_ratio": max_ratio,
                    "matching_rows": matching_rows,
                }
            )

        passed = all(result["passed"] for result in results)
        message = (
            "All column ratios are within expected bounds."
            if passed
            else "Some column ratios are outside expected bounds."
        )
        details = {
            "total_rows": total_rows,
            "results": results,
        }

        return {
            "passed": passed,
            "message": message,
            "details": details,
        }


class AllRowsMatchTest(BaseRowTest):
    test_name = "all_rows_match"

    def _run_test(self) -> TestResultCore:
        non_matching = [
            row
            for row in self.actual_rows
            if not self.row_contained(row, self.config_rows)
        ]

        passed = not non_matching
        message = (
            "All actual rows match the expected rows."
            if passed
            else f"Found {len(non_matching)} non-matching rows."
        )
        details = {
            "non_matching_rows": non_matching,
            "expected": self.config_rows,
            "ignored_columns": list(self.ignore_columns),
        }

        return {
            "passed": passed,
            "message": message,
            "details": details,
        }
