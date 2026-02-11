import os
import pickle
import logging
import numpy as np
from datetime import datetime
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import brier_score_loss, mean_absolute_error
from backend.db.models import (
    SessionLocal, DimGame, DimTeam, FactBoxScore, ModelMetrics, FeatureStore
)
from backend.features.engineering import compute_team_rolling_stats, compute_player_rolling_stats

logger = logging.getLogger(__name__)
MODELS_DIR = "model_artifacts"
os.makedirs(MODELS_DIR, exist_ok=True)


def _save_model(model, name):
    path = os.path.join(MODELS_DIR, f"{name}.pkl")
    with open(path, "wb") as f:
        pickle.dump(model, f)


def _load_model(name):
    path = os.path.join(MODELS_DIR, f"{name}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


def train_win_probability_model():
    db = SessionLocal()
    try:
        games = db.query(DimGame).filter(
            DimGame.status.in_(["Final", "final"]),
            DimGame.home_team_score > 0
        ).order_by(DimGame.date.desc()).limit(200).all()

        if len(games) < 10:
            logger.warning("Not enough games to train win probability model")
            _create_default_model()
            return {"status": "created_default", "games": len(games)}

        X, y = [], []
        for game in games:
            home_feats = compute_team_rolling_stats(game.home_team_id)
            away_feats = compute_team_rolling_stats(game.visitor_team_id)
            if not home_feats or not away_feats:
                continue

            features = [
                home_feats.get("win_pct", 0.5) - away_feats.get("win_pct", 0.5),
                home_feats.get("net_rating", 0) - away_feats.get("net_rating", 0),
                home_feats.get("avg_scored", 100) - away_feats.get("avg_scored", 100),
                home_feats.get("avg_fg_pct", 0.45) - away_feats.get("avg_fg_pct", 0.45),
                0.03,
            ]
            X.append(features)
            y.append(1 if game.home_team_score > game.visitor_team_score else 0)

        if len(X) < 5:
            _create_default_model()
            return {"status": "created_default", "games": len(X)}

        X = np.array(X)
        y = np.array(y)
        model = LogisticRegression(max_iter=1000)
        model.fit(X, y)
        _save_model(model, "win_probability")

        preds = model.predict_proba(X)[:, 1]
        brier = brier_score_loss(y, preds)
        accuracy = np.mean((preds > 0.5) == y)

        db.add(ModelMetrics(
            model_name="win_probability", metric_name="brier_score",
            metric_value=brier, sample_size=len(y), trained_at=datetime.utcnow()
        ))
        db.add(ModelMetrics(
            model_name="win_probability", metric_name="accuracy",
            metric_value=accuracy, sample_size=len(y), trained_at=datetime.utcnow()
        ))
        db.commit()
        return {"status": "trained", "brier": brier, "accuracy": accuracy, "games": len(y)}
    finally:
        db.close()


def _create_default_model():
    model = LogisticRegression(max_iter=1000)
    X_dummy = np.array([[0.1, 5, 3, 0.02, 0.03], [-0.1, -5, -3, -0.02, 0.03],
                        [0.2, 8, 5, 0.04, 0.03], [-0.2, -8, -5, -0.04, 0.03]])
    y_dummy = np.array([1, 0, 1, 0])
    model.fit(X_dummy, y_dummy)
    _save_model(model, "win_probability")


def predict_win_probability(home_team_id, away_team_id):
    model = _load_model("win_probability")
    if model is None:
        _create_default_model()
        model = _load_model("win_probability")

    home_feats = compute_team_rolling_stats(home_team_id)
    away_feats = compute_team_rolling_stats(away_team_id)

    if not home_feats:
        home_feats = {"win_pct": 0.5, "net_rating": 0, "avg_scored": 100, "avg_fg_pct": 0.45}
    if not away_feats:
        away_feats = {"win_pct": 0.5, "net_rating": 0, "avg_scored": 100, "avg_fg_pct": 0.45}

    features = np.array([[
        home_feats.get("win_pct", 0.5) - away_feats.get("win_pct", 0.5),
        home_feats.get("net_rating", 0) - away_feats.get("net_rating", 0),
        home_feats.get("avg_scored", 100) - away_feats.get("avg_scored", 100),
        home_feats.get("avg_fg_pct", 0.45) - away_feats.get("avg_fg_pct", 0.45),
        0.03,
    ]])

    prob = model.predict_proba(features)[0]
    return {"home_win_prob": float(prob[1]), "away_win_prob": float(prob[0])}


def train_player_prop_model(prop_type="PTS"):
    db = SessionLocal()
    try:
        box_scores = db.query(FactBoxScore).filter(
            FactBoxScore.pts > 0
        ).order_by(FactBoxScore.id.desc()).limit(1000).all()

        if len(box_scores) < 10:
            return {"status": "insufficient_data"}

        X, y = [], []
        for bs in box_scores:
            player_feats = compute_player_rolling_stats(bs.player_id)
            if not player_feats:
                continue
            target_map = {
                "PTS": bs.pts, "REB": bs.reb, "AST": bs.ast,
                "STL": bs.stl, "BLK": bs.blk, "FG3M": bs.fg3m,
            }
            target = target_map.get(prop_type, bs.pts)
            if target is None:
                continue
            X.append([
                player_feats.get("avg_pts", 0),
                player_feats.get("avg_reb", 0),
                player_feats.get("avg_ast", 0),
                player_feats.get("avg_stl", 0),
                player_feats.get("avg_blk", 0),
                player_feats.get("avg_fg_pct", 0),
                player_feats.get("avg_fg3m", 0),
            ])
            y.append(target)

        if len(X) < 5:
            return {"status": "insufficient_data"}

        X = np.array(X)
        y = np.array(y, dtype=float)
        model = LinearRegression()
        model.fit(X, y)
        _save_model(model, f"player_prop_{prop_type.lower()}")

        preds = model.predict(X)
        mae = mean_absolute_error(y, preds)

        db.add(ModelMetrics(
            model_name=f"player_prop_{prop_type.lower()}",
            metric_name="mae", metric_value=mae,
            sample_size=len(y), trained_at=datetime.utcnow()
        ))
        db.commit()
        return {"status": "trained", "mae": mae, "samples": len(y)}
    finally:
        db.close()


def predict_player_prop(player_id, prop_type="PTS"):
    model = _load_model(f"player_prop_{prop_type.lower()}")
    if model is None:
        return None

    player_feats = compute_player_rolling_stats(player_id)
    if not player_feats:
        return None

    expected_features = model.n_features_in_ if hasattr(model, 'n_features_in_') else 7
    if expected_features == 5:
        X = np.array([[
            player_feats.get("avg_pts", 0),
            player_feats.get("avg_reb", 0),
            player_feats.get("avg_ast", 0),
            player_feats.get("avg_fg_pct", 0),
            player_feats.get("avg_fg3m", 0),
        ]])
    else:
        X = np.array([[
            player_feats.get("avg_pts", 0),
            player_feats.get("avg_reb", 0),
            player_feats.get("avg_ast", 0),
            player_feats.get("avg_stl", 0),
            player_feats.get("avg_blk", 0),
            player_feats.get("avg_fg_pct", 0),
            player_feats.get("avg_fg3m", 0),
        ]])
    try:
        pred = model.predict(X)[0]
        return max(0, float(pred))
    except Exception:
        return None


def get_model_health():
    db = SessionLocal()
    try:
        metrics = db.query(ModelMetrics).order_by(ModelMetrics.trained_at.desc()).limit(20).all()
        result = {}
        for m in metrics:
            if m.model_name not in result:
                result[m.model_name] = {}
            result[m.model_name][m.metric_name] = {
                "value": m.metric_value,
                "sample_size": m.sample_size,
                "trained_at": m.trained_at.isoformat() if m.trained_at else None,
            }
        return result
    finally:
        db.close()
