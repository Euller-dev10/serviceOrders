"""Registra o adapter do pgvector nas conexões PostgreSQL (psycopg2)."""


def register_pgvector(sender, connection, **kwargs):
    if connection.vendor != 'postgresql':
        return
    try:
        from pgvector.psycopg2 import register_vector

        register_vector(connection)
    except Exception:
        pass
