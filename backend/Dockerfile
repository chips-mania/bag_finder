FROM python:3.11-slim-bookworm

WORKDIR /app

# OpenCV (headless) runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# CPU torch first, then the rest (skip torch lines to avoid CUDA wheels)
RUN grep -vE '^(torch|torchvision)==' requirements.txt > /tmp/reqs.txt \
    && pip install --no-cache-dir \
        torch==2.1.0 torchvision==0.16.0 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /tmp/reqs.txt

COPY . .

ENV MODEL_PATH=mobile_sam.pt \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Railway injects PORT; first boot downloads CLIP + MobileSAM weights
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
