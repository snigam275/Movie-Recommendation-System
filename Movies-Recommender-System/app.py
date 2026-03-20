import streamlit as st
import pickle
import pandas as pd


movies_dict = pickle.load(open('movies_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dict)

similarity = pickle.load(open('similarity.pkl', 'rb'))
#Function for recommendation
def recommend(movie):
    movie_index = movies[movies['title']==movie].index[0]
    distances = similarity[movie_index]
    movie_list = sorted(list(enumerate(distances)),reverse = True, key = lambda x:x[1])[1:7]

    recommended_movie = []
    for i in movie_list:
        recommended_movie.append(movies.iloc[i[0]].title)
    return recommended_movie


st.title("Movie Recommender System")

selected_movie_name = st.selectbox(
'Which movie do you want?',
movies['title'].values)

if st.button('Recommend'):
    recommendations = recommend(selected_movie_name)
    for i in recommendations:
        st.write(i)