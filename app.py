# app.py (Versão Final com Novo Layout de Abas)
import streamlit as st
import requests
import json
import base64
import pandas as pd
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import nltk
from nltk.corpus import stopwords
from pathlib import Path
import os
from dotenv import load_dotenv
from jose import jwt, JWTError
from datetime import datetime, timezone

# --- CARREGAMENTO DE VARIÁVEIS DE AMBIENTE ---
load_dotenv()
API_INTERNAL_URL = os.getenv("API_INTERNAL_URL", "http://localhost:8000")
API_PUBLIC_URL   = os.getenv("API_PUBLIC_URL",   API_INTERNAL_URL)
JWT_SECRET = os.getenv('JWT_SECRET', 'uma-chave-secreta-padrao-mude-isso')
login_url = f"{API_PUBLIC_URL}/auth/login"

# estado inicial p/ cota (uma única vez)
if "rate_limit" not in st.session_state:
    st.session_state.rate_limit = {}   # {'limit': int, 'remaining': int, 'reset': int}

def _fmt_reset(reset_ts: int) -> str:
    """Converte timestamp UNIX em 'HH:MM UTC'."""
    try:
        dt_utc = datetime.fromtimestamp(int(reset_ts), tz=timezone.utc)
        return dt_utc.strftime("%H:%M UTC")
    except Exception:
        return "-"

def render_quota_badge():
    """Exibe um badge compacto com cota restante/limite e hora de reset."""
    q = st.session_state.get("rate_limit") or {}
    remaining = q.get("remaining")
    limit = q.get("limit")
    reset = q.get("reset")
    if remaining is None or limit is None:
        return
    text = f"Limite diário: {remaining}/{limit} restantes"
    if reset:
        text += f" • reset {_fmt_reset(reset)}"
    st.markdown(
        f"<div style='display:inline-flex;gap:.5rem;padding:.35rem .6rem;border:1px solid #334155;"
        f"border-radius:9999px;background:#0f172a;color:#cbd5e1;font-size:.85rem;'>{text}</div>",
        unsafe_allow_html=True,
    )

# --- ESTILOS INICIAIS ---
st.markdown("""
<style>
:root { --card-bg: #111827; --muted:#94a3b8; --ring:#374151; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; }
h1,h2,h3 { letter-spacing: .2px; }
.badges { display:flex; gap:.5rem; flex-wrap:wrap; margin:.5rem 0 1rem; }
.badge { padding:.25rem .6rem; border-radius:9999px; background:#0f172a; border:1px solid var(--ring); font-size:.85rem; color:#cbd5e1; }
.card { border:1px solid var(--ring); background:var(--card-bg); border-radius:16px; padding:16px; }
.source-card { border:1px solid #253047; border-radius:16px; padding:14px; margin-bottom:10px; background:#0d1324; }
.source-head { display:flex; align-items:center; gap:.6rem; }
.source-head img { border-radius:9999px; }
.kpi { display:flex; gap:1rem; flex-wrap:wrap; margin:.6rem 0 1rem; }
.kpi .item { border:1px dashed #334155; border-radius:12px; padding:.6rem .8rem; }
.kpi .label { color:var(--muted); font-size:.8rem; }
.kpi .value { font-weight:600; font-size:1.05rem; }
hr { border:none; border-top:1px solid #263142; margin:1rem 0; }
a, a:visited { color:#93c5fd; text-decoration:none; }
a:hover { text-decoration:underline; }
</style>
""", unsafe_allow_html=True)

# CSS do botão Google
st.markdown("""
<style>
.google-wrap{ display:flex; justify-content:center; }           /* centraliza */
.google-btn{
  --w: 280px;                                                   /* largura padrão */
  width: var(--w);
  display:inline-flex; align-items:center; justify-content:center; gap:.55rem;
  padding:12px 16px; border-radius:10px; font-weight:600; text-decoration:none;
  letter-spacing:.2px;
  transition: all .15s ease;
  border:1px solid transparent;
}
.google-btn .google-icon svg{ width:18px; height:18px; display:block; }

/* VARIANTES */
.google-btn.dark{ background:#1a73e8; color:#fff; border-color:#1a73e8; box-shadow:0 2px 8px rgba(26,115,232,.35); }
.google-btn.dark:hover{ background:#1669c1; border-color:#1669c1; }

.google-btn.light{ background:#fff; color:#3c4043; border-color:#dadce0; }
.google-btn.light:hover{ background:#f8faff; border-color:#d2e3fc; }

.google-btn.outline{ background:transparent; color:#e5e7eb; border-color:#334155; }
.google-btn.outline:hover{ background:#0f172a; border-color:#475569; }
</style>
""", unsafe_allow_html=True)

def google_login_button(url: str, label: str = "Entrar com Google", width: int = 260, variant: str = "dark"):
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 533.5 544.3" aria-hidden="true" focusable="false">
      <path fill="#EA4335" d="M533.5 278.4c0-18.5-1.7-36.3-4.9-53.6H272.1v101.4h146.9c-6.3 34.1-25.3 63-54 82.3v68h87.4c51.2-47.2 81.1-116.8 81.1-198.1z"/>
      <path fill="#34A853" d="M272.1 544.3c73.4 0 135.1-24.3 180.1-66.2l-87.4-68c-24.3 16.3-55.4 26-92.7 26-71 0-131.2-47.9-152.7-112.2H29.6v70.6c44.6 88.4 136 149.8 242.5 149.8z"/>
      <path fill="#4285F4" d="M119.4 323.9c-10-29.8-10-62.1 0-91.9V161.4H29.6c-39.4 78.7-39.4 171.8 0 250.5l89.8-88z"/>
      <path fill="#FBBC05" d="M272.1 106.7c39.9-.6 78.2 13.9 107.5 40.6l80.2-80.2C404.1 24.7 343.1.4 272.1 0 165.6 0 74.2 61.4 29.6 150l89.8 70.6C140.9 154.4 201.1 106.7 272.1 106.7z"/>
    </svg>
    """
    st.markdown(f"""
<div class="google-wrap">
  <a class="google-btn {variant}" style="--w:{width}px" href="{url}" target="_self" rel="nofollow noopener">
    <span class="google-icon">{svg}</span>
    <span>{label}</span>
  </a>
</div>
""", unsafe_allow_html=True)

# --- FUNÇÕES AUXILIARES ---
@st.cache_data
def get_base_64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f: data = f.read()
    return base64.b64encode(data).decode()

def apply_background_styles():
    SCRIPT_DIR = Path(__file__).parent
    ASSETS_DIR = SCRIPT_DIR / "assets"
    BACKGROUND_FILE = ASSETS_DIR / "background.png"
    CSS_FILE = ASSETS_DIR / "style.css"
    img_str = get_base_64_of_bin_file(BACKGROUND_FILE)
    with open(CSS_FILE, "r", encoding="utf-8") as f:
        css_code = f.read().replace("{img_str}", img_str)
    css_code += 'img[data-testid="stImage"] { border-radius: 50%; }'
    st.markdown(f"<style>{css_code}</style>", unsafe_allow_html=True)

@st.cache_data
def generate_word_cloud(texts, topic):
    stopwords_languages = ['portuguese', 'english', 'spanish', 'french', 'german']
    combined_stopwords = set(s for lang in stopwords_languages for s in stopwords.words(lang))
    if topic:
        combined_stopwords.add(topic.lower())
    text_corpus = " ".join(texts)
    if not text_corpus.strip(): return None
    wordcloud = WordCloud(width=800, height=400, background_color=None, mode="RGBA", colormap='viridis', stopwords=combined_stopwords).generate(text_corpus)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis("off")
    fig.patch.set_alpha(0.0)
    return fig

def display_top_posts(posts: list, top_n: int = 3):
    if not posts:
        st.warning("Não foram encontrados posts para exibir.")
        return
    for post in posts:
        post['total_engagement'] = post.get('like_count', 0) + post.get('repost_count', 0)
    sorted_posts = sorted(posts, key=lambda p: p['total_engagement'], reverse=True)[:top_n]
    cols = st.columns(top_n, gap="large")
    for i, post in enumerate(sorted_posts):
        with cols[i]:
            author = post.get('author', {})
            record = post.get('record', {})
            handle = author.get('handle', '')
            post_rkey = post.get('uri', '').split('/')[-1]
            post_url = f"https://bsky.app/profile/{handle}/post/{post_rkey}"

            with st.container(border=True, height=350):
                header_cols = st.columns([1, 4])
                with header_cols[0]:
                    if author.get('avatar'): st.image(author.get('avatar'), width=50)
                with header_cols[1]:
                    st.markdown(f"**{author.get('display_name', '')}**\n<small>[@{handle}]({post_url})</small>", unsafe_allow_html=True)
                st.info(f"*{record.get('text', '')[:280]}...*")
                metric_cols = st.columns(2)
                metric_cols[0].metric(label="❤️ Curtidas", value=f"{post.get('like_count', 0):,}")
                metric_cols[1].metric(label="🔁 Reposts", value=f"{post.get('repost_count', 0):,}")

# --- CONFIGURAÇÃO DA PÁGINA E NLTK ---
st.set_page_config(page_title="AskTheSky", page_icon="🚀", layout="wide")
try:
    stopwords.words('portuguese')
except LookupError:
    with st.spinner("Configurando recursos de idioma..."):
        nltk.download('stopwords')
    st.rerun()
apply_background_styles()

# --- LÓGICA DE AUTENTICAÇÃO ---
if "token" in st.query_params:
    st.session_state["token"] = st.query_params["token"]
    st.query_params.clear()
    st.rerun()

if "token" in st.session_state:
    try:
        user_info = jwt.decode(st.session_state["token"], JWT_SECRET, algorithms=['HS256'])
        st.session_state["user_info"] = user_info
        st.session_state["authentication_status"] = True
    except JWTError:
        del st.session_state["token"]
        st.session_state["authentication_status"] = False
else:
    st.session_state["authentication_status"] = None

# --- LÓGICA DE EXIBIÇÃO ---
if st.session_state.get("authentication_status"):
    # --- GERENCIAMENTO DE ESTADO ---
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'topic' not in st.session_state:
        st.session_state.topic = ""
    if 'question' not in st.session_state:
        st.session_state.question = ""
    if 'llm_model' not in st.session_state:
        st.session_state.llm_model = "gpt-4o-mini"
    if 'submitted' not in st.session_state:
        st.session_state.submitted = False

    def handle_submission():
        st.session_state.submitted = True

    # --- LAYOUT DO DASHBOARD ---
    # Header
    header_cols = st.columns([0.8, 0.2])
    with header_cols[0]:
        st.title("AskTheSky 🚀")
        st.caption("Faça uma pergunta sobre um tópico e receba uma análise baseada em posts recentes do Bluesky.")
        render_quota_badge()
    with header_cols[1]:
        with st.container(border=True):
            user_info = st.session_state.get("user_info", {})
            st.write(f"Logado como: **{user_info.get('name', '')}**")
            if st.button("Logout", use_container_width=True):
                del st.session_state["token"]
                del st.session_state["authentication_status"]
                del st.session_state["user_info"]
                st.rerun()

    st.divider()

    # Formulário de Análise
    with st.container(border=True):
        # alinhar todos os conteúdos pela base da coluna
        form_cols = st.columns([2, 3, 1, 1], vertical_alignment="bottom")

        with form_cols[0]:
            st.markdown("**Tópico de Análise**")  # label “manual”
            st.session_state.topic = st.text_input(
                "", value=st.session_state.topic,
                placeholder="Ex: 'NVIDIA'",
                label_visibility="collapsed"
            )

        with form_cols[1]:
            st.markdown("**Sua Pergunta Específica**")
            st.session_state.question = st.text_input(
                "", value=st.session_state.question,
                placeholder="Ex: 'Qual a percepção sobre as novas placas RTX?'",
                label_visibility="collapsed"
            )

        with form_cols[2]:
            st.markdown("**Modelo de IA**")
            st.session_state.llm_model = st.selectbox(
                "", ("gpt-4o-mini", "gemini-1.5-flash-latest"),
                index=("gpt-4o-mini", "gemini-1.5-flash-latest").index(st.session_state.llm_model),
                label_visibility="collapsed"
            )

        with form_cols[3]:
            # “label” vazio para manter a mesma altura das outras colunas
            st.markdown("&nbsp;")
            submitted = st.button(
                "Analisar 1000 Posts ✨",
                use_container_width=True,
                type="primary",
             on_click=handle_submission
            )

    render_quota_badge()


    # --- LÓGICA DE SUBMISSÃO E EXIBIÇÃO DE RESULTADOS ---
    if st.session_state.submitted:
        if not st.session_state.topic or not st.session_state.question:
            st.error("Por favor, preencha o Tópico e a Pergunta.")
            st.session_state.submitted = False
        else:
            with st.spinner("🔄 Coletando e analisando posts... Isso pode levar alguns minutos..."):
                new_result_this_run = False
                try:
                    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
                    payload = {
                        "topic": st.session_state.topic,
                        "question": st.session_state.question,
                        "llm_model": st.session_state.llm_model,
                        # se você tiver esses controles na UI, pode enviar também:
                        # "top_k": st.session_state.get("top_k", 6),
                        # "economy_mode": st.session_state.get("economy_mode", False),
                    }

                    # ⚠️ use json=payload (não data=json.dumps), pois seu backend espera JSON
                    r = requests.post(f"{API_INTERNAL_URL}/analyze", headers=headers, json=payload, timeout=120)

                    # ✅ salve SEMPRE os headers de cota (sucesso ou erro)
                    limit = r.headers.get("X-RateLimit-Limit")
                    remaining = r.headers.get("X-RateLimit-Remaining")
                    reset = r.headers.get("X-RateLimit-Reset")
                    st.session_state.rate_limit = {
                        "limit": int(limit) if str(limit).isdigit() else None,
                        "remaining": int(remaining) if str(remaining).isdigit() else None,
                        "reset": int(reset) if str(reset).isdigit() else None,
                    }

                    # ✅ trate explicitamente cota estourada ANTES de raise_for_status
                    if r.status_code == 429:
                        msg = "Você atingiu o limite diário de perguntas."
                        if reset:
                            msg += f" Tente novamente após {_fmt_reset(reset)}."
                        st.error(msg)
                        # não mexa no analysis_result anterior; apenas saia do try
                    else:
                        r.raise_for_status()
                        st.session_state.analysis_result = r.json()
                        new_result_this_run = True

                except requests.RequestException as e:
                    st.error(f"Falha ao consultar o servidor: {e}")

                finally:
                    st.session_state.submitted = False
                    # ✅ só rerun se tivemos novo resultado (evita apagar a mensagem 429 imediatamente)
                    if new_result_this_run:
                        st.rerun()

    # --- NOVO LAYOUT COM ABAS PARA OS RESULTADOS ---
    if st.session_state.analysis_result:
        data = st.session_state.analysis_result
        answer = data.get("answer") or "—"
        timings = data.get("timings") or {}
        tokens  = data.get("tokens")  or {}
        sources = data.get("sources") or []
        source_posts = data.get("source_posts") or []
        raw_posts = data.get("raw_posts") or []

        st.markdown("---")

        # Resumo da resposta e KPIs
        with st.container(border=True):
            st.markdown("#### Resposta da Análise")
            st.info(answer)

            kpi_cols = st.columns(4)
            total_time = sum(timings.values()) if timings else 0.0
            kpi_cols[0].metric("Tempo Total (s)", f"{total_time:.2f}")
            kpi_cols[1].metric("Fontes Encontradas", len(sources))
            kpi_cols[2].metric("Total de Tokens", tokens.get("total_tokens", "N/A"))
            kpi_cols[3].metric("Custo Estimado (USD)", f"${tokens.get('cost_usd', 0.0):.4f}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Abas com detalhes
        tab1, tab2, tab3 = st.tabs(["🔗 Fontes da Análise", "📊 Métricas Detalhadas", "🧭 Análise Exploratória"])

        with tab1:
            st.markdown("##### Posts mais relevantes utilizados como fonte para a resposta:")
            if not sources:
                st.caption("Nenhuma fonte encontrada.")
            for i, s in enumerate(sources, 1):
                author = s.get("author") or "autor"
                uri = s.get("uri") or "#"
                txt = (s.get("text") or "")[:500]
                score = s.get("score")
                with st.container(border=True):
                    cols = st.columns([0.08, 0.92])
                    with cols[0]:
                        if s.get("avatar"): st.image(s["avatar"], width=44)
                    with cols[1]:
                        st.markdown(f"**[@{author}]({uri})**")
                        if score is not None: st.caption(f"Similaridade com a pergunta: {score:.3f}")
                        st.write(txt)

        with tab2:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("##### Tempos por estágio (s)")
                if timings: st.dataframe(pd.DataFrame.from_dict(timings, orient='index', columns=['Segundos']), use_container_width=True)
                else: st.caption("Métricas de tempo não disponíveis.")
            with col2:
                st.markdown("##### Tokens / Custo (OpenAI)")
                token_data = {
                    "Prompt Tokens": tokens.get("prompt_tokens"),
                    "Completion Tokens": tokens.get("completion_tokens"),
                    "Total Tokens": tokens.get("total_tokens"),
                    "Custo (USD)": f"${tokens.get('cost_usd', 0.0):.5f}"
                }
                st.dataframe(pd.DataFrame.from_dict(token_data, orient='index', columns=['Valor']), use_container_width=True)

        with tab3:
            st.markdown("##### Termos em destaque (Nuvem de Palavras)")
            wordcloud_fig = generate_word_cloud(source_posts, st.session_state.topic)
            if wordcloud_fig:
                st.pyplot(wordcloud_fig, use_container_width=True)
            else:
                st.warning("Não foi possível gerar a nuvem de palavras.")

            st.markdown("---")
            st.markdown("##### Destaques da conversa (Maior Engajamento)")
            display_top_posts(raw_posts)

# --- TELAS DE LOGIN / ERRO ---
elif st.session_state.get("authentication_status") is False:
    st.error('Seu token de login é inválido ou expirou.')
    google_login_button(login_url, "Login novamente com Google", width=260, variant="dark")
else: # Equivale a authentication_status is None
    st.title("Bem-vindo ao AskTheSky 🚀")
    st.info("Por favor, faça login com sua conta Google para utilizar o aplicativo.")
    google_login_button(login_url, "Entrar com Google", width=260, variant="dark")
