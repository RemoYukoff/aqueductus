import importlib.util
import os
import re
from re import Match
from typing import Any

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


class TestRunner:
    # Regex to match ${ENV_VAR_NAME} or $ENV_VAR_NAME
    _ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)}|\$(\S+)")
    # Regex to match {{placeholder}}
    _PLACEHOLDER_PATTERN = re.compile(r"\{\{(.+)}}")

    def __init__(self, config_files: tuple[str]):
        self.placeholders = self._load_placeholders()
        self.config = self._load_config(config_files)
        self.providers = self._init_providers()
        self.tests = self._init_tests()

    def _load_placeholders(self) -> dict[str, Any]:
        directory = os.getcwd()
        env_path = os.path.join(directory, "environment.py")

        if not os.path.exists(env_path):
            return {}

        # Load the module dynamically
        spec = importlib.util.spec_from_file_location("environment", env_path)
        environment = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(environment)

        # Return the PLACEHOLDERS variable if it exists
        if hasattr(environment, "PLACEHOLDERS"):
            return environment.PLACEHOLDERS

        return {}

    @staticmethod
    def _replace_env_vars_text(match: Match[str]) -> str:
        env_var_name = (match.group(1) or match.group(2)).strip()
        env_var_value = os.getenv(env_var_name)
        if env_var_value is None:
            raise ValueError(f"Environment variable '{env_var_name}' is not set")
        return env_var_value

    def _replace_placeholders_text(self, match: Match[str]) -> str:
        placeholder_name = match.group(1).strip()
        placeholder_value = self.placeholders.get(placeholder_name)
        if placeholder_value is None:
            raise ValueError(f"Placeholder variable '{placeholder_name}' is not set")
        return placeholder_value

    def _load_config(self, config_files: tuple[str]) -> dict[str, Any]:
        merged_config = {"providers": [], "tests": []}
        for config_file in config_files:
            # TODO: Add yaml schema validation
            with open(config_file, "r") as f:
                yaml_text = f.read()
                yaml_text = self._ENV_VAR_PATTERN.sub(
                    self._replace_env_vars_text, yaml_text
                )
                yaml_text = self._PLACEHOLDER_PATTERN.sub(
                    self._replace_placeholders_text, yaml_text
                )

                config = yaml.safe_load(yaml_text)
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
