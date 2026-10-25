# Build:  docker build -t reform3d .
# Slicer: docker build --build-arg WITH_SLICER=1 -t reform3d .   (without it the print estimate is a rough calculation)
# Run:    docker run --rm -p 8000:8000 --env-file .env -v reform3d-data:/data --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges reform3d
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 REFORM3D_DATA_DIR=/data PIP_NO_CACHE_DIR=1

# Optional: real print time and support numbers from PrusaSlicer (adds about 400 MB).  docker build --build-arg WITH_SLICER=1 -t reform3d .
ARG WITH_SLICER=0
RUN if [ "$WITH_SLICER" = "1" ]; then apt-get update && apt-get install -y --no-install-recommends prusa-slicer && rm -rf /var/lib/apt/lists/*; fi

RUN useradd --create-home --uid 10001 reform && mkdir /data && chown reform:reform /data
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app app
COPY web web

USER reform
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
