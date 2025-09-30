#!/usr/bin/env bash
set -e
sed -i 's/\r$//' /entrypoint.sh || true

if [ "$ROLE" = "frontend" ]; then
  echo "Starting Streamlit (frontend) on :8501"
  exec poetry run streamlit run app.py --server.port=8501 --server.address=0.0.0.0
else
  echo "Starting FastAPI (backend) on :8000"
  exec poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000
fi
