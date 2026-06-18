FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PANNs CNN14 embedding stack (default similarity space). CPU-only torch; --no-deps
# on panns so it can't drag in a CUDA torch or matplotlib (stubbed in embeddings.py).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --no-deps panns-inference torchlibrosa

# Pre-fetch the CNN14 checkpoint + label file so inference works offline at runtime.
RUN python -c "import os, urllib.request; os.makedirs('/root/panns_data', exist_ok=True); \
    urllib.request.urlretrieve('http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv', '/root/panns_data/class_labels_indices.csv'); \
    urllib.request.urlretrieve('https://zenodo.org/record/3987831/files/Cnn14_mAP%3D0.431.pth?download=1', '/root/panns_data/Cnn14_mAP=0.431.pth')"

COPY app/ ./app/

CMD ["python", "-m", "app.main"]
