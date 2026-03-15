# PostgreSQL Production Configuration

The Cheshire Cat can be configured to use an external or production PostgreSQL database with the `pgvector` extension for long-term memory.

## Configuration

To connect the Cat to your PostgreSQL instance, set the following environment variables in your production environment:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `CCAT_VECTOR_DB` | Set this to `postgresql` to enable PostgreSQL. | `qdrant` |
| `CCAT_POSTGRESQL_HOST` | The hostname or IP of your PostgreSQL server. | `localhost` |
| `CCAT_POSTGRESQL_PORT` | The port of your PostgreSQL server. | `5432` |
| `CCAT_POSTGRESQL_USER` | The database user. | `ccat` |
| `CCAT_POSTGRESQL_PASSWORD` | The password for the database user. | `ccat` |
| `CCAT_POSTGRESQL_DB` | The name of the database. | `ccat` |

## Production Requirements

1.  **pgvector Extension**: Ensure the `pgvector` extension is installed and enabled in your database. You can enable it by running:
    ```sql
    CREATE EXTENSION IF NOT EXISTS vector;
    ```
2.  **Network Access**: Ensure the Cat Core has network access to the PostgreSQL host and port.
3.  **Permissions**: The database user must have permissions to create tables and perform CRUD operations, as the Cat will automatically create tables for memory collections (e.g., `vector_long_term_memory`).
