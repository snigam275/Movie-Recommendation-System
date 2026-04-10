"""
Improved Movie Recommendation System — ML Pipeline
====================================================
Run this script to regenerate the pickle files with better NLP.

Changes from original notebook:
1. TF-IDF Vectorizer instead of CountVectorizer (better recommendation quality)
2. Fixed cast extraction: consistently grabs top 3 (was 4 due to bug)
3. Consolidated duplicate convert functions into one reusable function
4. Cleaner code structure with proper documentation

Usage:
    cd c:\\Users\\shrey\\Desktop\\MovieRecommendationSystem
    python build_model.py
"""

import pandas as pd
import numpy as np
import ast
import pickle
import nltk
from nltk.stem.porter import PorterStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ─── 1. Load Datasets ──────────────────────────────────────────────────────────
print("📂 Loading datasets...")
movies = pd.read_csv('DataSetFolder/tmdb_5000_movies.csv')
credits = pd.read_csv('DataSetFolder/tmdb_5000_credits.csv')
print(f"   Movies: {movies.shape}, Credits: {credits.shape}")

# ─── 2. Merge DataFrames ───────────────────────────────────────────────────────
merged = movies.merge(credits, on='title')
print(f"   Merged: {merged.shape}")

# Select relevant columns
movie_data = merged[["movie_id", "title", "overview", "genres", "keywords", "cast", "crew"]].copy()

# Drop nulls
movie_data.dropna(inplace=True)
print(f"   After dropping nulls: {movie_data.shape}")

# ─── 3. Feature Extraction (Consolidated Functions) ────────────────────────────

def extract_names(obj, key='name', max_count=None):
    """
    Extract names from a JSON-like string of list of dicts.
    Consolidated replacement for convert, convert1, convert2.

    Args:
        obj: JSON string containing list of dicts
        key: dictionary key to extract (default: 'name')
        max_count: maximum number of items to extract (None = all)
    """
    parsed = ast.literal_eval(obj) if isinstance(obj, str) else obj
    names = []
    for i, item in enumerate(parsed):
        if max_count and i >= max_count:
            break
        if isinstance(item, dict):
            names.append(item.get(key, ''))
        else:
            names.append(str(item))
    return names


def extract_director(obj):
    """Extract only the director from the crew list."""
    parsed = ast.literal_eval(obj) if isinstance(obj, str) else obj
    for person in parsed:
        if person.get('job') == 'Director':
            return [person['name']]
    return []


print("🔧 Extracting features...")

# Genres — extract all genre names
movie_data['genres'] = movie_data['genres'].apply(lambda x: extract_names(x))

# Keywords — extract all keyword names
movie_data['keywords'] = movie_data['keywords'].apply(lambda x: extract_names(x))

# Cast — extract TOP 3 (fixed: was 4 due to != 4 bug)
movie_data['cast'] = movie_data['cast'].apply(lambda x: extract_names(x, max_count=3))

# Crew — extract director only
movie_data['crew'] = movie_data['crew'].apply(extract_director)

# Overview — split into word list
movie_data['overview'] = movie_data['overview'].apply(lambda x: x.split())

# ─── 4. Remove Spaces in Names (prevent "Sam" confusion) ──────────────────────
for col in ['genres', 'keywords', 'cast', 'crew']:
    movie_data[col] = movie_data[col].apply(lambda x: [i.replace(" ", "") for i in x])

# ─── 5. Create Tags ────────────────────────────────────────────────────────────
movie_data['tag'] = (
    movie_data['overview']
    + movie_data['genres']
    + movie_data['keywords']
    + movie_data['cast']
    + movie_data['crew']
)

new_df = movie_data[["movie_id", "title", "tag"]].copy()
new_df['tag'] = new_df['tag'].apply(lambda x: " ".join(x).lower())

# ─── 6. Stemming ───────────────────────────────────────────────────────────────
print("🌿 Applying stemming...")
ps = PorterStemmer()

def stem(text):
    return " ".join([ps.stem(word) for word in text.split()])

new_df['tag'] = new_df['tag'].apply(stem)

# ─── 7. TF-IDF Vectorization (UPGRADED from CountVectorizer) ───────────────────
print("🧮 Building TF-IDF vectors (5000 features)...")
tfidf = TfidfVectorizer(max_features=5000, stop_words='english')
vectors = tfidf.fit_transform(new_df['tag']).toarray()
print(f"   Vector shape: {vectors.shape}")

# ─── 8. Cosine Similarity ──────────────────────────────────────────────────────
print("📐 Calculating cosine similarity matrix...")
similarity = cosine_similarity(vectors)
print(f"   Similarity matrix: {similarity.shape}")

# ─── 9. Quick Test ──────────────────────────────────────────────────────────────
def recommend(movie, n=6):
    idx = new_df[new_df['title'] == movie].index[0]
    scores = sorted(list(enumerate(similarity[idx])), reverse=True, key=lambda x: x[1])[1:n+1]
    for i, score in scores:
        print(f"   {new_df.iloc[i].title} ({score:.2%} match)")

print("\n🎬 Test: Recommendations for 'Batman Begins':")
recommend('Batman Begins')

print("\n🎬 Test: Recommendations for 'Avatar':")
recommend('Avatar')

# ─── 10. Save Pickle Files ─────────────────────────────────────────────────────
print("\n💾 Saving pickle files...")
pickle.dump(new_df.to_dict(), open('Movies-Recommender-System/movies_dict.pkl', 'wb'))
pickle.dump(similarity, open('Movies-Recommender-System/similarity.pkl', 'wb'))
print("   ✅ movies_dict.pkl saved")
print("   ✅ similarity.pkl saved (~176 MB)")
print("\n🎉 Done! Restart your Streamlit app to use the improved model.")
