import logging
from datetime import datetime
from sqlalchemy import func
from backend.db.models import (
    SessionLocal, FactBoxScore, DimGame, FeatureStore, DimPlayer
)

logger = logging.getLogger(__name__)


def compute_team_rolling_stats(team_id, n_games=10):
    db = SessionLocal()
    try:
        recent_games = db.query(DimGame).filter(
            ((DimGame.home_team_id == team_id) | (DimGame.visitor_team_id == team_id)),
            DimGame.status.in_(["Final", "final"])
        ).order_by(DimGame.date.desc()).limit(n_games).all()

        if not recent_games:
            return {}

        wins = 0
        total_scored = 0
        total_allowed = 0
        for g in recent_games:
            if g.home_team_id == team_id:
                total_scored += g.home_team_score or 0
                total_allowed += g.visitor_team_score or 0
                if (g.home_team_score or 0) > (g.visitor_team_score or 0):
                    wins += 1
            else:
                total_scored += g.visitor_team_score or 0
                total_allowed += g.home_team_score or 0
                if (g.visitor_team_score or 0) > (g.home_team_score or 0):
                    wins += 1

        n = len(recent_games)
        features = {
            "win_pct": wins / n if n else 0,
            "avg_scored": total_scored / n if n else 0,
            "avg_allowed": total_allowed / n if n else 0,
            "net_rating": (total_scored - total_allowed) / n if n else 0,
        }

        box_stats = db.query(
            func.avg(FactBoxScore.fg_pct),
            func.avg(FactBoxScore.fg3_pct),
            func.avg(FactBoxScore.ft_pct),
            func.avg(FactBoxScore.reb),
            func.avg(FactBoxScore.ast),
            func.avg(FactBoxScore.turnover),
        ).filter(
            FactBoxScore.team_id == team_id,
            FactBoxScore.game_id.in_([g.id for g in recent_games])
        ).first()

        if box_stats and box_stats[0] is not None:
            features["avg_fg_pct"] = float(box_stats[0] or 0)
            features["avg_fg3_pct"] = float(box_stats[1] or 0)
            features["avg_ft_pct"] = float(box_stats[2] or 0)
            features["avg_reb"] = float(box_stats[3] or 0)
            features["avg_ast"] = float(box_stats[4] or 0)
            features["avg_tov"] = float(box_stats[5] or 0)
        else:
            features["avg_fg_pct"] = 0.45
            features["avg_fg3_pct"] = 0.35
            features["avg_ft_pct"] = 0.76
            features["avg_reb"] = 44.0
            features["avg_ast"] = 24.0
            features["avg_tov"] = 14.0

        today = datetime.utcnow().strftime("%Y-%m-%d")
        for fname, fval in features.items():
            existing = db.query(FeatureStore).filter_by(
                entity_type="team", entity_id=team_id, feature_name=fname, game_date=today
            ).first()
            if existing:
                existing.feature_value = fval
                existing.computed_at = datetime.utcnow()
            else:
                db.add(FeatureStore(
                    entity_type="team", entity_id=team_id,
                    feature_name=fname, feature_value=fval,
                    game_date=today
                ))
        db.commit()
        return features
    finally:
        db.close()


def compute_player_rolling_stats(player_id, n_games=10):
    db = SessionLocal()
    try:
        recent = db.query(FactBoxScore).filter(
            FactBoxScore.player_id == player_id
        ).order_by(FactBoxScore.id.desc()).limit(n_games).all()

        if not recent:
            return {}

        n = len(recent)
        features = {
            "avg_pts": sum(b.pts or 0 for b in recent) / n,
            "avg_reb": sum(b.reb or 0 for b in recent) / n,
            "avg_ast": sum(b.ast or 0 for b in recent) / n,
            "avg_stl": sum(b.stl or 0 for b in recent) / n,
            "avg_blk": sum(b.blk or 0 for b in recent) / n,
            "avg_fg3m": sum(b.fg3m or 0 for b in recent) / n,
            "avg_fg_pct": sum(b.fg_pct or 0 for b in recent) / n,
        }

        today = datetime.utcnow().strftime("%Y-%m-%d")
        for fname, fval in features.items():
            existing = db.query(FeatureStore).filter_by(
                entity_type="player", entity_id=player_id, feature_name=fname, game_date=today
            ).first()
            if existing:
                existing.feature_value = fval
                existing.computed_at = datetime.utcnow()
            else:
                db.add(FeatureStore(
                    entity_type="player", entity_id=player_id,
                    feature_name=fname, feature_value=fval,
                    game_date=today
                ))
        db.commit()
        return features
    finally:
        db.close()
