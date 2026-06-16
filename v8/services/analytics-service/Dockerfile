FROM python:3.12-slim

WORKDIR /nexus

RUN pip install poetry==1.7.1

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --only main

COPY . .

RUN poetry install --no-interaction --no-ansi --only main

EXPOSE 8005

CMD ["uvicorn", "app.core.launchpad:nexus_gateway", "--host", "0.0.0.0", "--port", "8005"]
