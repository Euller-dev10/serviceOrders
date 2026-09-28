import json

from django.db import models


class VectorField(models.Field):
    """Campo vetorial: pgvector no PostgreSQL; fallback JSON/texto no SQLite (testes)."""

    def __init__(self, dim=1536, *args, **kwargs):
        self.dim = dim
        kwargs.setdefault('null', True)
        kwargs.setdefault('blank', True)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs['dim'] = self.dim
        return name, path, args, kwargs

    def db_type(self, connection):
        if connection.vendor == 'postgresql':
            return f'vector({self.dim})'
        return 'text'

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return None
        if isinstance(value, list):
            return [float(x) for x in value]
        if isinstance(value, str):
            text = value.strip()
            if text.startswith('['):
                try:
                    return [float(x) for x in json.loads(text)]
                except (ValueError, json.JSONDecodeError):
                    return None
        return None

    def to_python(self, value):
        if value is None or value == '':
            return None
        if isinstance(value, list):
            return [float(x) for x in value]
        if isinstance(value, str):
            text = value.strip()
            if text.startswith('['):
                try:
                    return [float(x) for x in json.loads(text)]
                except (ValueError, json.JSONDecodeError):
                    return None
        return None

    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return '[' + ','.join(str(float(x)) for x in value) + ']'
        return value
