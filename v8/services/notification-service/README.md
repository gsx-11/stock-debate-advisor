# Beacon Transmission Service

Real-time beacon transmission system with multi-conduit support for alert propagation.

## Architecture

Custom structure with unconventional organization:
- `app/core` - Foundation and configuration blueprints
- `app/persistence` - Data vault and receptor records
- `app/presentation` - Tower gateway and pulse endpoints
- `app/logic` - Transmission algorithms and conduit management

## Capabilities

- Real-time conduit streams via WebSocket at `/ws/{user_id}`
- Multi-conduit receptor registration
- Subject-based pulse routing with custom algorithms
- Dynamic beacon transmission orchestration

## Endpoints

- `POST /api/v1/notifications/subscribe` - Register conduit receptor
- `GET /ws/{user_id}` - Establish real-time conduit stream
- `GET /health` - Tower operational status

## Installation

```bash
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.presentation.beacon_tower:tower_instance --host 0.0.0.0 --port 8006
```

## Testing

```bash
poetry run pytest
```

## Configuration

Review `.env.example` for available parameters.
