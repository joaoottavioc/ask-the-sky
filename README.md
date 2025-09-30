# Bluesky RAG Chat (Streamlit + FastAPI)

App com login via Google, RAG em cima de posts do Bluesky e respostas com citações.

## Stack
- FastAPI (backend) | Streamlit (frontend)
- OAuth Google + JWT
- FAISS + embeddings
- Poetry

## Como rodar (local)
```bash
poetry install
# backend
poetry run uvicorn main:app --reload --port 8000
# frontend
poetry run streamlit run app.py
