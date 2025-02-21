import inspect
import sqlite3
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Sequence, Type

try:
    import pyathena
except ImportError:
    pyathena = None
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None
try:
    import pymysql
    import pymysql.cursors
except ImportError:
    pymysql = None


class ProviderFactory:
    _providers: dict[str, Type["Provider"]] = {}

    @classmethod
    def create_provider(
        cls,
        provider_type: str,
        provider_config: dict[str, Any],
    ) -> "Provider":
        if provider_type not in cls._providers:
            raise ValueError(
                f"Unknown provider type: {provider_type}. "
                f"Available providers: {list(cls._providers.keys())}"
            )

        return cls._providers[provider_type](provider_config)

    @classmethod
    def register_provider(cls, name: str, provider_class: Type["Provider"]) -> None:
        if not issubclass(provider_class, Provider):
            raise TypeError(
                f"Class {provider_class.__name__} must inherit from Provider"
            )
        cls._providers[name] = provider_class


class Provider(ABC):
    # Class variable to store provider metadata
    provider_name: ClassVar[str]

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Automatically register any subclass with the ProviderFactory."""
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        if cls.provider_name is None:
            raise ValueError(f"Subclass {cls.__name__} must define provider_name")
        ProviderFactory.register_provider(cls.provider_name, cls)

    @staticmethod
    def _format_import_error(module: str, extra: str):
        return ImportError(
            f"Missing required dependency: '{module}'.\n"
            f"Install it with: pip install aqueductus[{extra}]"
        )

    @staticmethod
    def _format_query_error(
        provider_name: str, query: str, error: Exception
    ) -> RuntimeError:
        return RuntimeError(
            f"Failed to execute {provider_name} query: {str(error)}\nQuery: {query}"
        )

    @staticmethod
    def _format_connection_error(
        provider_name: str, error: Exception
    ) -> ConnectionError:
        return ConnectionError(f"Failed to connect to {provider_name}: {str(error)}")

    @abstractmethod
    def __init__(self, config: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def execute_query(self, query: str) -> Sequence[dict[str, Any]]:
        pass


class AthenaProvider(Provider):
    provider_name = "athena"

    def __init__(self, config: dict[str, Any]):
        if pyathena is None:
            raise self._format_import_error("pyathena", "athena")
        try:
            self.conn = pyathena.connect(
                region_name=config["region"],
                aws_access_key_id=config["aws_access_key_id"],
                aws_secret_access_key=config["aws_secret_access_key"],
                work_group=config["work_group"],
            ).cursor()
        except Exception as e:
            raise self._format_connection_error("Athena", e) from e

    def execute_query(self, query: str) -> Sequence[dict[str, Any]]:
        try:
            self.conn.execute(query)
            columns = [col[0] for col in self.conn.description]  # type: ignore[union-attr]
            return [dict(zip(columns, row)) for row in self.conn.fetchall()]
        except Exception as e:
            raise self._format_query_error("Athena", query, e) from e


class MySQLProvider(Provider):
    provider_name = "mysql"

    def __init__(self, config: dict[str, Any]):
        if pymysql is None:
            raise self._format_import_error("pymysql", "mysql")
        try:
            self.conn = pymysql.connect(
                host=config["host"],
                user=config["user"],
                password=config["password"],
                port=config["port"],
                database=config["database"],
                cursorclass=pymysql.cursors.DictCursor,
            )
        except Exception as e:
            raise self._format_connection_error("MySQL", e) from e

    def execute_query(self, query: str) -> Sequence[dict[str, Any]]:
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            raise self._format_query_error("MySQL", query, e) from e


class SQLiteProvider(Provider):
    provider_name = "sqlite"

    def __init__(self, config: dict[str, Any]):
        try:
            self.conn = sqlite3.connect(config["database_path"])
            self.conn.row_factory = sqlite3.Row
        except Exception as e:
            raise self._format_connection_error("SQLite", e) from e

    def execute_query(self, query: str) -> Sequence[dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()
        except Exception as e:
            raise self._format_query_error("SQLite", query, e) from e
        finally:
            cursor.close()


class PostgreSQLProvider(Provider):
    provider_name = "postgresql"

    def __init__(self, config: dict[str, Any]):
        if psycopg2 is None:
            raise self._format_import_error("psycopg2", "postgresql")
        try:
            self.conn = psycopg2.connect(
                host=config["host"],
                user=config["user"],
                password=config["password"],
                port=config["port"],
                database=config["database"],
            )
        except Exception as e:
            raise self._format_connection_error("PostgreSQL", e) from e

    def execute_query(self, query: str) -> Sequence[dict[str, Any]]:
        try:
            with self.conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            raise self._format_query_error("PostgreSQL", query, e) from e
