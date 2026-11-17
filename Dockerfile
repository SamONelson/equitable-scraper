FROM python:3.12-slim

ENV OUTPUT_FOLDER=/opt/equitable-scraper/policy-data
ENV PORTAL_URL=NOT_DEFINED
ENV USERNAME=NOT_DEFINED
ENV PASSWORD=NOT_DEFINED
ENV CHROME_BIN=/usr/bin/chromium

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/equitable-scraper/

COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src/*.py ./

RUN mkdir -p "$OUTPUT_FOLDER"

CMD ["python", "main.py"]
