# STAGE 1: install dependencies (big image, with build tools)
FROM python:3.9 AS builder
RUN python -m venv /venv
RUN /venv/bin/pip install flask

# STAGE 2: minimal runtime
FROM python:3.9-slim
COPY --from=builder /venv /venv
WORKDIR /app
COPY app.py .
CMD ["/venv/bin/python", "app.py"]
