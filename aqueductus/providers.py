from abc import ABC, abstractmethod
from typing import Any, Type, ClassVar

import sqlalchemy as sa
from pyathena import connect


class ProviderFactory:
    # TODO: Figure out how we can load the custom providers before the main call
    # or the providers will not be available for use
    # we could load from providers.py on the user dir automatically maybe?
    # or allow the user to set wich file will load their providers
    _providers: dict[str, Type["Provider"]] = {}

    @classmethod
    def get_provider(
        cls,
        provider_type: str,
        provider_config: dict[str, Any],
    ) -> "Provider":
        if provider_type not in cls._providers:
            raise ValueError(
                f"Unknown provider type: {provider_type}. "
                f"Available providers: {list(cls._providers.keys())}"
            )

        return cls.provider_mapping[provider_type](provider_config)

    @classmethod
    def register_provider(cls, name: str, provider_class: Type["Provider"]) -> None:
        if not issubclass(provider_class, "Provider"):
            raise TypeError(
                f"Class {provider_class.__name__} must inherit from Provider"
            )
        cls._providers[name] = provider_class


class Provider(ABC):
    # Class variable to store provider metadata
    provider_name: ClassVar[str] = None

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Automatically register any subclass with the ProviderFactory."""
        super().__init_subclass__(**kwargs)
        if cls.provider_name is not None:
            ProviderFactory.register_provider(cls.provider_name, cls)

    @abstractmethod
    def __init__(self, config: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def execute_query(self, query: str) -> list[dict[str, Any]]:
        pass


class AthenaProvider(Provider):
    provider_name = "athena"

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


class MySQLProvider(Provider):
    provider_name = "mysql"

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
