import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.db.models import init_db
from backend.db.seed import seed_database

init_db()
seed_database()

client = TestClient(app)


def test_status():
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "has_api_key" in data


def test_games_today():
    resp = client.get("/api/games/today")
    assert resp.status_code == 200
    games = resp.json()
    assert isinstance(games, list)
    assert len(games) > 0
    assert "home_team" in games[0]
    assert "visitor_team" in games[0]


def test_odds():
    resp = client.get("/api/odds")
    assert resp.status_code == 200
    odds = resp.json()
    assert isinstance(odds, list)
    if len(odds) > 0:
        assert "current" in odds[0]
        assert "history" in odds[0]


def test_props():
    resp = client.get("/api/props")
    assert resp.status_code == 200
    props = resp.json()
    assert isinstance(props, list)
    if len(props) > 0:
        assert "player_name" in props[0]
        assert "consensus_line" in props[0]
        assert "disagreement" in props[0]


def test_edge_calculator():
    resp = client.get("/api/edge?odds=-110&true_prob=0.55")
    assert resp.status_code == 200
    data = resp.json()
    assert "implied_probability" in data
    assert "edge" in data
    assert "expected_value" in data
    assert "disclaimer" in data


def test_picks():
    resp = client.get("/api/picks")
    assert resp.status_code == 200
    data = resp.json()
    assert "picks" in data
    assert "stats" in data
    assert "win_rate" in data["stats"]


def test_create_pick():
    resp = client.post("/api/picks", json={
        "game_id": 900000, "pick_type": "moneyline",
        "selection": "Test Pick", "odds": -110, "stake": 10, "notes": "test"
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"


def test_teams():
    resp = client.get("/api/teams")
    assert resp.status_code == 200
    teams = resp.json()
    assert len(teams) == 30


def test_model_health():
    resp = client.get("/api/model/health")
    assert resp.status_code == 200
    assert "models" in resp.json()


def test_picks_export():
    resp = client.get("/api/picks/export")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
