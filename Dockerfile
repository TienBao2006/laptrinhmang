# Multi-stage build for Bus Booking Server
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy project files
COPY . .

# No external dependencies to install (Zero-dependency project)
# Just verify the structure
RUN python -m py_compile run_server.py

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy application from builder
COPY --from=builder /app /app

# Create data directory for SQLite database
RUN mkdir -p /app/data

# Expose server port
EXPOSE 8888

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import socket; s = socket.socket(); s.connect(('localhost', 8888)); s.close()" || exit 1

# Run the server
CMD ["python", "run_server.py"]
