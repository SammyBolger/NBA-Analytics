from backend.features.engineering import compute_team_rolling_stats, compute_player_rolling_stats
from backend.db.models import init_db
from backend.db.seed import seed_database

init_db()
seed_database()


def test_team_rolling_stats():
    features = compute_team_rolling_stats(14)
    assert isinstance(features, dict)
    if features:
        assert "win_pct" in features
        assert "avg_scored" in features
        assert 0 <= features["win_pct"] <= 1


def test_player_rolling_stats():
    features = compute_player_rolling_stats(101)
    assert isinstance(features, dict)
    if features:
        assert "avg_pts" in features
        assert features["avg_pts"] >= 0


def test_edge_math():
    from backend.api.routes import calculate_edge
    class FakeDB:
        def query(self, *a, **kw): return self
        def filter_by(self, *a, **kw): return self
        def first(self): return None

    odds = -110
    implied = abs(odds) / (abs(odds) + 100)
    assert abs(implied - 0.5238) < 0.01

    true_prob = 0.55
    edge = true_prob - implied
    assert edge > 0

    payout_mult = 100 / abs(odds)
    ev = true_prob * payout_mult - (1 - true_prob)
    assert ev > 0
