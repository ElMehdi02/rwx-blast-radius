
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

RUN git clone -q \
    https://github.com/tobymao/sqlglot.git \
    /opt/sqlglot && \
    cd /opt/sqlglot && \
    git checkout -q \
    eb11aec4be8cb2122afe713a4816662c3f0fb2fa

COPY requirements.lock /app/requirements.lock

RUN pip install --no-cache-dir \
    -r /app/requirements.lock && \
    pip install --no-cache-dir pytest-cov==7.0.0

COPY selector.py previous_v20.py previous_v17.py previous_selector.py baseline_selector.py build_index.py build_dependencies.py /app/

WORKDIR /opt/sqlglot

ENV PYTHONPATH=/app:/opt/sqlglot
ENV SKIP_INTEGRATION=0
ENV COVERAGE_FILE=/app/.coverage
ENV COVERAGE_CORE=ctrace
ENV BLAST_MODE=balanced

RUN timeout 300s python -m pytest -q \
    --cov=sqlglot \
    --cov-context=test \
    --cov-report= \
    tests/test_optimizer.py \
    tests/test_executor.py \
    tests/test_parser.py \
    tests/test_expressions.py \
    tests/test_serde.py \
    tests/dialects || true

RUN python /app/build_index.py && \
    python /app/build_dependencies.py

RUN chmod 644 \
    /app/impact_index.json \
    /app/dependencies.json

WORKDIR /app

USER nobody

ENV HOME=/tmp

CMD ["python", "/app/selector.py"]
