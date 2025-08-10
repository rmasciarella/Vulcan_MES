#!/usr/bin/env python3
"""
Convert existing schema.sql into proper Alembic initial migration.
This script analyzes the schema.sql file and creates an Alembic migration
that can recreate the same database structure.
"""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchemaToMigrationConverter:
    """Converts schema.sql to Alembic migration."""

    def __init__(self, schema_file: Path, output_dir: Path):
        self.schema_file = schema_file
        self.output_dir = output_dir
        self.enums = []
        self.tables = []
        self.indexes = []
        self.functions = []
        self.triggers = []
        self.views = []

    def parse_schema(self) -> None:
        """Parse the schema.sql file and extract components."""
        logger.info(f"Parsing schema file: {self.schema_file}")

        if not self.schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_file}")

        content = self.schema_file.read_text()

        # Split content into sections
        self._extract_enums(content)
        self._extract_tables(content)
        self._extract_indexes(content)
        self._extract_functions(content)
        self._extract_triggers(content)
        self._extract_views(content)

        logger.info(
            f"Parsed: {len(self.enums)} enums, {len(self.tables)} tables, "
            f"{len(self.indexes)} indexes, {len(self.functions)} functions, "
            f"{len(self.triggers)} triggers, {len(self.views)} views"
        )

    def _extract_enums(self, content: str) -> None:
        """Extract CREATE TYPE statements for enums."""
        enum_pattern = r"CREATE TYPE\s+(\w+)\s+AS\s+ENUM\s*\((.*?)\);"
        matches = re.findall(enum_pattern, content, re.IGNORECASE | re.DOTALL)

        for name, values in matches:
            # Clean up the values
            value_list = []
            for value in values.split(","):
                clean_value = value.strip().strip("'\"")
                if clean_value:
                    value_list.append(clean_value)

            self.enums.append({"name": name, "values": value_list})

    def _extract_tables(self, content: str) -> None:
        """Extract CREATE TABLE statements."""
        # Match table creation statements
        table_pattern = r"CREATE TABLE\s+(\w+)\s*\((.*?)\);"
        matches = re.findall(table_pattern, content, re.IGNORECASE | re.DOTALL)

        for table_name, columns_def in matches:
            # Skip sample data inserts
            if "INSERT INTO" in columns_def:
                continue

            columns = self._parse_table_columns(columns_def)

            self.tables.append({"name": table_name, "columns": columns})

    def _parse_table_columns(self, columns_def: str) -> list[dict[str, Any]]:
        """Parse table column definitions."""
        columns = []

        # Split by comma but be careful with function calls and constraints
        lines = columns_def.split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("--"):
                continue

            # Check if this line is a column definition or constraint
            if (
                line.startswith("CONSTRAINT")
                or line.startswith("CHECK")
                or line.startswith("UNIQUE")
                or line.startswith("PRIMARY KEY")
                or line.startswith("FOREIGN KEY")
            ):
                # This is a table constraint, not a column
                continue

            # Remove trailing comma
            line = line.rstrip(",")

            if line:
                column_info = self._parse_column_definition(line)
                if column_info:
                    columns.append(column_info)

        return columns

    def _parse_column_definition(self, column_def: str) -> dict[str, Any] | None:
        """Parse a single column definition."""
        # Basic column pattern: name type [constraints]
        parts = column_def.strip().split()
        if len(parts) < 2:
            return None

        column_name = parts[0]
        column_type = parts[1]

        # Handle constraints
        constraints = " ".join(parts[2:])

        return {
            "name": column_name,
            "type": column_type,
            "constraints": constraints,
            "nullable": "NOT NULL" not in constraints.upper(),
            "primary_key": "PRIMARY KEY" in constraints.upper(),
            "unique": "UNIQUE" in constraints.upper(),
            "default": self._extract_default_value(constraints),
        }

    def _extract_default_value(self, constraints: str) -> str | None:
        """Extract default value from constraints."""
        default_match = re.search(
            r"DEFAULT\s+([^,\s]+(?:\s*\([^)]*\))?)", constraints, re.IGNORECASE
        )
        return default_match.group(1) if default_match else None

    def _extract_indexes(self, content: str) -> None:
        """Extract CREATE INDEX statements."""
        index_pattern = r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(\w+)\s+ON\s+(\w+)\s*\((.*?)\)(?:\s+WHERE\s+(.*?))?;"
        matches = re.findall(index_pattern, content, re.IGNORECASE | re.DOTALL)

        for index_name, table_name, columns, where_clause in matches:
            self.indexes.append(
                {
                    "name": index_name,
                    "table": table_name,
                    "columns": [col.strip() for col in columns.split(",")],
                    "unique": "UNIQUE"
                    in content[
                        content.find(index_name) - 20 : content.find(index_name)
                    ],
                    "where": where_clause.strip() if where_clause else None,
                }
            )

    def _extract_functions(self, content: str) -> None:
        """Extract CREATE FUNCTION statements."""
        function_pattern = r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(.*?)(?=CREATE|$)"
        matches = re.findall(function_pattern, content, re.IGNORECASE | re.DOTALL)

        for function_def in matches:
            # Extract function name
            name_match = re.match(r"(\w+)\s*\(", function_def.strip())
            if name_match:
                self.functions.append(
                    {"name": name_match.group(1), "definition": function_def.strip()}
                )

    def _extract_triggers(self, content: str) -> None:
        """Extract CREATE TRIGGER statements."""
        trigger_pattern = r"CREATE TRIGGER\s+(\w+).*?;"
        matches = re.findall(trigger_pattern, content, re.IGNORECASE | re.DOTALL)

        for trigger_name in matches:
            # Find full trigger definition
            trigger_start = content.find(f"CREATE TRIGGER {trigger_name}")
            trigger_end = content.find(";", trigger_start) + 1

            if trigger_start != -1 and trigger_end != -1:
                self.triggers.append(
                    {
                        "name": trigger_name,
                        "definition": content[trigger_start:trigger_end],
                    }
                )

    def _extract_views(self, content: str) -> None:
        """Extract CREATE VIEW statements."""
        view_pattern = r"CREATE VIEW\s+(\w+)\s+AS(.*?)(?=CREATE|$)"
        matches = re.findall(view_pattern, content, re.IGNORECASE | re.DOTALL)

        for view_name, view_def in matches:
            # Clean up the view definition
            view_def = view_def.strip().rstrip(";")

            self.views.append({"name": view_name, "definition": view_def})

    def generate_migration(self) -> str:
        """Generate Alembic migration code."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        revision_id = f"initial_schema_{timestamp}"

        migration_code = f'''"""Initial schema migration from schema.sql

Revision ID: {revision_id}
Revises:
Create Date: {datetime.now().isoformat()}

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '{revision_id}'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create custom types (enums)
{self._generate_enum_creation()}

    # Create tables
{self._generate_table_creation()}

    # Create indexes
{self._generate_index_creation()}

    # Create functions
{self._generate_function_creation()}

    # Create triggers
{self._generate_trigger_creation()}

    # Create views
{self._generate_view_creation()}


def downgrade() -> None:
    # Drop views
{self._generate_view_drop()}

    # Drop triggers
{self._generate_trigger_drop()}

    # Drop functions
{self._generate_function_drop()}

    # Drop indexes
{self._generate_index_drop()}

    # Drop tables
{self._generate_table_drop()}

    # Drop custom types
{self._generate_enum_drop()}
'''

        return migration_code

    def _generate_enum_creation(self) -> str:
        """Generate enum creation code."""
        code_lines = []
        for enum in self.enums:
            values = "', '".join(enum["values"])
            code_lines.append(f"    # Create {enum['name']} enum")
            code_lines.append(
                f"    op.execute(\"CREATE TYPE {enum['name']} AS ENUM ('{values}')\")"
            )
            code_lines.append("")
        return "\n".join(code_lines)

    def _generate_table_creation(self) -> str:
        """Generate table creation code."""
        code_lines = []
        for table in self.tables:
            code_lines.append(f"    # Create {table['name']} table")
            code_lines.append(f"    op.create_table('{table['name']}',")

            for column in table["columns"]:
                col_line = self._generate_column_code(column)
                code_lines.append(f"        {col_line},")

            code_lines.append("    )")
            code_lines.append("")

        return "\n".join(code_lines)

    def _generate_column_code(self, column: dict[str, Any]) -> str:
        """Generate SQLAlchemy column definition."""
        col_type = self._map_postgres_type_to_sqlalchemy(column["type"])

        params = []
        if not column["nullable"]:
            params.append("nullable=False")
        if column["primary_key"]:
            params.append("primary_key=True")
        if column["unique"]:
            params.append("unique=True")
        if column["default"]:
            params.append(f"default={repr(column['default'])}")

        params_str = ", ".join(params) if params else ""
        if params_str:
            return f"sa.Column('{column['name']}', {col_type}, {params_str})"
        else:
            return f"sa.Column('{column['name']}', {col_type})"

    def _map_postgres_type_to_sqlalchemy(self, pg_type: str) -> str:
        """Map PostgreSQL types to SQLAlchemy types."""
        type_mapping = {
            "BIGSERIAL": "sa.BigInteger()",
            "SERIAL": "sa.Integer()",
            "INTEGER": "sa.Integer()",
            "BIGINT": "sa.BigInteger()",
            "TEXT": "sa.Text()",
            "BOOLEAN": "sa.Boolean()",
            "TIMESTAMP": "sa.TIMESTAMP()",
            "DATE": "sa.Date()",
            "TIME": "sa.Time()",
            "DECIMAL": "sa.Numeric()",
        }

        # Handle VARCHAR with length
        if pg_type.startswith("VARCHAR"):
            length_match = re.search(r"VARCHAR\((\d+)\)", pg_type)
            if length_match:
                return f"sa.String({length_match.group(1)})"
            return "sa.String()"

        # Handle custom enums
        for enum in self.enums:
            if pg_type == enum["name"]:
                return f"postgresql.ENUM(name='{enum['name']}')"

        # Default mapping
        return type_mapping.get(pg_type.upper(), f"sa.String()  # TODO: Map {pg_type}")

    def _generate_index_creation(self) -> str:
        """Generate index creation code."""
        code_lines = []
        for index in self.indexes:
            columns = "', '".join(index["columns"])
            unique_param = ", unique=True" if index["unique"] else ""

            code_lines.append(f"    # Create {index['name']} index")
            if index["where"]:
                code_lines.append(
                    f"    op.execute(\"CREATE INDEX {index['name']} ON {index['table']} ({', '.join(index['columns'])}) WHERE {index['where']}\")"
                )
            else:
                code_lines.append(
                    f"    op.create_index('{index['name']}', '{index['table']}', ['{columns}']{unique_param})"
                )
            code_lines.append("")

        return "\n".join(code_lines)

    def _generate_function_creation(self) -> str:
        """Generate function creation code."""
        code_lines = []
        for function in self.functions:
            # Escape quotes in function definition
            definition = function["definition"].replace("'", "\\'")
            code_lines.append(f"    # Create {function['name']} function")
            code_lines.append(
                f"    op.execute('''CREATE OR REPLACE FUNCTION {definition}''')"
            )
            code_lines.append("")

        return "\n".join(code_lines)

    def _generate_trigger_creation(self) -> str:
        """Generate trigger creation code."""
        code_lines = []
        for trigger in self.triggers:
            definition = trigger["definition"].replace("'", "\\'")
            code_lines.append(f"    # Create {trigger['name']} trigger")
            code_lines.append(f"    op.execute('''{definition}''')")
            code_lines.append("")

        return "\n".join(code_lines)

    def _generate_view_creation(self) -> str:
        """Generate view creation code."""
        code_lines = []
        for view in self.views:
            definition = view["definition"].replace("'", "\\'")
            code_lines.append(f"    # Create {view['name']} view")
            code_lines.append(
                f"    op.execute('''CREATE VIEW {view['name']} AS {definition}''')"
            )
            code_lines.append("")

        return "\n".join(code_lines)

    def _generate_enum_drop(self) -> str:
        """Generate enum drop code."""
        code_lines = []
        for enum in reversed(self.enums):  # Drop in reverse order
            code_lines.append(
                f"    op.execute(\"DROP TYPE IF EXISTS {enum['name']} CASCADE\")"
            )
        return "\n".join(code_lines)

    def _generate_table_drop(self) -> str:
        """Generate table drop code."""
        code_lines = []
        for table in reversed(self.tables):  # Drop in reverse order
            code_lines.append(f"    op.drop_table('{table['name']}')")
        return "\n".join(code_lines)

    def _generate_index_drop(self) -> str:
        """Generate index drop code."""
        code_lines = []
        for index in reversed(self.indexes):
            code_lines.append(f"    op.drop_index('{index['name']}')")
        return "\n".join(code_lines)

    def _generate_function_drop(self) -> str:
        """Generate function drop code."""
        code_lines = []
        for function in reversed(self.functions):
            code_lines.append(
                f"    op.execute(\"DROP FUNCTION IF EXISTS {function['name']} CASCADE\")"
            )
        return "\n".join(code_lines)

    def _generate_trigger_drop(self) -> str:
        """Generate trigger drop code."""
        code_lines = []
        for trigger in reversed(self.triggers):
            code_lines.append(
                f"    op.execute(\"DROP TRIGGER IF EXISTS {trigger['name']} CASCADE\")"
            )
        return "\n".join(code_lines)

    def _generate_view_drop(self) -> str:
        """Generate view drop code."""
        code_lines = []
        for view in reversed(self.views):
            code_lines.append(
                f"    op.execute(\"DROP VIEW IF EXISTS {view['name']} CASCADE\")"
            )
        return "\n".join(code_lines)

    def save_migration(self, migration_code: str) -> Path:
        """Save the generated migration to a file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_initial_schema_from_sql.py"
        output_file = self.output_dir / filename

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        output_file.write_text(migration_code)
        logger.info(f"Migration saved to: {output_file}")

        return output_file


def main():
    """Main function to convert schema.sql to Alembic migration."""
    # Get script directory
    current_dir = Path(__file__).parent
    backend_dir = current_dir.parent.parent.parent

    # File paths
    schema_file = current_dir / "schema.sql"
    migrations_dir = backend_dir / "app" / "alembic" / "versions"

    logger.info("Starting schema.sql to Alembic migration conversion")
    logger.info(f"Schema file: {schema_file}")
    logger.info(f"Output directory: {migrations_dir}")

    try:
        # Create converter
        converter = SchemaToMigrationConverter(schema_file, migrations_dir)

        # Parse schema
        converter.parse_schema()

        # Generate migration
        migration_code = converter.generate_migration()

        # Save migration
        output_file = converter.save_migration(migration_code)

        logger.info("Schema conversion completed successfully!")
        logger.info(f"Generated migration: {output_file}")
        logger.info(
            "Please review the generated migration before running 'alembic upgrade head'"
        )

        return 0

    except Exception as e:
        logger.error(f"Schema conversion failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
