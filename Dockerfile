# ASTRA web app (Analyse + Live). Simulation needs Docker on the host and is not available inside this container.
#   docker build -t astra .
#   docker run --rm -p 8787:8787 astra                      -> http://127.0.0.1:8787
#   Live from a ground station: add -p 14550:14550/udp and connect to udp:0.0.0.0:14550
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE* ./
COPY src ./src
COPY examples ./examples
RUN pip install --no-cache-dir . && useradd -m astra
USER astra
EXPOSE 8787 14550/udp
CMD ["astra", "ui", "--host", "0.0.0.0", "--port", "8787", "--no-browser"]
