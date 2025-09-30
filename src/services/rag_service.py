# src/services/rag_service.py
import os
from src.clients.bluesky_client import BlueskyClient
from src.core.config import settings

# Imports do LangChain
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.callbacks import get_openai_callback  # <-- for token accounting

from src.services.timing import stage  # <-- our helper

def perform_rag_analysis(
    topic: str,
    question: str,
    post_limit: int,
    llm_model: str,
    bsky_client: BlueskyClient,
    top_k: int = 6,
    economy_mode: bool = False,
) -> dict:
    timings = {}

    # 1) Fetch posts ---------------------------------------------------------
    with stage(timings, "fetch_posts"):
        posts = bsky_client.search_posts(query=topic, limit=post_limit)  # :contentReference[oaicite:5]{index=5}
        post_texts = [getattr(getattr(p, "record", None), "text", "") for p in posts]
        post_texts = [t for t in post_texts if t]

    if not post_texts:
        return {
            "answer": "Não foram encontrados posts suficientes sobre este tópico para realizar a análise.",
            "source_posts": [],
            "raw_posts": [],
            "sources": [],
            "timings": timings,
            "tokens": {},
        }

    # Build rich metadata for UI cards (uri/author/avatar/…)
    raw_posts = []
    for post in posts:
        author = getattr(post, "author", None)
        record = getattr(post, "record", None)
        raw_posts.append({
            "uri": getattr(post, "uri", ""),
            "author": {
                "handle": getattr(author, "handle", "N/A"),
                "display_name": getattr(author, "display_name", "N/A"),
                "avatar": getattr(author, "avatar", None)
            },
            "record": {"text": getattr(record, "text", "")},
            "like_count": getattr(post, "like_count", 0),
            "repost_count": getattr(post, "repost_count", 0),
        })  # mirrors your current structure :contentReference[oaicite:6]{index=6}

    # 2) Embeddings + FAISS --------------------------------------------------
    with stage(timings, "embed_index"):
        model_name = "sentence-transformers/all-MiniLM-L6-v2"  # same as today :contentReference[oaicite:7]{index=7}
        embeddings = HuggingFaceEmbeddings(model_name=model_name)
        vector_store = FAISS.from_texts(texts=post_texts, embedding=embeddings)  # :contentReference[oaicite:8]{index=8}

    # 3) Retrieve top-k with scores -----------------------------------------
    with stage(timings, "retrieve"):
        # Use the vector store directly to get scores
        retrieved = vector_store.similarity_search_with_score(question, k=top_k)
        # retrieved -> list[(Document, score)]
        sources = []
        for doc, score in retrieved:
            # find original post meta by matching text
            txt = doc.page_content
            # naïve map: first index match (ok for demo; can improve with hash map)
            try:
                i = post_texts.index(txt)
                meta = raw_posts[i]
            except ValueError:
                meta = {"uri": None, "author": {}, "record": {"text": txt}}
            sources.append({
                "uri": meta.get("uri"),
                "author": meta.get("author", {}).get("handle"),
                "avatar": meta.get("author", {}).get("avatar"),
                "text": txt,
                "score": float(score),
                "created_at": None  # add if you later capture timestamps
            })

    # 4) Choose LLM and build RAG chain -------------------------------------
    # keep your current model switch :contentReference[oaicite:9]{index=9}
    if "gpt" in llm_model:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        llm = ChatOpenAI(model=llm_model, temperature=0.3)
    elif "gemini" in llm_model:
        os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY
        llm = ChatGoogleGenerativeAI(model=llm_model, temperature=0.3)
    else:
        raise ValueError("Modelo de LLM inválido ou não suportado.")

    prompt_template = """
    Sua tarefa é atuar como um analista.
    Use APENAS o contexto abaixo para responder. Seja conciso (~150 palavras).
    Contexto:
    {context}
    Pergunta: {question}
    Responda em português e cite as fontes com colchetes [1], [2], …
    """
    PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])

    # Use the same vector store as retriever (k can differ from top_k above) :contentReference[oaicite:10]{index=10}
    retriever = vector_store.as_retriever(search_kwargs={"k": top_k})
    rag_chain = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever,
                                            chain_type_kwargs={"prompt": PROMPT})

    # 5) Generate answer + tokens -------------------------------------------
    token_info = {}
    with stage(timings, "llm"):
        if "gpt" in llm_model:
            with get_openai_callback() as cb:
                response = rag_chain.invoke(question)
                token_info = {
                    "prompt_tokens": cb.prompt_tokens,
                    "completion_tokens": cb.completion_tokens,
                    "total_tokens": cb.total_tokens,
                    "cost_usd": round(cb.total_cost, 6),
                }
        else:
            # Gemini: no built-in callback; return empty token_info
            response = rag_chain.invoke(question)

    return {
        "answer": response.get("result", "Não foi possível gerar uma resposta."),
        "source_posts": post_texts,  # keeps your current fields for wordcloud :contentReference[oaicite:11]{index=11}
        "raw_posts": raw_posts,
        "sources": sources,          # NEW: top-k with meta+score
        "timings": timings,          # NEW: per-stage seconds
        "tokens": token_info,        # NEW: only filled on OpenAI
    }