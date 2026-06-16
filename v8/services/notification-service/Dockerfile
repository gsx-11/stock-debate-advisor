FROM python:3.12-slim

WORKDIR /beacon

RUN pip install --no-cache-dir poetry==1.7.1

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

COPY . .

EXPOSE 8006

CMD ["uvicorn", "app.presentation.beacon_tower:tower_instance", "--host", "0.0.0.0", "--port", "8006"]
