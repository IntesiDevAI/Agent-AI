FROM python:3.10-slim

ENV ACCEPT_EULA=Y
ENV DEBIAN_FRONTEND=noninteractive

# Installa pacchetti di base
RUN apt-get update && apt-get install -y \
    gnupg2 \
    curl \
    ca-certificates \
    apt-transport-https \
    unixodbc-dev \
    gcc \
    g++ \
    && mkdir -p /etc/apt/keyrings

# Aggiungi repository Microsoft (modo moderno, senza apt-key)
RUN curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor > /etc/apt/keyrings/microsoft.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
    > /etc/apt/sources.list.d/mssql-release.list

# Installa msodbcsql17
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Setup app
WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]