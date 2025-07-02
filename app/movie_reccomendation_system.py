import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from typing import List, Dict
import sqlite3
import json

# Inicializar FastAPI com documentação
app = FastAPI(
    title="Movie Recommendation API",
    description="API para sistema de recomendação de filmes usando filtragem híbrida",
    version="1.0.0"
)

# Carregar dados
df = pd.read_csv("movies.csv")

# Pré-processamento para sistema de recomendação
def preprocess_data(df):
    """Preprocessa os dados para o sistema de recomendação."""
    df['Genres'] = df['Genres'].apply(lambda x: ' '.join(eval(x)))
    tfidf = TfidfVectorizer()
    genre_matrix = tfidf.fit_transform(df['Genres'])
    df['Normalized_Rating'] = (df['Average_rating'] - df['Average_rating'].min()) / (df['Average_rating'].max() - df['Average_rating'].min())
    return genre_matrix, df

genre_matrix, df = preprocess_data(df)

# Sistema de recomendação híbrido
def get_recommendations(user_ratings: Dict[int, float], n=5):
    """Gera recomendações de filmes com base em avaliações do usuário."""
    user_genre_vector = np.zeros(genre_matrix.shape[1])
    for movie_id, rating in user_ratings.items():
        user_genre_vector += genre_matrix[movie_id].toarray()[0] * rating
    
    similarities = cosine_similarity([user_genre_vector], genre_matrix)[0]
    rated_movies = set(user_ratings.keys())
    scores = similarities * df['Normalized_Rating'].values
    
    top_indices = np.argsort(scores)[::-1]
    recommendations = []
    
    for idx in top_indices:
        if idx not in rated_movies:
            recommendations.append({
                'Film_title': df.iloc[idx]['Film_title'],
                'Average_rating': df.iloc[idx]['Average_rating'],
                'Genres': df.iloc[idx]['Genres']
            })
            if len(recommendations) == n:
                break
    
    return recommendations

# Configuração do banco de dados SQLite
def init_db():
    """Inicializa o banco de dados SQLite."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  preferences TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Modelos Pydantic
class UserPreferences(BaseModel):
    user_id: int | None = None
    ratings: Dict[int, float]

class Movie(BaseModel):
    film_title: str
    director: str
    genres: List[str]
    runtime: float
    original_language: str
    description: str
    studios: List[str]

# Endpoints da API
@app.post("/users/", response_model=dict, summary="Adicionar novo usuário", tags=["Usuários"])
async def add_user(preferences: UserPreferences):
    """Adiciona um novo usuário com suas preferências de filmes."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT INTO users (preferences) VALUES (?)", (json.dumps(preferences.ratings),))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return {"user_id": user_id, "message": "User added successfully"}

@app.post("/movies/", response_model=dict, summary="Adicionar novo filme", tags=["Filmes"])
async def add_movie(movie: Movie):
    """Adiciona um novo filme ao catálogo."""
    global df, genre_matrix
    new_movie = pd.DataFrame({
        'Film_title': [movie.film_title],
        'Director': [movie.director],
        'Genres': [' '.join(movie.genres)],
        'Runtime': [movie.runtime],
        'Original_language': [movie.original_language],
        'Description': [movie.description],
        'Studios': [str(movie.studios)],
        'Average_rating': [3.0],
        'Normalized_Rating': [0.5]
    })
    df = pd.concat([df, new_movie], ignore_index=True)
    genre_matrix, df = preprocess_data(df)
    return {"message": "Movie added successfully"}

@app.put("/users/{user_id}", response_model=dict, summary="Atualizar preferências do usuário", tags=["Usuários"])
async def update_user(user_id: int, preferences: UserPreferences):
    """Atualiza as preferências de um usuário existente."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET preferences = ? WHERE user_id = ?", (json.dumps(preferences.ratings), user_id))
    if c.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    conn.commit()
    conn.close()
    return {"message": "User preferences updated successfully"}

@app.get("/recommendations/{user_id}", response_model=dict, summary="Obter recomendações", tags=["Recomendações"])
async def get_user_recommendations(user_id: int, n: int = 5):
    """Obtém recomendações de filmes para um usuário específico."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT preferences FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_ratings = json.loads(result[0])
    recommendations = get_recommendations(user_ratings, n)
    return {"user_id": user_id, "recommendations": recommendations}