import os
import re
from datetime import datetime
from re import Match, Pattern
from typing import Any, Callable

import yaml

from aqueductus.providers import DataProvider, ProviderFactory
from aqueductus.testers import TestFactory


class Test:
    def __init__(
        self,
        name: str,
        provider: DataProvider,
        query: str,
        test_configs: dict[str, Any],
        providers: dict[str, DataProvider],
    ):
        self.name = name
        self.provider = provider
        self.query = query
        self.test_configs = test_configs
        self.providers = providers

    def run(self) -> dict[str, Any]:
        query_results = self.provider.execute_query(self.query)
        results = []
        for test_type, test_config in self.test_configs.items():
            test = TestFactory.create_test(
                test_type, test_config, query_results, self.providers
            )
            results.append(
                {
                    "test_type": test_type,
                    "result": test.run(),
                }
            )

        return {"name": self.name, "query": self.query, "results": results}


class ConfigResolver:
    # Regex to match ${ENV_VAR_NAME} or $ENV_VAR_NAME
    _env_var_pattern = re.compile(r"\$\{([^}]+)}|\$(\S+)")
    # TODO: I don't think this is needed anymore or maybe we should change it and just add
    # static placeholders sections to the yamls file
    # Regex to match {{placeholder}}
    _placeholder_pattern = re.compile(r"\{\{(.+)}}")
    placeholders = {"today": datetime.today().strftime("%Y-%m-%d")}

    def __init__(self, placeholders: dict[str, Any] | None = None):
        if placeholders:
            self.placeholders.update(placeholders)

    @staticmethod
    def resolve(config: dict[str, Any]) -> dict[str, Any]:
        config = ConfigResolver._resolve_pattern(
            config,
            [
                (
                    ConfigResolver._env_var_pattern,
                    ConfigResolver._replace_env_vars,
                ),
                (
                    ConfigResolver._placeholder_pattern,
                    ConfigResolver._replace_placeholders,
                ),
            ],
        )
        return config

    @staticmethod
    def _resolve_pattern(
        config: dict[str, Any],
        pattern_resolvers: list[tuple[Pattern[str], Callable[[Match[str]], str]]],
    ) -> dict[str, Any]:
        def replace_env_vars(value: Any) -> Any:
            if isinstance(value, str):
                for pattern, replacement in pattern_resolvers:
                    value = pattern.sub(replacement, value)
                return value
            elif isinstance(value, dict):
                return {k: replace_env_vars(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_env_vars(v) for v in value]
            else:
                return value

        return replace_env_vars(config)

    @staticmethod
    def _replace_env_vars(match: Match[str]) -> str:
        env_var_name = match.group(1) or match.group(2)
        env_var_value = os.getenv(env_var_name)
        if env_var_value is None:
            raise ValueError(f"Environment variable '{env_var_name}' is not set")
        return env_var_value

    @staticmethod
    def _replace_placeholders(match: Match[str]) -> str:
        placeholder_name = match.group(1)
        placeholder_value = ConfigResolver.placeholders.get(placeholder_name)
        if placeholder_value is None:
            raise ValueError(f"There's no placeholder value for '{placeholder_name}'")
        return placeholder_value


class TestRunner:

    def __init__(
        self, config_file: tuple[str], placeholders: dict[str, Any] | None = None
    ):
        self.config_resolver = ConfigResolver(placeholders)
        self.config = self._load_config(config_file)
        self.providers = self._init_providers()
        self.tests = self._init_tests()

    def _load_config(self, config_files: tuple[str]) -> dict[str, Any]:
        merged_config = {"providers": [], "tests": []}
        for config_file in config_files:
            # TODO: Add yaml schema validation
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)
                config = self.config_resolver.resolve(config)
                if "providers" in config:
                    merged_config["providers"].extend(config["providers"])
                if "tests" in config:
                    merged_config["tests"].extend(config["tests"])
        return merged_config

    def _init_providers(self) -> dict[str, DataProvider]:
        providers = {}
        for provider_config in self.config["providers"]:
            providers[provider_config["name"]] = ProviderFactory.create_provider(
                provider_config["type"],
                provider_config["config"],
            )
        return providers

    def _init_tests(self) -> list[Test]:
        tests = []
        for test_config in self.config["tests"]:
            provider = self.providers[test_config["provider"]]
            test_specific_configs = {
                k: v for k, v in test_config.items() if k in TestFactory.test_mapping
            }
            tests.append(
                Test(
                    name=test_config["name"],
                    provider=provider,
                    query=test_config["query"],
                    test_configs=test_specific_configs,
                    providers=self.providers,
                )
            )
        return tests

    def run_all(self) -> list[dict[str, Any]]:
        return [test.run() for test in self.tests]
