# Multi-stage build for Bus Booking Server
FROM python:3.11-slim AS builder

WORKDIR /app

COPY . .

# Cài thư viện Python cần thiết
RUN pip install --no-cache-dir PyMySQL

RUN python -m py_compile run_server.py


# Final stage
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /app /app

# Copy các package đã cài từ builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

RUN mkdir -p /app/data

EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import socket; s = socket.socket(); s.connect(('localhost', 8888)); s.close()" || exit 1

CMD ["python", "run_server.py"]