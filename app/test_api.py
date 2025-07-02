import pytest
from fastapi.testclient import TestClient
from movie_recommendation_system import app, init_db, get_recommendations
import sqlite3
import json

client = TestClient(app)

@pytest.fixture
def setup_db():
    init_db()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT INTO users (preferences) VALUES (?)", (json.dumps({0: 4.0, 1: 3.5}),))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return user_id

def test_add_user():
    response = client.post("/users/", json={"ratings": {2: 4.5, 3: 3.0}})
    assert response.status_code == 200
    assert "user_id" in response.json()
    assert response.json()["message"] == "User added successfully"

def test_add_movie():
    movie_data = {
        "film_title": "Test Movie",
        "director": "Test Director",
        "genres": ["Drama", "Comedy"],
        "runtime": 100.0,
        "original_language": "English",
        "description": "A test movie",
        "studios": ["Test Studio"]
    }
    response = client.post("/movies/", json=movie_data)
    assert response.status_code == 200
    assert response.json()["message"] == "Movie added successfully"

def test_update_user(setup_db):
    user_id = setup_db
    response = client.put(f"/users/{user_id}", json={"ratings": {4: 5.0, 5: 2.5}})
    assert response.status_code == 200
    assert response.json()["message"] == "User preferences updated successfully"

def test_update_user_not_found():
    response = client.put("/users/9999", json={"ratings": {4: 5.0}})
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

def test_get_recommendations(setup_db):
    user_id = setup_db
    response = client.get(f"/recommendations/{user_id}?n=3")
    assert response.status_code == 200
    assert "recommendations" in response.json()
    assert len(response.json()["recommendations"]) == 3

def test_get_recommendations_not_found():
    response = client.get("/recommendations/9999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

def test_get_recommendations_function():
    user_ratings = {0: 4.0, 1: 3.5}
    recommendations = get_recommendations(user_ratings, n=2)
    assert len(recommendations) == 2
    assert all(isinstance(rec, dict) for rec in recommendations)
    assert all("Film_title" in rec for rec in recommendations)