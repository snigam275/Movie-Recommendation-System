"""
CineVibe — Flask API Backend
Serves movie recommendations and proxies TMDB API calls.
"""

import os
import pickle
import requests
import time
import json
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

# ─── Configuration ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))

TMDB_KEY = os.getenv("TMDB_API_KEY")
OMDB_KEY = os.getenv("OMDB_API_KEY", "trilogy")
FALLBACK_POSTER = "/no_poster.png"

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# ─── Load ML Data ───────────────────────────────────────────────────────────────
print("📂 Loading movie data...")
movies_dict = pickle.load(open(os.path.join(BASE_DIR, 'movies_dict.pkl'), 'rb'))
similarity = pickle.load(open(os.path.join(BASE_DIR, 'similarity.pkl'), 'rb'))

import pandas as pd
movies = pd.DataFrame(movies_dict)
print(f"   ✅ Loaded {len(movies)} movies")


# ─── TMDB Helpers ───────────────────────────────────────────────────────────────
poster_cache = {}

def fetch_tmdb_details(movie_id, title="Unknown"):
    """Fetch movie details from TMDB with OMDB poster fallback."""
    cache_key = str(movie_id)
    if cache_key in poster_cache:
        return poster_cache[cache_key]

    default = {
        "poster": FALLBACK_POSTER, "rating": None, "genres": [],
        "overview": "", "year": "", "runtime": "",
    }
    if not TMDB_KEY:
        return default
    try:
        try:
            url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_KEY}"
            resp = requests.get(url, timeout=2.5)
            if resp.status_code == 429:
                time.sleep(1)
                resp = requests.get(url, timeout=2.5)
            status = resp.status_code
        except Exception:
            status = 500

        omdb_data = None  # Lazy-load OMDB
        def get_omdb():
            nonlocal omdb_data
            if omdb_data is not None:
                return omdb_data
            try:
                omdb_data = requests.get(
                    f"https://www.omdbapi.com/?t={title}&apikey={OMDB_KEY}", timeout=5
                ).json()
            except Exception:
                omdb_data = {}
            return omdb_data

        if status != 200:
            # TMDB failed entirely — try full OMDB fallback
            omdb = get_omdb()
            if omdb.get("Response") == "True":
                poster = omdb.get("Poster") if omdb.get("Poster") != "N/A" else FALLBACK_POSTER
                runtime_str = omdb.get("Runtime", "")
                result = {
                    "poster": poster,
                    "rating": omdb.get("imdbRating"),
                    "genres": [g.strip() for g in omdb.get("Genre", "").split(",")] if omdb.get("Genre") else [],
                    "overview": omdb.get("Plot", ""),
                    "year": omdb.get("Year", ""),
                    "runtime": runtime_str if runtime_str != "N/A" else "",
                }
                poster_cache[cache_key] = result
                return result
            return default

        data = resp.json()
        poster = None
        if data.get("poster_path"):
            poster = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
        if not poster:
            omdb = get_omdb()
            if omdb.get("Poster") and omdb["Poster"] != "N/A":
                poster = omdb["Poster"]
        if not poster:
            poster = FALLBACK_POSTER

        overview = data.get("overview", "")
        if not overview:
            omdb = get_omdb()
            overview = omdb.get("Plot", "")

        result = {
            "poster": poster,
            "rating": data.get("vote_average"),
            "genres": [g["name"] for g in data.get("genres", [])],
            "overview": overview,
            "year": (data.get("release_date") or "")[:4],
            "runtime": f"{data.get('runtime', '')} min" if data.get("runtime") else "",
        }
        poster_cache[cache_key] = result
        return result
    except Exception:
        return default


# ─── Routes: Static Pages ───────────────────────────────────────────────────────
@app.route('/')
def landing():
    return send_from_directory('static', 'index.html')

@app.route('/recommend')
def recommend_page():
    return send_from_directory('static', 'recommend.html')


# ─── Routes: API ────────────────────────────────────────────────────────────────
@app.route('/api/movies')
def api_movies():
    """Return all movie titles for search autocomplete."""
    titles = movies['title'].tolist()
    return jsonify(titles)


@app.route('/api/featured')
def api_featured():
    """Return featured movies with backdrops for the landing page carousel."""
    import random
    popular_ids = movies.head(100)['movie_id'].tolist()
    popular_titles = movies.head(100)['title'].tolist()
    indices = list(range(len(popular_ids)))
    random.shuffle(indices)
    featured = []
    for idx in indices:
        if len(featured) >= 4:
            break
        mid = popular_ids[idx]
        title = popular_titles[idx]
        if not TMDB_KEY:
            featured.append({
                "title": title,
                "backdrop": FALLBACK_POSTER,
                "rating": None,
                "year": "",
                "runtime": "",
                "genres": [],
                "overview": "",
            })
            continue
        try:
            url = f"https://api.themoviedb.org/3/movie/{mid}?api_key={TMDB_KEY}"
            resp = requests.get(url, timeout=2.5)
            if resp.status_code != 200:
                raise ValueError("TMDB failed")
            data = resp.json()
            backdrop = data.get("backdrop_path")
            if not backdrop:
                backdrop = FALLBACK_POSTER
            featured.append({
                "title": data.get("title", title),
                "backdrop": backdrop if backdrop == FALLBACK_POSTER else f"https://image.tmdb.org/t/p/w1280{backdrop}",
                "rating": data.get("vote_average"),
                "year": (data.get("release_date") or "")[:4],
                "runtime": f"{data.get('runtime', '')}m" if data.get("runtime") else "",
                "genres": [g["name"] for g in data.get("genres", [])],
                "overview": data.get("overview", ""),
            })
        except Exception:
            # Fallback to OMDB
            try:
                omdb = requests.get(f"https://www.omdbapi.com/?t={title}&apikey={OMDB_KEY}", timeout=3).json()
                if omdb.get("Response") == "True":
                    poster = omdb.get("Poster") if omdb.get("Poster") != "N/A" else FALLBACK_POSTER
                    featured.append({
                        "title": title,
                        "backdrop": poster,
                        "rating": omdb.get("imdbRating"),
                        "year": omdb.get("Year", ""),
                        "runtime": omdb.get("Runtime", ""),
                        "genres": [g.strip() for g in omdb.get("Genre", "").split(",")] if omdb.get("Genre") else [],
                        "overview": omdb.get("Plot", ""),
                    })
            except Exception:
                continue
    if not featured:
        featured = [
            {
                "title": title,
                "backdrop": FALLBACK_POSTER,
                "rating": None,
                "year": "",
                "runtime": "",
                "genres": [],
                "overview": "",
            }
            for title in popular_titles[:4]
        ]
    return jsonify(featured)


@app.route('/api/movie-by-title')
def api_movie_by_title():
    """Get movie details by title (for the selected movie info panel)."""
    title = request.args.get('title', '')
    match = movies[movies['title'].str.lower() == title.lower()]
    if match.empty:
        return jsonify({"error": "Not found"}), 404
    mid = int(match.iloc[0].movie_id)
    details = fetch_tmdb_details(mid, match.iloc[0].title)
    details["title"] = match.iloc[0].title
    details["movie_id"] = mid
    return jsonify(details)


@app.route('/api/recommend')
def api_recommend():
    """Return movie recommendations."""
    movie = request.args.get('movie', '')
    n = int(request.args.get('n', 12))
    genre = request.args.get('genre', '')

    matches = movies[movies['title'].str.lower() == movie.lower()]
    if matches.empty:
        return jsonify({"error": "Movie not found"}), 404

    movie_index = matches.index[0]
    distances = similarity[movie_index]
    candidates = sorted(
        list(enumerate(distances)), reverse=True, key=lambda x: x[1]
    )[1:100]

    def fetch_one(item):
        idx, score = item
        mid = movies.iloc[idx].movie_id
        title = movies.iloc[idx].title
        details = fetch_tmdb_details(mid, title)
        return {
            "title": title,
            "movie_id": int(mid),
            "score": round(score * 100, 1),
            **details,
        }

    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(fetch_one, candidates))

    # Filter: only movies with posters
    results = [r for r in results if r.get("poster")]

    # Genre filter
    if genre and genre != "All":
        results = [r for r in results if genre in r.get("genres", [])]

    return jsonify(results[:n])


@app.route('/api/movie/<int:movie_id>')
def api_movie_detail(movie_id):
    """Get single movie details."""
    match = movies[movies['movie_id'] == movie_id]
    title = match.iloc[0].title if not match.empty else "Unknown"
    details = fetch_tmdb_details(movie_id, title)
    details["title"] = title
    details["movie_id"] = movie_id
    return jsonify(details)


@app.route('/api/popular')
def api_popular():
    """Return some popular movies for the landing page posters."""
    popular_ids = movies.head(40)['movie_id'].tolist()
    popular_titles = movies.head(40)['title'].tolist()

    results = []
    for mid, title in zip(popular_ids, popular_titles):
        details = fetch_tmdb_details(mid, title)
        if details.get("poster"):
            results.append({"poster": details["poster"], "title": title})
        if len(results) >= 28:  # 7 cols × 4 rows
            break
    return jsonify(results)


if __name__ == '__main__':
    print("🎬 CineVibe server starting on http://localhost:5000")
    app.run(debug=True, port=5000)
