from abc import ABC, abstractmethod
from typing import Any, Type

import sqlalchemy as sa
from pyathena import connect


class DataProvider(ABC):
    @abstractmethod
    def __init__(self, config: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def execute_query(self, query: str) -> list[dict[str, Any]]:
        pass


class AthenaProvider(DataProvider):
    def __init__(self, config: dict[str, Any]):
        try:
            self.conn = connect(
                region_name=config["region"],
                aws_access_key_id=config["aws_access_key_id"],
                aws_secret_access_key=config["aws_secret_access_key"],
                work_group=config["work_group"],
            ).cursor()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Athena: {str(e)}") from e

    def execute_query(self, query: str) -> list[dict[str, Any]]:
        try:
            self.conn.execute(query)
            columns = [col[0] for col in self.conn.description]
            return [dict(zip(columns, row)) for row in self.conn.fetchall()]
        except Exception as e:
            raise RuntimeError(
                f"Failed to execute Athena query: {str(e)}\nQuery: {query}"
            ) from e


class MySQLProvider(DataProvider):
    def __init__(self, config: dict[str, Any]):
        try:
            self.engine = sa.create_engine(
                f"mysql+pymysql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
            )
        except Exception as e:
            raise ConnectionError(f"Failed to create MySQL connection: {str(e)}") from e

    def execute_query(self, query: str) -> list[dict[str, Any]]:
        try:
            with self.engine.connect() as conn:
                result = conn.execute(sa.text(query))
                return [dict(row._mapping) for row in result]
        except sa.exc.SQLAlchemyError as e:
            raise RuntimeError(
                f"Failed to execute MySQL query: {str(e)}\nQuery: {query}"
            ) from e


class ProviderFactory:
    provider_mapping: dict[str, Type[DataProvider]] = {
        "athena": AthenaProvider,
        "mysql": MySQLProvider,
    }

    @classmethod
    def create_provider(
        cls,
        provider_type: str,
        provider_config: dict[str, Any],
    ) -> DataProvider:
        if provider_type not in cls.provider_mapping:
            raise ValueError(f"Unknown test type: {provider_type}")
        return cls.provider_mapping[provider_type](provider_config)
