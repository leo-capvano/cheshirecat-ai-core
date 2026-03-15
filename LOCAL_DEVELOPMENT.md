# Local Development Setup for Cheshire Cat AI

This guide explains how to set up the Cheshire Cat AI for local development using Docker.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## 1. Initial Configuration

Before starting, you need to create a `.env` file from the example provided:

```bash
cp .env.example .env
```

You can customize the variables in `.env` if needed, but the default values should work for a standard local setup.

## 2. Start the Vector Database

The Cheshire Cat uses PostgreSQL with `pgvector` for its long-term memory in this local setup. You can start it using the provided Docker Compose file:

```bash
docker compose -f res/postgres/postgres-docker-compose.yml up -d
```

This will start a PostgreSQL instance on port `5433` (as configured in the compose file).

### PostgreSQL Configuration Details

For a full list of PostgreSQL environment variables and configuration for production, please refer to the [PostgreSQL Documentation](POSTGRES.md).

**Note for Local Development:**
The `compose-local.yml` is pre-configured to connect to the `pgvector-local` container started in Step 2. If you use the provided compose file, ensure your settings in `.env` match:
- `CCAT_POSTGRESQL_PORT=5433`
- `CCAT_POSTGRESQL_USER=postgres`
- `CCAT_POSTGRESQL_PASSWORD=password`
- `CCAT_POSTGRESQL_DB=vectordb`

### Switching back to Qdrant

If you prefer to use Qdrant (the default), set the following in your `.env`:
```bash
CCAT_VECTOR_DB=qdrant
```

## 3. Start the Cheshire Cat Core

To start the Cat Core in development mode, use the `compose-local.yml` file:

```bash
docker compose -f compose-local.yml up --build
```

### What happens in Development Mode:
- **Hot Reloading:** The `./core` directory is mounted into the container, allowing changes to the code to be reflected immediately.
- **Debugging:** `debugpy` is enabled on port `5678`.
- **Waiting for Debugger:** The container is configured with the `--wait-for-client` flag. **This means the application will not start until you attach a debugger** (see the VS Code section below).
- **Custom Dockerfile:** It uses `core/Dockerfile-local` which installs development dependencies.

## 4. Accessing the Application

Once everything is running, you can access the following services:

- **Admin Panel:** [http://localhost:1865/admin](http://localhost:1865/admin) - The main interface to chat with the Cat and manage plugins.
- **API Documentation:** [http://localhost:1865/docs](http://localhost:1865/docs) - Interactive Swagger UI for the REST API.
- **WebSocket:** `ws://localhost:1865/ws` - For real-time chat integration.

## 5. Development Tips

### Attaching a Debugger (VS Code)

To debug the Cat, you can add this configuration to your `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Attach to Cat",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 5678
            },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}/core",
                    "remoteRoot": "/app"
                }
            ]
        }
    ]
}
```

### Viewing Logs

To see the logs from the Cat Core:

```bash
docker logs -f cheshire_cat_core
```

## Stopping the Application

To stop all services:

```bash
# Stop Core
docker compose -f compose-local.yml down

# Stop Database
docker compose -f res/postgres/postgres-docker-compose.yml down
```
