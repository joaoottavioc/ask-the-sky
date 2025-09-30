# src/main.py
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from typing import List, Dict, Any
from typing import Optional

# --- IMPORTAÇÕES ADICIONAIS ---
from starlette.middleware.sessions import SessionMiddleware
# Adicione a importação do CORSMiddleware aqui
from fastapi.middleware.cors import CORSMiddleware

from src.services.rag_service import perform_rag_analysis
from src.clients.bluesky_client import BlueskyClient

from authlib.integrations.starlette_client import OAuth
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv
from src.services.rate_limit import RateLimiter
from src.core.config import settings


load_dotenv()  # ensure .env is loaded into os.environ

# --- CONFIGURAÇÃO DE AUTENTICAÇÃO ---
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
JWT_SECRET = os.environ.get('JWT_SECRET', 'a-chave-secreta-deve-ser-longa-e-segura')
STREAMLIT_BASE_URL = os.environ.get('STREAMLIT_BASE_URL', 'http://localhost:8501')
# Uma chave secreta para assinar o cookie de sessão do backend
SESSION_COOKIE_SECRET = os.environ.get('SESSION_COOKIE_SECRET', 'outra-chave-secreta-para-o-backend')

DAILY_QUESTION_LIMIT = int(os.getenv("DAILY_QUESTION_LIMIT", "50"))
REDIS_URL = os.getenv("REDIS_URL", "")


# mantém seu lifespan e inicializa tudo lá dentro
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Iniciando a API...")
    bsky_client = BlueskyClient()
    bsky_client.login()
    app.state.bsky_client = bsky_client

    # inicializa o rate limiter aqui
    app.state.limiter = RateLimiter(REDIS_URL)

    yield
    print("Encerrando a API.")

# crie o app DEPOIS de definir lifespan
app = FastAPI(title="AskTheSky - RAG Analysis API", lifespan=lifespan)

# --- CONFIGURAÇÃO DE MIDDLEWARE ---

# 1. CORS Middleware (Deve ser um dos primeiros)
# Garante que o frontend (Streamlit) possa se comunicar com este backend.
origins = [
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    # Você pode adicionar a URL de produção do seu frontend aqui também
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"], # Permite todos os cabeçalhos
)

# 2. Session Middleware
# Usado para o processo de autenticação OAuth com o Google.
app.add_middleware(SessionMiddleware, secret_key=SESSION_COOKIE_SECRET, https_only=False)


oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_app_token(user_info: dict) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(hours=8)
    jwt_payload = {
        'sub': user_info.get('sub'),
        'email': user_info.get('email'),
        'name': user_info.get('name'),
        'picture': user_info.get('picture'),
        'exp': expiration
    }
    return jwt.encode(jwt_payload, JWT_SECRET, algorithm='HS256')

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        email: str = payload.get("email")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return payload


# Nota: A função 'lifespan' está definida duas vezes no seu código original.
# O FastAPI usará a última definição. Removi a duplicata para maior clareza.
# A mesma coisa acontece com a criação de 'app' e a adição do 'SessionMiddleware'.
# A versão abaixo é uma versão limpa e corrigida.

@app.on_event("startup")
def _startup():
    # Isso pode ser redundante se já estiver no lifespan, mas não causa problemas.
    if not hasattr(app.state, "limiter"):
      app.state.limiter = RateLimiter(REDIS_URL)

def enforce_quota(request: Request, user: dict = Depends(get_current_user)):
    # fallback defensivo
    limiter = getattr(request.app.state, "limiter", None)
    if limiter is None:
        limiter = RateLimiter(settings.redis_url or "")
        request.app.state.limiter = limiter

    user_id = user.get("sub") or user.get("email") or "anon"
    limiter: RateLimiter = request.app.state.limiter
    remaining, reset_ts = limiter.hit(user_id, DAILY_QUESTION_LIMIT)
    # guarda para headers
    request.state.rate_remaining = remaining
    request.state.rate_reset = reset_ts
    return True  # apenas para encadear como dependency


# --- Modelos de Dados ---
class AnalysisRequest(BaseModel):
    topic: str = Field(..., examples=["NVIDIA"])
    question: str = Field(..., examples=["Qual a percepção sobre as novas placas RTX?"])
    llm_model: str = Field(default="gpt-4o-mini", description="O modelo de IA a ser usado.")
    top_k: int = Field(default=6, ge=1, le=12)
    economy_mode: bool = Field(default=False)

class AnalysisResponse(BaseModel):
    answer: str
    source_posts: List[str]
    raw_posts: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    timings: Dict[str, float]
    tokens: Dict[str, Any]

# --- Endpoints de Autenticação ---
@app.get("/auth/login")
async def login(request: Request):
    redirect_uri = request.url_for('auth')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback", name="auth") # Dê um nome à rota para que request.url_for funcione
async def auth(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')
    app_token = create_app_token(user_info)

    response = RedirectResponse(url=f"{STREAMLIT_BASE_URL}?token={app_token}")
    return response

@app.get("/user/me")
async def get_user(current_user: dict = Depends(get_current_user)):
    return current_user

# --- Endpoints da API ---
@app.get("/")
def read_root():
    return {"message": "Bem-vindo à API de Análise AskTheSky!"}

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_topic(
    request: AnalysisRequest,
    fastapi_request: Request,
    response: Response,
    _quota_ok = Depends(enforce_quota),
    user: dict = Depends(get_current_user),
):
    bsky_client = fastapi_request.app.state.bsky_client
    result = perform_rag_analysis(
        topic=request.topic,
        question=request.question,
        post_limit=1000,
        llm_model=request.llm_model,
        bsky_client=fastapi_request.app.state.bsky_client,
        top_k=getattr(request, "top_k", 6),
        economy_mode=getattr(request, "economy_mode", False),
    )
    # Rate limit headers
    response.headers["X-RateLimit-Limit"] = str(DAILY_QUESTION_LIMIT)
    response.headers["X-RateLimit-Remaining"] = str(getattr(fastapi_request.state, "rate_remaining", 0))
    response.headers["X-RateLimit-Reset"] = str(getattr(fastapi_request.state, "rate_reset", 0))
    return AnalysisResponse(**result)

# --- Execução da API ---
if __name__ == "__main__":
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)