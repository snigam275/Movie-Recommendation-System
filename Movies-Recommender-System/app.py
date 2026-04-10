import streamlit as st
import pickle
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
from dotenv import load_dotenv
import os
import time
from concurrent.futures import ThreadPoolExecutor

# ─── Configuration ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))
api_key = os.getenv("TMDB_API_KEY")
omdb_api_key = os.getenv("OMDB_API_KEY", "trilogy")
gemini_api_key = os.getenv("GEMINI_API_KEY")

st.set_page_config(
    page_title="🎬 CineMatch — Movie Recommender",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Build Model if needed ──────────────────────────────────────────────────────
def build_model():
    import ast
    import nltk
    from nltk.stem.porter import PorterStemmer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as cos_sim

    DATA_DIR = os.path.join(BASE_DIR, '..', 'DataSetFolder')

    movies_csv = pd.read_csv(os.path.join(DATA_DIR, 'tmdb_5000_movies.csv'))
    credits_csv = pd.read_csv(os.path.join(DATA_DIR, 'tmdb_5000_credits.csv'))
    merged = movies_csv.merge(credits_csv, on='title')
    movie_data = merged[["movie_id","title","overview","genres","keywords","cast","crew"]].copy()
    movie_data.dropna(inplace=True)

    def extract_names(obj, key='name', max_count=None):
        parsed = ast.literal_eval(obj) if isinstance(obj, str) else obj
        names = []
        for i, item in enumerate(parsed):
            if max_count and i >= max_count: break
            if isinstance(item, dict): names.append(item.get(key,''))
            else: names.append(str(item))
        return names

    def extract_director(obj):
        parsed = ast.literal_eval(obj) if isinstance(obj, str) else obj
        for person in parsed:
            if person.get('job') == 'Director': return [person['name']]
        return []

    movie_data['genres']   = movie_data['genres'].apply(lambda x: extract_names(x))
    movie_data['keywords'] = movie_data['keywords'].apply(lambda x: extract_names(x))
    movie_data['cast']     = movie_data['cast'].apply(lambda x: extract_names(x, max_count=3))
    movie_data['crew']     = movie_data['crew'].apply(extract_director)
    movie_data['overview'] = movie_data['overview'].apply(lambda x: x.split())

    for col in ['genres','keywords','cast','crew']:
        movie_data[col] = movie_data[col].apply(lambda x: [i.replace(" ","") for i in x])

    movie_data['tag'] = (movie_data['overview'] + movie_data['genres'] +
                         movie_data['keywords'] + movie_data['cast'] + movie_data['crew'])
    new_df = movie_data[["movie_id","title","tag"]].copy()
    new_df['tag'] = new_df['tag'].apply(lambda x: " ".join(x).lower())

    ps = PorterStemmer()
    new_df['tag'] = new_df['tag'].apply(lambda text: " ".join([ps.stem(w) for w in text.split()]))

    tfidf = TfidfVectorizer(max_features=5000, stop_words='english')
    vectors = tfidf.fit_transform(new_df['tag']).toarray()
    sim = cos_sim(vectors)

    pickle.dump(new_df.to_dict(), open(os.path.join(BASE_DIR, 'movies_dict.pkl'), 'wb'))
    pickle.dump(sim, open(os.path.join(BASE_DIR, 'similarity.pkl'), 'wb'))
    return new_df, sim

# ─── Load Data ──────────────────────────────────────────────────────────────────
@st.cache_resource
def load_data():
    movies_dict_path = os.path.join(BASE_DIR, 'movies_dict.pkl')
    similarity_path  = os.path.join(BASE_DIR, 'similarity.pkl')

    if not os.path.exists(movies_dict_path) or not os.path.exists(similarity_path):
        st.info("⚙️ First time setup: Building model... (2-3 mins)")
        new_df, sim = build_model()
        return new_df, sim

    movies_dict = pickle.load(open(movies_dict_path, 'rb'))
    similarity  = pickle.load(open(similarity_path,  'rb'))
    return pd.DataFrame(movies_dict), similarity

movies, similarity = load_data()

# ─── Initialize Request Session ────────────────────────────────────────────────
session = requests.Session()
retries = Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries, pool_connections=200, pool_maxsize=200)
session.mount('https://', adapter)
session.mount('http://', adapter)

# ─── Premium CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&display=swap');

    /* ── Global ── */
    .stApp {
        background: linear-gradient(160deg, #080810 0%, #0d0d1a 30%, #121228 60%, #0a1628 100%);
        font-family: 'Outfit', sans-serif;
        color: #e0e0e0;
    }
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Hero ── */
    .hero-container {
        text-align: center;
        padding: 2rem 0 1rem;
    }
    .hero-title {
        font-size: 3.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 40%, #ff9068 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -2px;
        margin-bottom: 4px;
        text-shadow: 0 0 80px rgba(255,65,108,0.3);
    }
    .hero-subtitle {
        font-size: 1.05rem;
        color: #6b7280;
        font-weight: 300;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    /* ── Movie Card ── */
    .movie-card {
        background: linear-gradient(160deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 14px;
        overflow: hidden;
        transition: all 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        position: relative;
        cursor: pointer;
    }
    .movie-card:hover {
        transform: translateY(-10px) scale(1.03);
        border-color: rgba(255,65,108,0.5);
        box-shadow: 0 25px 50px rgba(255,65,108,0.15),
                    0 0 60px rgba(255,65,108,0.08);
    }
    .movie-card img {
        width: 100%;
        aspect-ratio: 2/3;
        object-fit: cover;
        display: block;
    }
    .card-info {
        padding: 10px 12px 14px;
        background: linear-gradient(0deg, rgba(0,0,0,0.8), transparent);
    }
    .card-title {
        color: #f0f0f0;
        font-size: 0.82rem;
        font-weight: 600;
        line-height: 1.3;
        margin-bottom: 6px;
        min-height: 2.2em;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .card-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
    }
    .card-rating {
        color: #fbbf24;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .card-year {
        color: #6b7280;
        font-size: 0.72rem;
    }
    .match-pill {
        background: linear-gradient(135deg, #ff416c, #ff4b2b);
        color: white;
        padding: 2px 8px;
        border-radius: 20px;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.3px;
    }

    /* ── Hover overlay ── */
    .card-overlay {
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 60%;
        background: linear-gradient(180deg, rgba(0,0,0,0.7) 0%, transparent 100%);
        opacity: 0;
        transition: opacity 0.3s;
        padding: 12px;
        display: flex;
        flex-direction: column;
    }
    .movie-card:hover .card-overlay {
        opacity: 1;
    }
    .overlay-genres {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
    }
    .genre-chip {
        background: rgba(255,65,108,0.25);
        color: #ff9068;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.6rem;
        font-weight: 500;
        border: 1px solid rgba(255,65,108,0.3);
    }

    /* ── Selected Movie Panel ── */
    .selected-panel {
        background: linear-gradient(160deg, rgba(255,65,108,0.06), rgba(255,255,255,0.02));
        border: 1px solid rgba(255,65,108,0.15);
        border-radius: 20px;
        padding: 28px;
        margin: 1.5rem 0;
        backdrop-filter: blur(20px);
        display: flex;
        gap: 24px;
    }
    .selected-poster img {
        border-radius: 14px;
        width: 180px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
    }
    .selected-details h2 {
        color: #f0f0f0;
        font-size: 1.6rem;
        font-weight: 700;
        margin: 0 0 6px 0;
    }
    .selected-details .meta-row {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 10px;
    }
    .rating-badge {
        background: linear-gradient(135deg, #fbbf24, #f59e0b);
        color: #000;
        padding: 3px 10px;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 700;
    }
    .year-badge {
        background: rgba(255,255,255,0.08);
        color: #9ca3af;
        padding: 3px 10px;
        border-radius: 8px;
        font-size: 0.8rem;
    }
    .genre-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 12px;
    }
    .genre-tag {
        background: rgba(255,65,108,0.12);
        color: #ff9068;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 500;
        border: 1px solid rgba(255,65,108,0.2);
    }
    .overview-text {
        color: #9ca3af;
        font-size: 0.9rem;
        line-height: 1.7;
        max-height: 4.5em;
        overflow: hidden;
    }

    /* ── Section Headers ── */
    .section-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 2rem 0 1.2rem;
    }
    .section-header h3 {
        color: #f0f0f0;
        font-size: 1.3rem;
        font-weight: 700;
        margin: 0;
    }
    .section-line {
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, rgba(255,65,108,0.3), transparent);
    }

    /* ── Button ── */
    .stButton > button {
        background: linear-gradient(135deg, #ff416c, #ff4b2b) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.65rem 2rem !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        letter-spacing: 0.5px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 20px rgba(255,65,108,0.3) !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 30px rgba(255,65,108,0.5) !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d0d1a, #080810) !important;
        border-right: 1px solid rgba(255,255,255,0.05);
    }
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #ff416c;
    }

    /* ── Selectbox ── */
    .stSelectbox [data-testid="stMarkdownContainer"] p {
        color: #9ca3af;
        font-weight: 500;
    }

    /* ── Stats ── */
    .stats-bar {
        display: flex;
        justify-content: center;
        gap: 40px;
        padding: 1rem 0;
        margin-bottom: 1rem;
    }
    .stat-item {
        text-align: center;
    }
    .stat-value {
        font-size: 1.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ff416c, #ff9068);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .stat-label {
        font-size: 0.7rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #ff416c; border-radius: 3px; }

    /* ── Animations ── */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-in {
        animation: fadeInUp 0.5s ease-out forwards;
    }
</style>
""", unsafe_allow_html=True)


# ─── API Helpers ────────────────────────────────────────────────────────────────

# Local premium fallback poster
FALLBACK_POSTER = os.path.join(BASE_DIR, 'no_poster.png')


def _make_placeholder(title="No Poster"):
    """Return local fallback poster path."""
    return FALLBACK_POSTER


def _try_omdb_poster(title):
    try:
        url = f"https://www.omdbapi.com/?t={title}&apikey={omdb_api_key}"
        resp = session.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            poster = data.get("Poster")
            if poster and poster != "N/A":
                return poster
    except Exception:
        pass
    return None


@st.cache_data(ttl=86400)
def _ask_gemini(title):
    if not gemini_api_key:
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_api_key}"
        prompt = (
            f'Give me details about the movie "{title}". '
            f'Respond ONLY with valid JSON, no markdown: '
            f'{{"overview": "brief plot summary", "genres": ["genre1", "genre2"], '
            f'"year": "release year", "rating": "IMDB rating out of 10"}}'
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = session.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            text = text.strip().strip("`").strip()
            if text.startswith("json"):
                text = text[4:].strip()
            return json.loads(text)
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600)
def fetch_movie_details(movie_id, title="Unknown"):
    """Multi-layer fallback: TMDB → OMDB (poster) → Gemini (details) → placeholder."""
    placeholder = _make_placeholder(title)
    default = {
        "poster": placeholder, "rating": "N/A",
        "genres": [], "overview": "No overview available.", "year": "—",
    }
    if not api_key:
        gemini_data = _ask_gemini(title)
        if gemini_data:
            return {
                "poster": _try_omdb_poster(title) or placeholder,
                "rating": gemini_data.get("rating", "N/A"),
                "genres": gemini_data.get("genres", []),
                "overview": gemini_data.get("overview", "No overview available."),
                "year": str(gemini_data.get("year", "—")),
            }
        return default
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}"
        response = session.get(url, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ TMDB API failed for '{title}' (id={movie_id}): HTTP {response.status_code}")
            gemini_data = _ask_gemini(title)
            if gemini_data:
                return {
                    "poster": _try_omdb_poster(title) or placeholder,
                    "rating": gemini_data.get("rating", "N/A"),
                    "genres": gemini_data.get("genres", []),
                    "overview": gemini_data.get("overview", "No overview available."),
                    "year": str(gemini_data.get("year", "—")),
                }
            return default

        data = response.json()
        poster = None
        if data.get("poster_path"):
            poster = f"https://image.tmdb.org/t/p/w500/{data['poster_path']}"
        if not poster:
            poster = _try_omdb_poster(data.get("title", title))
        if not poster:
            poster = placeholder

        overview = data.get("overview", "")
        genres = [g["name"] for g in data.get("genres", [])]
        rating = data.get("vote_average", "N/A")
        year = data.get("release_date", "—")[:4]

        if not overview or not genres:
            gemini_data = _ask_gemini(title)
            if gemini_data:
                overview = overview or gemini_data.get("overview", "")
                genres = genres or gemini_data.get("genres", [])
                if rating in ("N/A", 0):
                    rating = gemini_data.get("rating", "N/A")
                if year == "—":
                    year = str(gemini_data.get("year", "—"))

        return {
            "poster": poster, "rating": rating,
            "genres": genres, "overview": overview or "No overview available.",
            "year": year,
        }
    except Exception:
        return default


# ─── Recommendation Engine ──────────────────────────────────────────────────────
def _has_real_poster(details):
    """Check if movie has a real poster (not our local fallback)."""
    poster = details.get("poster", "")
    return poster and poster != FALLBACK_POSTER and "placehold" not in str(poster)


def recommend(movie, n=10, genre_filter=None):
    """Return top N similar movies with real posters, optionally filtered by genre."""
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    # Get more candidates to account for filtered poster-less movies
    candidates = sorted(
        list(enumerate(distances)), reverse=True, key=lambda x: x[1]
    )[1:80]  # get top 80 candidates to filter from

    # Parallel fetch details for speed
    def fetch_one(item):
        idx, score = item
        movie_id = movies.iloc[idx].movie_id
        title = movies.iloc[idx].title
        details = fetch_movie_details(movie_id, title)
        return {"title": title, "score": round(score * 100, 1), **details}

    with ThreadPoolExecutor(max_workers=10) as executor:
        all_results = list(executor.map(fetch_one, candidates))

    # Only keep movies with real posters
    all_results = [r for r in all_results if _has_real_poster(r)]

    # Apply genre filter if selected
    if genre_filter and genre_filter != "All":
        all_results = [r for r in all_results if genre_filter in r.get("genres", [])]

    return all_results[:n]


def get_all_genres():
    """Extract unique genres from the movie database for the filter."""
    genres = set()
    # Sample some movies to get common genres
    sample_ids = movies.head(200)['movie_id'].tolist()
    common_genres = [
        "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary",
        "Drama", "Family", "Fantasy", "History", "Horror", "Music", "Mystery",
        "Romance", "Science Fiction", "TV Movie", "Thriller", "War", "Western"
    ]
    return ["All"] + common_genres


# ─── UI: Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎬 CineMatch")
    st.markdown("---")

    st.markdown("### 🎭 Filter by Genre")
    genre_filter = st.selectbox(
        "Genre",
        get_all_genres(),
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("### 📊 Results Count")
    num_results = st.slider("Movies to show", 5, 20, 10, label_visibility="collapsed")

    st.markdown("---")
    st.markdown(
        '<p style="color:#4b5563; font-size:0.75rem; text-align:center;">'
        '4,800+ movies · TF-IDF engine<br>TMDB · OMDB · Gemini AI</p>',
        unsafe_allow_html=True,
    )


# ─── UI: Hero ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-container">
    <div class="hero-title">CineMatch</div>
    <div class="hero-subtitle">AI-Powered Movie Recommendations</div>
</div>
""", unsafe_allow_html=True)

# Stats bar
st.markdown(f"""
<div class="stats-bar">
    <div class="stat-item">
        <div class="stat-value">{len(movies):,}</div>
        <div class="stat-label">Movies</div>
    </div>
    <div class="stat-item">
        <div class="stat-value">TF-IDF</div>
        <div class="stat-label">Algorithm</div>
    </div>
    <div class="stat-item">
        <div class="stat-value">3</div>
        <div class="stat-label">API Sources</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── UI: Movie Selector ────────────────────────────────────────────────────────
col_select, col_btn = st.columns([5, 1])
with col_select:
    selected_movie = st.selectbox(
        "🔍 Search for a movie you enjoy:",
        movies['title'].values,
        index=None,
        placeholder="Type a movie name...",
    )
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    recommend_clicked = st.button("🎯 Find", use_container_width=True)


# ─── UI: Selected Movie Panel ──────────────────────────────────────────────────
if selected_movie:
    sel_id = movies[movies['title'] == selected_movie].iloc[0].movie_id
    sel = fetch_movie_details(sel_id, selected_movie)

    st.markdown("---")
    col_poster, col_info = st.columns([1, 3])
    with col_poster:
        st.image(sel["poster"], use_container_width=True)
    with col_info:
        genres_html = "".join(f'<span class="genre-tag">{g}</span>' for g in sel["genres"])
        overview = sel["overview"][:300] + ("..." if len(sel["overview"]) > 300 else "")
        st.markdown(f"""
        <div style="padding: 8px 0;">
            <h2 style="color:#f0f0f0; font-size:1.6rem; margin:0 0 6px 0; font-family:'Outfit',sans-serif;">{selected_movie}</h2>
            <div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">
                <span class="rating-badge">⭐ {sel['rating']}</span>
                <span class="year-badge">📅 {sel['year']}</span>
            </div>
            <div class="genre-tags">{genres_html}</div>
            <p style="color:#9ca3af; font-size:0.9rem; line-height:1.7; margin-top:8px;">{overview}</p>
        </div>
        """, unsafe_allow_html=True)


# ─── UI: Recommendations Grid ──────────────────────────────────────────────────
if recommend_clicked and selected_movie:
    with st.spinner("🎬 Finding your perfect matches..."):
        results = recommend(selected_movie, n=num_results, genre_filter=genre_filter)

    if not results:
        st.warning(f"No movies found matching genre: **{genre_filter}**. Try 'All'.")
    else:
        filter_label = f" in {genre_filter}" if genre_filter != "All" else ""
        st.markdown(f"""
        <div class="section-header animate-in">
            <h3>🎯 Top {len(results)} Picks{filter_label}</h3>
            <div class="section-line"></div>
        </div>
        """, unsafe_allow_html=True)

        # Render in rows of 5
        for row_start in range(0, len(results), 5):
            row = results[row_start:row_start + 5]
            cols = st.columns(5, gap="medium")
            for i, rec in enumerate(row):
                with cols[i]:
                    # Use st.image for reliable poster loading
                    st.image(rec["poster"], use_container_width=True)
                    st.markdown(f"""
                    <div style="text-align:center; padding:4px 0;">
                        <div class="card-title">{rec['title']}</div>
                        <div class="card-meta" style="justify-content:center; margin-top:6px;">
                            <span class="card-rating">⭐ {rec['rating']}</span>
                            <span class="match-pill">{rec['score']}%</span>
                            <span class="card-year">{rec['year']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

elif recommend_clicked and not selected_movie:
    st.warning("⚠️ Please select a movie first!")

# Footer
st.markdown("""
<div style="text-align:center; margin-top:4rem; padding:2rem 0;
    border-top:1px solid rgba(255,255,255,0.04);">
    <p style="color:#374151; font-size:0.75rem; letter-spacing:1px;">
        CINEMATCH © 2025 &nbsp;·&nbsp; Powered by TMDB, OMDB & Gemini AI
    </p>
</div>
""", unsafe_allow_html=True)