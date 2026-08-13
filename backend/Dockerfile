# Backend: FastAPI + LibreOffice (pptx/xlsx -> pdf) + poppler (pdf -> png)
FROM python:3.11-slim

# Native deps for render_service.py:
#  - libreoffice-impress/calc: pptx/xlsx -> pdf (headless)
#  - poppler-utils: pdftoppm (pdf -> png)
#  - fonts-liberation: Arial/Times metric-compatible fonts for correct render
RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-impress \
      libreoffice-calc \
      poppler-utils \
      fonts-liberation \
      fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the Python package (deps from pyproject.toml)
COPY pyproject.toml ./
COPY aurum_encuestas ./aurum_encuestas
RUN pip install --no-cache-dir .

# All persistent state lives under $HOME/.aurum (see config.py).
# Point HOME at the mounted volume so uploads/cache/training survive restarts.
# LibreOffice also needs a writable HOME for its user profile.
ENV HOME=/data
RUN mkdir -p /data && chmod 777 /data
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "aurum_encuestas.api:app", "--host", "0.0.0.0", "--port", "8000"]
