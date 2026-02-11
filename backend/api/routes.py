import csv
import io
import math
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from backend.db.models import (
    get_db, DimGame, DimTeam, DimPlayer, FactBoxScore,
    FactOddsSnapshot, FactPropSnapshot, ScoreHistory,
    UserPick, FeatureStore, ModelMetrics, User
)
from backend.api.auth import require_user
from backend.models.ml_models import (
    predict_win_probability, train_win_probability_model,
    train_player_prop_model, predict_player_prop, get_model_health
)
from backend.ingest.bdl_client import has_api_key, fetch_players, fetch_game_stats, fetch_players_by_team, fetch_season_averages
from backend.features.engineering import compute_team_rolling_stats, compute_player_rolling_stats

router = APIRouter(prefix="/api")


@router.get("/status")
def api_status():
    return {"status": "ok", "has_api_key": has_api_key(), "timestamp": datetime.utcnow().isoformat()}


@router.get("/games/today")
def get_todays_games(db: Session = Depends(get_db)):
    from backend.utils import get_nba_day
    nba_date = get_nba_day()
    live_statuses = ["In Progress", "in progress",
        "1st Qtr", "2nd Qtr", "3rd Qtr", "4th Qtr", "Halftime", "OT", "Half"]
    query = db.query(DimGame).filter(
        (DimGame.date == nba_date) | (DimGame.status.in_(live_statuses))
    )
    games = query.all()
    if not games:
        most_recent_date = db.query(DimGame.date).order_by(desc(DimGame.date)).first()
        if most_recent_date:
            games = db.query(DimGame).filter_by(date=most_recent_date[0]).all()
        else:
            games = []

    result = []
    for g in games:
        home = db.query(DimTeam).filter_by(id=g.home_team_id).first()
        away = db.query(DimTeam).filter_by(id=g.visitor_team_id).first()
        momentum = db.query(ScoreHistory).filter_by(game_id=g.id).order_by(ScoreHistory.recorded_at).all()
        result.append({
            "id": g.id, "date": g.date, "status": g.status,
            "period": g.period, "time": g.time,
            "home_team": _team_dict(home), "visitor_team": _team_dict(away),
            "home_team_score": g.home_team_score, "visitor_team_score": g.visitor_team_score,
            "momentum": [{"home": m.home_score, "visitor": m.visitor_score, "period": m.period,
                          "time": m.recorded_at.isoformat()} for m in momentum]
        })
    return result


@router.get("/games/calendar")
def get_calendar_games(db: Session = Depends(get_db)):
    games = db.query(DimGame).order_by(desc(DimGame.date)).all()
    dates = {}
    team_cache = {}
    for g in games:
        date_key = g.date
        if date_key not in dates:
            dates[date_key] = []
        if g.home_team_id not in team_cache:
            team_cache[g.home_team_id] = db.query(DimTeam).filter_by(id=g.home_team_id).first()
        if g.visitor_team_id not in team_cache:
            team_cache[g.visitor_team_id] = db.query(DimTeam).filter_by(id=g.visitor_team_id).first()
        dates[date_key].append({
            "id": g.id, "date": g.date, "status": g.status,
            "home_team": _team_dict(team_cache[g.home_team_id]),
            "visitor_team": _team_dict(team_cache[g.visitor_team_id]),
            "home_team_score": g.home_team_score, "visitor_team_score": g.visitor_team_score,
        })
    return {"dates": dates}


@router.get("/games/{game_id}")
def get_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(DimGame).filter_by(id=game_id).first()
    if not game:
        raise HTTPException(404, "Game not found")
    home = db.query(DimTeam).filter_by(id=game.home_team_id).first()
    away = db.query(DimTeam).filter_by(id=game.visitor_team_id).first()
    box_scores = db.query(FactBoxScore).filter_by(game_id=game_id).all()
    momentum = db.query(ScoreHistory).filter_by(game_id=game_id).order_by(ScoreHistory.recorded_at).all()

    return {
        "game": {
            "id": game.id, "date": game.date, "status": game.status,
            "period": game.period, "time": game.time,
            "home_team": _team_dict(home), "visitor_team": _team_dict(away),
            "home_team_score": game.home_team_score, "visitor_team_score": game.visitor_team_score,
        },
        "box_scores": [_boxscore_dict(bs, db) for bs in box_scores],
        "momentum": [{"home": m.home_score, "visitor": m.visitor_score, "period": m.period} for m in momentum]
    }


@router.get("/odds")
def get_odds(game_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(FactOddsSnapshot)
    if game_id:
        query = query.filter_by(game_id=game_id)
    snapshots = query.order_by(desc(FactOddsSnapshot.snapshot_at)).limit(500).all()

    games_odds = {}
    for s in snapshots:
        gid = s.game_id
        if gid not in games_odds:
            game = db.query(DimGame).filter_by(id=gid).first()
            home = db.query(DimTeam).filter_by(id=game.home_team_id).first() if game else None
            away = db.query(DimTeam).filter_by(id=game.visitor_team_id).first() if game else None
            games_odds[gid] = {
                "game_id": gid,
                "home_team": _team_dict(home),
                "away_team": _team_dict(away),
                "current": [],
                "history": [],
            }

        entry = {
            "vendor": s.vendor, "market_type": s.market_type,
            "home_line": s.home_line, "away_line": s.away_line,
            "home_odds": s.home_odds, "away_odds": s.away_odds,
            "total": s.total, "over_odds": s.over_odds, "under_odds": s.under_odds,
            "snapshot_at": s.snapshot_at.isoformat() if s.snapshot_at else None,
        }
        games_odds[gid]["history"].append(entry)

    for gid in games_odds:
        history = games_odds[gid]["history"]
        vendors = {}
        for h in history:
            if h["vendor"] not in vendors:
                vendors[h["vendor"]] = h
        games_odds[gid]["current"] = list(vendors.values())

        lines = [h["home_line"] for h in games_odds[gid]["current"] if h["home_line"]]
        if lines:
            best_home = min(lines)
            games_odds[gid]["best_line"] = best_home
            spread_range = max(lines) - min(lines)
            games_odds[gid]["divergence"] = round(spread_range, 1)
            if len(history) > 1:
                first = history[-1]["home_line"] or 0
                last = history[0]["home_line"] or 0
                games_odds[gid]["movement"] = round(last - first, 1)
            else:
                games_odds[gid]["movement"] = 0

    return list(games_odds.values())


@router.get("/props")
def get_props(
    game_id: Optional[int] = None,
    player_name: Optional[str] = None,
    prop_type: Optional[str] = None,
    vendor: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(FactPropSnapshot)
    if game_id:
        query = query.filter_by(game_id=game_id)
    if player_name:
        query = query.filter(FactPropSnapshot.player_name.ilike(f"%{player_name}%"))
    if prop_type:
        query = query.filter_by(prop_type=prop_type)
    if vendor:
        query = query.filter_by(vendor=vendor)

    props = query.order_by(desc(FactPropSnapshot.snapshot_at)).limit(500).all()

    grouped = {}
    for p in props:
        key = f"{p.player_id}_{p.prop_type}"
        if key not in grouped:
            grouped[key] = {
                "player_id": p.player_id, "player_name": p.player_name,
                "team_id": p.team_id, "prop_type": p.prop_type,
                "game_id": p.game_id, "vendors": [],
            }
        grouped[key]["vendors"].append({
            "vendor": p.vendor, "line": p.line,
            "over_odds": p.over_odds, "under_odds": p.under_odds,
            "snapshot_at": p.snapshot_at.isoformat() if p.snapshot_at else None,
        })

    result = []
    for key, data in grouped.items():
        lines = [v["line"] for v in data["vendors"]]
        over_odds = [v["over_odds"] for v in data["vendors"] if v["over_odds"]]
        under_odds = [v["under_odds"] for v in data["vendors"] if v["under_odds"]]

        import statistics
        data["consensus_line"] = round(statistics.median(lines), 1) if lines else 0
        data["best_over_odds"] = max(over_odds) if over_odds else 0
        data["best_under_odds"] = max(under_odds) if under_odds else 0
        if len(lines) > 1:
            data["disagreement"] = round(statistics.stdev(lines), 2)
        else:
            data["disagreement"] = 0
        result.append(data)

    return result


@router.get("/edge")
def calculate_edge(
    odds: float = Query(...),
    true_prob: Optional[float] = None,
    game_id: Optional[int] = None,
    side: str = Query("home"),
    db: Session = Depends(get_db)
):
    if odds > 0:
        implied = 100 / (odds + 100)
    else:
        implied = abs(odds) / (abs(odds) + 100)

    model_prob = true_prob
    if model_prob is None and game_id:
        game = db.query(DimGame).filter_by(id=game_id).first()
        if game:
            probs = predict_win_probability(game.home_team_id, game.visitor_team_id)
            model_prob = probs["home_win_prob"] if side == "home" else probs["away_win_prob"]

    if model_prob is None:
        model_prob = 0.5

    edge = model_prob - implied
    if odds > 0:
        payout_mult = odds / 100
    else:
        payout_mult = 100 / abs(odds)
    ev = model_prob * payout_mult - (1 - model_prob)

    return {
        "odds": odds, "implied_probability": round(implied, 4),
        "model_probability": round(model_prob, 4),
        "edge": round(edge, 4), "expected_value": round(ev, 4),
        "recommendation_signal": "positive_ev" if ev > 0 else "negative_ev",
    }


@router.get("/model/health")
def model_health_endpoint():
    health = get_model_health()
    return {"models": health}


@router.post("/model/retrain")
def retrain_models():
    win_result = train_win_probability_model()
    results = {"win_probability": win_result}
    for prop in ["PTS", "REB", "AST", "STL", "BLK"]:
        results[f"player_prop_{prop.lower()}"] = train_player_prop_model(prop)
    return results


@router.get("/model/predict/win")
def predict_win(home_team_id: int, away_team_id: int):
    result = predict_win_probability(home_team_id, away_team_id)
    return result


@router.get("/model/predict/prop")
def predict_prop(player_id: int, prop_type: str = "PTS"):
    result = predict_player_prop(player_id, prop_type)
    if result is None:
        return {"prediction": None, "message": "Insufficient data"}
    return {"prediction": round(result, 1), "prop_type": prop_type}


class PickCreate(BaseModel):
    game_id: int
    pick_type: str
    selection: str
    odds: float
    stake: float = 1.0
    notes: str = ""
    player_id: Optional[int] = None
    player_name: Optional[str] = None
    stat_type: Optional[str] = None
    line: Optional[float] = None
    pick_side: Optional[str] = None


@router.post("/picks")
def create_pick(pick: PickCreate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    if pick.game_id:
        game = db.query(DimGame).filter_by(id=pick.game_id).first()
        if game and game.status:
            s = game.status.lower()
            if 'final' in s or 'qtr' in s or 'half' in s or 'ot' in s or 'progress' in s:
                raise HTTPException(400, "Cannot place picks on live or completed games")
        existing = db.query(UserPick).filter_by(
            game_id=pick.game_id, pick_type='moneyline', user_id=current_user.id
        ).first()
        if existing:
            existing.selection = pick.selection
            existing.odds = pick.odds
            existing.notes = pick.notes
            existing.created_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return {"id": existing.id, "status": "updated"}
    new_pick = UserPick(
        game_id=pick.game_id, pick_type=pick.pick_type,
        selection=pick.selection, odds=pick.odds,
        stake=pick.stake, notes=pick.notes,
        player_id=pick.player_id,
        player_name=pick.player_name,
        stat_type=pick.stat_type,
        line=pick.line,
        pick_side=pick.pick_side,
        user_id=current_user.id,
        created_at=datetime.utcnow()
    )
    db.add(new_pick)
    db.commit()
    db.refresh(new_pick)
    return {"id": new_pick.id, "status": "created"}


@router.get("/picks")
def get_picks(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    picks = db.query(UserPick).filter_by(user_id=current_user.id).order_by(desc(UserPick.created_at)).all()
    total_staked = sum(p.stake for p in picks)
    total_payout = sum(p.payout or 0 for p in picks)
    graded = [p for p in picks if p.result in ("win", "loss")]
    wins = [p for p in graded if p.result == "win"]
    win_rate = len(wins) / len(graded) if graded else 0
    roi = ((total_payout - total_staked) / total_staked * 100) if total_staked > 0 else 0

    return {
        "picks": [{
            "id": p.id, "game_id": p.game_id, "pick_type": p.pick_type,
            "selection": p.selection, "odds": p.odds, "stake": p.stake,
            "notes": p.notes, "result": p.result, "payout": p.payout,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "graded_at": p.graded_at.isoformat() if p.graded_at else None,
            "player_id": p.player_id, "player_name": p.player_name,
            "stat_type": p.stat_type, "line": p.line,
            "pick_side": p.pick_side, "actual_stat": p.actual_stat,
        } for p in picks],
        "stats": {
            "total_picks": len(picks),
            "wins": len(wins),
            "losses": len(graded) - len(wins),
            "pending": len([p for p in picks if p.result == "pending"]),
            "win_rate": round(win_rate, 3),
            "total_staked": round(total_staked, 2),
            "total_payout": round(total_payout, 2),
            "roi": round(roi, 2),
            "profit": round(total_payout - total_staked, 2),
        }
    }


@router.delete("/picks/{pick_id}")
def delete_pick(pick_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    pick = db.query(UserPick).filter_by(id=pick_id).first()
    if not pick:
        raise HTTPException(404, "Pick not found")
    if pick.user_id != current_user.id:
        raise HTTPException(403, "Not authorized to delete this pick")
    db.delete(pick)
    db.commit()
    return {"status": "deleted"}


@router.get("/picks/export")
def export_picks(db: Session = Depends(get_db)):
    picks = db.query(UserPick).order_by(desc(UserPick.created_at)).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "game_id", "type", "selection", "odds", "stake", "result", "payout",
                      "player_name", "stat_type", "line", "pick_side", "actual_stat", "notes", "created_at"])
    for p in picks:
        writer.writerow([p.id, p.game_id, p.pick_type, p.selection, p.odds, p.stake, p.result, p.payout,
                         p.player_name, p.stat_type, p.line, p.pick_side, p.actual_stat, p.notes,
                         p.created_at.isoformat() if p.created_at else ""])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=picks.csv"})


@router.get("/teams")
def get_teams(db: Session = Depends(get_db)):
    teams = db.query(DimTeam).all()
    return [_team_dict(t) for t in teams]


@router.get("/players")
def get_players(team_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(DimPlayer)
    if team_id:
        query = query.filter_by(team_id=team_id)
    players = query.all()
    return [{"id": p.id, "first_name": p.first_name, "last_name": p.last_name,
             "position": p.position, "team_id": p.team_id, "jersey_number": p.jersey_number} for p in players]


def _prob_to_american(prob):
    if prob is None or prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return int(-100 * prob / (1 - prob))
    else:
        return int(100 * (1 - prob) / prob)


_model_odds_cache = {"data": None, "time": 0}

@router.get("/model-odds")
def get_model_odds(db: Session = Depends(get_db)):
    import time as _time
    from datetime import timedelta

    now = _time.time()
    if _model_odds_cache["data"] and (now - _model_odds_cache["time"]) < 30:
        return _model_odds_cache["data"]

    utc_now = datetime.utcnow()
    today = utc_now.strftime("%Y-%m-%d")
    yesterday = (utc_now - timedelta(days=1)).strftime("%Y-%m-%d")
    live_statuses = ["In Progress", "in progress",
        "1st Qtr", "2nd Qtr", "3rd Qtr", "4th Qtr", "Halftime", "OT", "Half"]

    games = db.query(DimGame).filter(
        (DimGame.date.in_([today, yesterday])) | (DimGame.status.in_(live_statuses))
    ).all()

    if not games:
        games = db.query(DimGame).order_by(desc(DimGame.date)).limit(10).all()

    stats_cache = {}
    results = []
    for g in games:
        home = db.query(DimTeam).filter_by(id=g.home_team_id).first()
        away = db.query(DimTeam).filter_by(id=g.visitor_team_id).first()

        probs = predict_win_probability(g.home_team_id, g.visitor_team_id)
        home_prob = probs["home_win_prob"]
        away_prob = probs["away_win_prob"]

        home_ml = _prob_to_american(home_prob)
        away_ml = _prob_to_american(away_prob)

        if g.home_team_id not in stats_cache:
            stats_cache[g.home_team_id] = compute_team_rolling_stats(g.home_team_id)
        if g.visitor_team_id not in stats_cache:
            stats_cache[g.visitor_team_id] = compute_team_rolling_stats(g.visitor_team_id)
        home_feats = stats_cache[g.home_team_id]
        away_feats = stats_cache[g.visitor_team_id]

        pick = home if home_prob >= away_prob else away
        pick_prob = max(home_prob, away_prob)
        confidence = "High" if pick_prob >= 0.65 else "Medium" if pick_prob >= 0.55 else "Low"

        results.append({
            "game_id": g.id,
            "date": g.date,
            "status": g.status,
            "home_team": _team_dict(home),
            "away_team": _team_dict(away),
            "home_team_score": g.home_team_score,
            "visitor_team_score": g.visitor_team_score,
            "home_win_prob": round(home_prob, 4),
            "away_win_prob": round(away_prob, 4),
            "home_moneyline": home_ml,
            "away_moneyline": away_ml,
            "model_pick": _team_dict(pick),
            "model_pick_prob": round(pick_prob, 4),
            "confidence": confidence,
            "home_stats": {
                "win_pct": round(home_feats.get("win_pct", 0.5), 3),
                "avg_scored": round(home_feats.get("avg_scored", 0), 1),
                "avg_allowed": round(home_feats.get("avg_allowed", 0), 1),
                "net_rating": round(home_feats.get("net_rating", 0), 1),
            } if home_feats else None,
            "away_stats": {
                "win_pct": round(away_feats.get("win_pct", 0.5), 3),
                "avg_scored": round(away_feats.get("avg_scored", 0), 1),
                "avg_allowed": round(away_feats.get("avg_allowed", 0), 1),
                "net_rating": round(away_feats.get("net_rating", 0), 1),
            } if away_feats else None,
        })

    results.sort(key=lambda x: x["model_pick_prob"], reverse=True)
    _model_odds_cache["data"] = results
    _model_odds_cache["time"] = now
    return results


@router.get("/players/search")
def search_players(query: str = Query("", min_length=0), db: Session = Depends(get_db)):
    if not query or len(query) < 2:
        return []

    local_players = db.query(DimPlayer).filter(
        (DimPlayer.first_name.ilike(f"%{query}%")) |
        (DimPlayer.last_name.ilike(f"%{query}%"))
    ).limit(20).all()

    if local_players:
        results = []
        for p in local_players:
            team = db.query(DimTeam).filter_by(id=p.team_id).first()
            results.append({
                "id": p.id,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "full_name": f"{p.first_name} {p.last_name}",
                "position": p.position,
                "team_id": p.team_id,
                "team": _team_dict(team),
            })
        return results

    if has_api_key():
        api_players = fetch_players(search=query)
        results = []
        for p in api_players[:15]:
            team_data = p.get("team", {})
            existing = db.query(DimPlayer).filter_by(id=p["id"]).first()
            if not existing:
                db.add(DimPlayer(
                    id=p["id"],
                    first_name=p.get("first_name", ""),
                    last_name=p.get("last_name", ""),
                    position=p.get("position", ""),
                    team_id=team_data.get("id"),
                ))
            team = db.query(DimTeam).filter_by(id=team_data.get("id")).first()
            results.append({
                "id": p["id"],
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "full_name": f"{p.get('first_name', '')} {p.get('last_name', '')}",
                "position": p.get("position", ""),
                "team_id": team_data.get("id"),
                "team": _team_dict(team) if team else {
                    "abbreviation": team_data.get("abbreviation", ""),
                    "full_name": team_data.get("full_name", ""),
                    "name": team_data.get("name", ""),
                },
            })
        db.commit()
        return results

    return []


@router.get("/player-stats/{player_id}")
def get_player_stats(player_id: int, db: Session = Depends(get_db)):
    player = db.query(DimPlayer).filter_by(id=player_id).first()
    if not player:
        raise HTTPException(404, "Player not found")

    team = db.query(DimTeam).filter_by(id=player.team_id).first()

    recent_games = db.query(FactBoxScore).filter_by(
        player_id=player_id
    ).order_by(FactBoxScore.id.desc()).limit(10).all()

    game_log = []
    for bs in recent_games:
        game = db.query(DimGame).filter_by(id=bs.game_id).first()
        game_log.append({
            "game_id": bs.game_id,
            "date": game.date if game else None,
            "opponent": None,
            "pts": bs.pts, "reb": bs.reb, "ast": bs.ast,
            "stl": bs.stl, "blk": bs.blk, "turnover": bs.turnover,
            "fgm": bs.fgm, "fga": bs.fga, "fg_pct": bs.fg_pct,
            "fg3m": bs.fg3m, "fg3a": bs.fg3a,
            "ftm": bs.ftm, "fta": bs.fta,
            "min": bs.min,
        })

    rolling = compute_player_rolling_stats(player_id)

    projections = {}
    for prop_type in ["PTS", "REB", "AST", "STL", "BLK"]:
        pred = predict_player_prop(player_id, prop_type)
        if pred is not None:
            projections[prop_type] = round(pred, 1)
        elif rolling:
            key_map = {"PTS": "avg_pts", "REB": "avg_reb", "AST": "avg_ast",
                       "STL": "avg_stl", "BLK": "avg_blk"}
            projections[prop_type] = round(rolling.get(key_map.get(prop_type, "avg_pts"), 0), 1)

    averages = {}
    if rolling:
        averages = {
            "pts": round(rolling.get("avg_pts", 0), 1),
            "reb": round(rolling.get("avg_reb", 0), 1),
            "ast": round(rolling.get("avg_ast", 0), 1),
            "stl": round(rolling.get("avg_stl", 0), 1),
            "blk": round(rolling.get("avg_blk", 0), 1),
            "fg_pct": round(rolling.get("avg_fg_pct", 0), 3),
            "fg3m": round(rolling.get("avg_fg3m", 0), 1),
        }

    return {
        "player": {
            "id": player.id,
            "first_name": player.first_name,
            "last_name": player.last_name,
            "full_name": f"{player.first_name} {player.last_name}",
            "position": player.position,
            "team": _team_dict(team),
        },
        "averages": averages,
        "projections": projections,
        "game_log": game_log,
        "games_available": len(recent_games),
    }


_todays_players_cache = {"data": None, "time": 0}

@router.get("/todays-players")
def get_todays_players(db: Session = Depends(get_db)):
    import time as _time
    from datetime import timedelta

    now = _time.time()
    if _todays_players_cache["data"] and (now - _todays_players_cache["time"]) < 300:
        return _todays_players_cache["data"]

    utc_now = datetime.utcnow()
    today = utc_now.strftime("%Y-%m-%d")
    yesterday = (utc_now - timedelta(days=1)).strftime("%Y-%m-%d")
    live_statuses = ["In Progress", "in progress",
        "1st Qtr", "2nd Qtr", "3rd Qtr", "4th Qtr", "Halftime", "OT", "Half"]

    games = db.query(DimGame).filter(
        (DimGame.date.in_([today, yesterday])) | (DimGame.status.in_(live_statuses))
    ).all()

    if not games:
        games = db.query(DimGame).order_by(desc(DimGame.date)).limit(6).all()

    result = []
    for g in games:
        home = db.query(DimTeam).filter_by(id=g.home_team_id).first()
        away = db.query(DimTeam).filter_by(id=g.visitor_team_id).first()

        home_players = _get_team_players_for_game(db, g.home_team_id, g.id)
        away_players = _get_team_players_for_game(db, g.visitor_team_id, g.id)

        game_data = {
            "game_id": g.id,
            "date": g.date,
            "status": g.status,
            "home_team": _team_dict(home),
            "away_team": _team_dict(away),
            "home_team_score": g.home_team_score,
            "visitor_team_score": g.visitor_team_score,
            "home_players": home_players,
            "away_players": away_players,
        }
        result.append(game_data)

    _todays_players_cache["data"] = result
    _todays_players_cache["time"] = now
    return result


def _get_team_players_for_game(db, team_id, game_id):
    players = db.query(DimPlayer).filter_by(team_id=team_id).all()

    if not players:
        return []

    POSITION_BASELINES = {
        "G": {"PTS": 14.5, "REB": 3.2, "AST": 4.8, "STL": 1.1, "BLK": 0.3, "fg_pct": 0.44},
        "F": {"PTS": 13.0, "REB": 5.8, "AST": 2.4, "STL": 0.9, "BLK": 0.7, "fg_pct": 0.46},
        "C": {"PTS": 11.5, "REB": 8.2, "AST": 1.8, "STL": 0.6, "BLK": 1.4, "fg_pct": 0.55},
        "G-F": {"PTS": 13.5, "REB": 4.5, "AST": 3.5, "STL": 1.0, "BLK": 0.5, "fg_pct": 0.45},
        "F-G": {"PTS": 13.5, "REB": 4.5, "AST": 3.5, "STL": 1.0, "BLK": 0.5, "fg_pct": 0.45},
        "F-C": {"PTS": 12.0, "REB": 7.0, "AST": 2.0, "STL": 0.7, "BLK": 1.0, "fg_pct": 0.50},
        "C-F": {"PTS": 12.0, "REB": 7.0, "AST": 2.0, "STL": 0.7, "BLK": 1.0, "fg_pct": 0.50},
    }

    player_list = []

    for p in players:
        rolling = compute_player_rolling_stats(p.id)

        pos = (p.position or "G").strip()
        baseline = POSITION_BASELINES.get(pos, POSITION_BASELINES.get("G"))

        if rolling:
            averages = {
                "pts": round(rolling.get("avg_pts", 0), 1),
                "reb": round(rolling.get("avg_reb", 0), 1),
                "ast": round(rolling.get("avg_ast", 0), 1),
                "stl": round(rolling.get("avg_stl", 0), 1),
                "blk": round(rolling.get("avg_blk", 0), 1),
                "fg_pct": round(rolling.get("avg_fg_pct", 0), 3),
            }
        else:
            averages = {
                "pts": baseline["PTS"],
                "reb": baseline["REB"],
                "ast": baseline["AST"],
                "stl": baseline["STL"],
                "blk": baseline["BLK"],
                "fg_pct": baseline["fg_pct"],
            }

        projections = {}
        for prop_type in ["PTS", "REB", "AST", "STL", "BLK"]:
            pred = predict_player_prop(p.id, prop_type)
            if pred is not None:
                projections[prop_type] = round(pred, 1)
            elif rolling:
                key_map = {"PTS": "avg_pts", "REB": "avg_reb", "AST": "avg_ast",
                           "STL": "avg_stl", "BLK": "avg_blk"}
                projections[prop_type] = round(rolling.get(key_map.get(prop_type, ""), 0), 1)
            else:
                projections[prop_type] = baseline[prop_type]

        games_count = db.query(FactBoxScore).filter_by(player_id=p.id).count()

        player_list.append({
            "id": p.id,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "full_name": f"{p.first_name} {p.last_name}",
            "position": p.position,
            "averages": averages,
            "projections": projections,
            "games_tracked": games_count,
        })

    player_list.sort(key=lambda x: x["projections"].get("PTS", 0), reverse=True)
    return player_list[:15]


def _team_dict(t):
    if not t:
        return {}
    return {
        "id": t.id, "abbreviation": t.abbreviation, "city": t.city,
        "conference": t.conference, "division": t.division,
        "full_name": t.full_name, "name": t.name,
        "primary_color": t.primary_color, "secondary_color": t.secondary_color,
    }


def _boxscore_dict(bs, db):
    player = db.query(DimPlayer).filter_by(id=bs.player_id).first()
    return {
        "player_id": bs.player_id,
        "player_name": f"{player.first_name} {player.last_name}" if player else "Unknown",
        "team_id": bs.team_id, "min": bs.min,
        "pts": bs.pts, "reb": bs.reb, "ast": bs.ast,
        "stl": bs.stl, "blk": bs.blk, "turnover": bs.turnover,
        "fgm": bs.fgm, "fga": bs.fga, "fg_pct": bs.fg_pct,
        "fg3m": bs.fg3m, "fg3a": bs.fg3a, "fg3_pct": bs.fg3_pct,
        "ftm": bs.ftm, "fta": bs.fta, "ft_pct": bs.ft_pct,
    }
