# Aqueductus

A powerful Python framework for validating data quality across different data sources through SQL queries and customizable assertions. Perfect for data engineers and analysts who need to ensure data consistency and quality.

## ✨ Key Features

- 🔌 **Multiple Data Sources**

  - Amazon Athena
  - MySQL
  - PostgresSQL
  - SQLite
  - Extensible architecture for adding more providers

- 🔍 **Rich Test Types**

  - Row presence validation
  - Negative testing (absence of rows)
  - Column completeness checks
  - Value distribution analysis
  - Row count validation
  - Column existence verification
  - Pattern matching with regex support
  - Comparative operators (>, <, =)

- 🛠️ **Advanced Configuration**

  - Environment and placeholder variables support
  - Multiple data source configurations
  - CSV file integration
  - Cross-provider testing

- 📊 **Flexible Reporting**
  - Console output
  - JSON export
  - JUnit XML (CI/CD friendly)
  - Markdown reports

## 🚀 Quick Start

### Installation

To install Aqueductus with SQLite support (default):

```bash
pip install aqueductus
```

To use it with MySQL, PostgreSQL, or Athena, install the corresponding extras:

```bash
pip install aqueductus[mysql,postgresql,athena]
```

## Quick Start

1. Create a configuration file (e.g., `config.yaml`):

```yaml
providers:
  - name: my_athena
    type: athena
    config:
      region: ${AWS_REGION}
      work_group: ${AWS_WORKGROUP}
      aws_access_key_id: ${AWS_ACCESS_KEY_ID}
      aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}

tests:
  - name: user_data_validation
    provider: my_athena
    query: >
      SELECT user_id, status
      FROM <<table>>
      WHERE created_date = <<expected_date>>

    # Verify specific rows exist
    contains_rows:
      source: inline
      rows:
        - column1: "value1"
          column2: "value2"
      ignore_columns:
        - timestamp

    # Verify column completeness
    column_ratio:
      - column: status
        value: "active"
        min_ratio: 0.95
```

2. Run the tests:

```bash
aqueductus config.yaml
```

## 🛠️ Using Placeholders

Placeholders allow you to dynamically replace certain parts of your queries or configuration files with values defined in your environment.

### How It Works

1. **Define Placeholders in Your YAML File:**
   In your YAML file (or any file you want to use), you can use placeholders in the format `<<placeholder>>`. For example:

   ```yaml
   query: "SELECT * FROM <<table_name>> WHERE <<column_name>> = 'some_value';"
   ```

2. **Define the Corresponding Values in `environment.py`:**
   In the `environment.py` file, define a dictionary called `PLACEHOLDER` where you map each placeholder to its corresponding value. For example:

   ```python
   PLACEHOLDER = {
       "table_name": "users",
       "column_name": "id"
   }
   ```

3. **Aqueductus Automatically Replaces Placeholders:**
   When Aqueductus processes the YAML file, it will automatically replace any `<<placeholder>>` with the value defined in the `PLACEHOLDER` dictionary from `environment.py`. In this case, the query will be replaced like so:

   ```yaml
   query: "SELECT * FROM users WHERE id = 'some_value';"
   ```

This allows you to easily reuse queries or configurations with different values based on your environment or specific use case.

## 📚 Test Types

### 1. Contains Rows

Verifies that specific rows exist in the query results:

```yaml
contains_rows:
  source: inline
  rows:
    - column1: "value1"
      column2: "value2"
  ignore_columns:
    - timestamp
```

### 2. Not Contains Rows

Ensures specific rows do not exist:

```yaml
not_contains_rows:
  rows:
    - column1: "invalid"
      column2: "invalid"
```

### 3. Column Ratio

Validates the ratio of values in a column:

```yaml
column_ratio:
  - column: status
    value: "active"
    min_ratio: 0.95
    max_ratio: 1.0
```

### 4. Row Count

Verifies the exact number of rows:

```yaml
row_count: 100
```

### 5. Columns Exist

Ensures required columns are present:

```yaml
columns_exists:
  - column1
  - column2
```

## 🔄 Data Sources

### CSV Integration

Load test data from CSV files:

```yaml
contains_rows:
  source: csv
  path: tests/expected_data.csv
```

### Cross-Provider Testing

Compare data across different providers:

```yaml
contains_rows:
  source: provider
  provider: other_athena
  query: SELECT * FROM reference_table
  map: # Optional column mapping
    source_col: target_col
```

## 📝 Output Formats

The framework supports multiple output formats:

```bash
# Single format
aqueductus config.yaml --format json

# Multiple formats
aqueductus config.yaml --format console,json,junit
```

Available formats:

- `console`: Human-readable console output
- `json`: JSON file output
- `junit`: JUnit XML for CI/CD integration
- `markdown`: Markdown report

## 🛠️ Development

By default, Aqueductus searches for `providers.py`, `testers.py`, and `reporters.py` files in the root directory. Each file will automatically detect and load subclasses for the corresponding provider, test type, or reporter, making it easy to add new components without additional configuration.

### Adding a New Provider

Reference to provider implementation:

```
class DataProvider(ABC):
    @abstractmethod
    def __init__(self, config: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def execute_query(self, query: str) -> list[dict[str, Any]]:
        pass

```

### Adding a New Test Type

Reference to test type implementation:

```
class DataTest(ABC):
    def __init__(
        self,
        query_results: list[dict[str, Any]],
        config: Any,
        providers: dict[str, DataProvider],
    ):
        self.query_results = query_results
        self.config = config
        self.providers = providers

    @abstractmethod
    def run(self) -> dict[str, Any]:
        pass

```

### Adding a New Reporter

Reference to reporter implementation:

```
class Reporter(ABC):

    @abstractmethod
    def generate_report(self, test_results: list[dict[str, Any]]) -> None:
        pass

```
