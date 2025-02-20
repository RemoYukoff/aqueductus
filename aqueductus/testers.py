import csv
import re
from abc import ABC, abstractmethod
from typing import Any, Type

from aqueductus.providers import Provider


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


class DataTest(ABC):
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
    def run(self) -> dict[str, Any]:
        pass


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
    def run(self) -> dict[str, Any]:
        missing = [
            row
            for row in self.config_rows
            if not self.row_contained(row, self.actual_rows)
        ]

        return {
            "passed": not missing,
            "missing_rows": missing,
            "total_expected": len(self.config_rows),
            "total_actual": len(self.query_results),
            "ignored_columns": list(self.ignore_columns),
        }


class NotContainsRowsTest(BaseRowTest):
    def run(self) -> dict[str, Any]:
        found = [
            row for row in self.config_rows if self.row_contained(row, self.actual_rows)
        ]

        return {
            "passed": not found,
            "found_rows": found,
            "total_unexpected": len(self.config_rows),
            "total_actual": len(self.query_results),
            "ignored_columns": list(self.ignore_columns),
        }


class RowCountTest(DataTest):
    def run(self) -> dict[str, Any]:
        expected_count = self.config
        actual_count = len(self.query_results)
        return {
            "passed": actual_count == expected_count,
            "actual_count": actual_count,
            "expected_count": expected_count,
        }


class ColumnsExistsTest(DataTest):
    def run(self) -> dict[str, Any]:
        columns = set(self.query_results[0].keys())
        expected_columns = set(self.config)
        missing = expected_columns - columns
        return {
            "passed": not missing,
            "missing_columns": list(missing),
            "expected_columns": list(expected_columns),
            "actual_columns": list(columns),
        }


class ColumnRatioTest(DataTest):
    def run(self) -> dict[str, Any]:
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
        return {
            "passed": all(result["passed"] for result in results),
            "total_rows": total_rows,
            "results": results,
        }


class AllRowsMatchTest(BaseRowTest):
    def run(self) -> dict[str, Any]:
        non_matching = [
            row
            for row in self.actual_rows
            if not self.row_contained(row, self.config_rows)
        ]

        return {
            "passed": not non_matching,
            "non_matching_rows": non_matching,
            "expected": self.config_rows,
            "ignored_columns": list(self.ignore_columns),
        }


class TestFactory:
    test_mapping: dict[str, Type[DataTest]] = {
        "contains_rows": ContainsRowsTest,
        "not_contains_rows": NotContainsRowsTest,
        "row_count": RowCountTest,
        "columns_exists": ColumnsExistsTest,
        "column_ratio": ColumnRatioTest,
        "all_rows_match": AllRowsMatchTest,
    }

    @classmethod
    def create_test(
        cls,
        test_type: str,
        test_config: Any,
        query_results: list[dict[str, Any]],
        providers: dict[str, Provider],
    ) -> DataTest:
        if test_type not in cls.test_mapping:
            raise ValueError(f"Unknown test type: {test_type}")
        return cls.test_mapping[test_type](
            query_results=query_results, config=test_config, providers=providers
        )
