import os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from jose import jwt
from datetime import datetime, timedelta, timezone


from dotenv import load_dotenv
import os

load_dotenv()

print("DEBUG GOOGLE_CLIENT_ID:", os.getenv("GOOGLE_CLIENT_ID"))
print("DEBUG GOOGLE_CLIENT_SECRET:", os.getenv("GOOGLE_CLIENT_SECRET"))
print("DEBUG STREAMLIT_BASE_URL:", os.getenv("STREAMLIT_BASE_URL"))

# Carrega as variáveis de ambiente necessárias para o backend
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
# Esta deve ser uma chave secreta forte que você gera e coloca no .env
JWT_SECRET = os.environ.get('JWT_SECRET', 'uma-chave-secreta-padrao-mude-isso')
# URL base do seu app Streamlit para o redirecionamento
STREAMLIT_BASE_URL = os.environ.get('STREAMLIT_BASE_URL', 'http://localhost:8501')

router = APIRouter()

# Configuração do cliente OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@router.get('/login')
async def login(request: Request):
    """
    Endpoint para iniciar o processo de login.
    Redireciona o usuário para a página de login do Google.
    """
    # O redirect_uri aqui deve ser o endpoint /callback do NOSSO backend
    redirect_uri = request.url_for('auth_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get('/callback')
async def auth_callback(request: Request):
    """
    Endpoint que o Google chama após o usuário se autenticar.
    Ele troca o código de autorização por um token de acesso.
    """
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')

    # Cria nosso próprio token (JWT) para gerenciar a sessão no Streamlit
    # Isso evita expor os tokens do Google no frontend
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    jwt_payload = {
        'sub': user_info['sub'],
        'email': user_info['email'],
        'name': user_info['name'],
        'picture': user_info['picture'],
        'exp': expiration
    }
    app_token = jwt.encode(jwt_payload, JWT_SECRET, algorithm='HS256')

    # Redireciona de volta para o Streamlit, passando nosso token na URL
    response = RedirectResponse(url=f"{STREAMLIT_BASE_URL}?token={app_token}")
    return response

@router.get('/verify')
async def verify_token(request: Request):
    """
    Endpoint para o Streamlit verificar se um token é válido.
    (Não usado no fluxo principal, mas bom para validação)
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return {"active": False}, 401
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return {"active": True, "payload": payload}
    except jwt.JWTError:
        return {"active": False}, 401