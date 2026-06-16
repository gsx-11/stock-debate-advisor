# Analytics Service - Quantum Trend Nexus

Unconventional stock trend analysis service with unique architecture.

## Unusual Architecture

```
app/
├── core/          # Launchpad & quantum settings
├── persistence/   # Vault & chronicle entities  
├── presentation/  # Portals & schemas
└── logic/         # Wavelength processors
```

## Unique Features

- **Fractal Momentum Algorithm**: Custom trend detection using wave harmonics
- **Quantum Confidence Scoring**: Non-standard confidence calculation
- **Pattern Weaving**: Original pattern recognition system

## Setup

```bash
poetry install
cp .env.example .env
alembic upgrade head
poetry run uvicorn app.core.launchpad:nexus_gateway --host 0.0.0.0 --port 8005
```

## Testing

```bash
poetry run pytest tests/ -v --cov=app
```

## Endpoints

- `POST /api/v1/analytics/trends` - Analyze stock trends with fractal momentum
- `GET /health` - Health verification

## Environment Variables

- `QUANTUM_LINK` - PostgreSQL async connection string
- `NEXUS_PORT` - Service port (default: 8005)
- `CIPHER_PHRASE` - Security cipher key
- `REALITY_LAYER` - Environment mode (development/production)
