FROM alpine:latest

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-virtualenv \
    bash \
    rm -rf /etc/periodic

WORKDIR /app

COPY failman.py .
COPY requirements.txt .
COPY config.yaml .
COPY crontab /etc/crontabs/root
COPY .env .

RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --upgrade pip && \
    /app/venv/bin/pip install -r requirements.txt

ENV PATH="/app/venv/bin:$PATH"

CMD ["crond", "-f", "-l", "8"]
