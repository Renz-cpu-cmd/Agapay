"""Developer tool: generate a NEW reviewed migration snapshot, never run on startup."""
import json
from pathlib import Path
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import sqlite, postgresql
from app.schema_catalog import metadata

target = Path(__file__).parent / 'app/migrations/0001_schema.json'
if target.exists():
    raise SystemExit('Existing migrations are immutable; create a new revision instead')
target.parent.mkdir(exist_ok=True)
result = {}
for name, dialect in [('sqlite', sqlite.dialect()), ('postgresql', postgresql.dialect())]:
    result[name] = [{
        'name': table.name,
        'sql': str(CreateTable(table).compile(dialect=dialect)),
        'columns': [c.name for c in table.columns],
        'column_contract': {c.name: {'type': str(c.type.compile(dialect=dialect)), 'nullable': c.nullable}
                            for c in table.columns},
        'unique_contract': [[c.name for c in constraint.columns] for constraint in table.constraints
                            if constraint.__class__.__name__ == 'UniqueConstraint'],
        'primary_key': [c.name for c in table.primary_key.columns],
        'indexes': [{'name': i.name, 'sql': str(CreateIndex(i).compile(dialect=dialect))}
                    for i in sorted(table.indexes, key=lambda i:i.name)],
    } for table in metadata.sorted_tables]
target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
print(f'Frozen {len(metadata.tables)} tables for review')
