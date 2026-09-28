FROM python:3.11-slim@sha256:9a7765b36773a37061455b332f18e265e7f58f6fea9c419a550d2a8b0e9db834

# pytest for generated Python tests. The Tester agent writes pytest-style tests
# (`import pytest`, bare assert functions); the plain python:3.11-slim image
# has no pytest, so every such mission failed on import before a single
# assertion ran (found re-qualifying stuck missions, 2026-09-28). pytest also
# collects unittest.TestCase classes, so stdlib-style tests keep working.
COPY requirements.txt /opt/factory/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /opt/factory/requirements.txt \
    && python -c "import pytest; assert pytest.__version__ == '9.1.1'"
COPY run-tests /opt/factory/run-tests
RUN chmod 0555 /opt/factory/run-tests

LABEL org.opencontainers.image.title="thefactory sandbox-test-python" \
      org.opencontainers.image.description="Offline pytest runner for Python runtime QC"
