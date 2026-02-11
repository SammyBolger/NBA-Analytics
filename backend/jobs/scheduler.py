import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from backend.ingest.bdl_client import fetch_todays_games, fetch_games_for_dates, fetch_game_stats, fetch_recent_completed_games, fetch_all_season_games, fetch_games_for_date_range, has_api_key, fetch_players_by_team
from backend.db.models import (
    SessionLocal, DimGame, DimTeam, DimPlayer, FactBoxScore,
    FactOddsSnapshot, FactPropSnapshot, ScoreHistory, RawApiResponse, UserPick
)
import json
import os
import time as _time

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "15"))


def _get_relevant_dates():
    from backend.utils import get_nba_day_dates
    return get_nba_day_dates()


def ingest_live_games():
    if not has_api_key():
        return
    try:
        dates = _get_relevant_dates()
        games = fetch_games_for_dates(dates)
        if not games:
            return

        db = SessionLocal()
        try:
            db.add(RawApiResponse(
                endpoint="games", params=datetime.utcnow().strftime("%Y-%m-%d"),
                response_json=json.dumps(games), fetched_at=datetime.utcnow()
            ))

            for g in games:
                home = g.get("home_team", {})
                visitor = g.get("visitor_team", {})

                for t_data in [home, visitor]:
                    if t_data.get("id"):
                        existing = db.query(DimTeam).filter_by(id=t_data["id"]).first()
                        if not existing:
                            db.add(DimTeam(
                                id=t_data["id"],
                                abbreviation=t_data.get("abbreviation", ""),
                                city=t_data.get("city", ""),
                                conference=t_data.get("conference", ""),
                                division=t_data.get("division", ""),
                                full_name=t_data.get("full_name", ""),
                                name=t_data.get("name", "")
                            ))

                game = db.query(DimGame).filter_by(id=g["id"]).first()
                if game:
                    game.status = g.get("status", game.status)
                    game.period = g.get("period", game.period)
                    game.time = g.get("time", game.time)
                    game.home_team_score = g.get("home_team_score", 0) or 0
                    game.visitor_team_score = g.get("visitor_team_score", 0) or 0
                else:
                    db.add(DimGame(
                        id=g["id"],
                        date=g.get("date", "")[:10],
                        season=g.get("season", 2025),
                        status=g.get("status", ""),
                        period=g.get("period", 0) or 0,
                        time=g.get("time", ""),
                        home_team_id=home.get("id"),
                        visitor_team_id=visitor.get("id"),
                        home_team_score=g.get("home_team_score", 0) or 0,
                        visitor_team_score=g.get("visitor_team_score", 0) or 0,
                        postseason=g.get("postseason", False)
                    ))

                if g.get("status") in ("In Progress", "in progress", "2nd Qtr", "3rd Qtr", "4th Qtr", "Halftime"):
                    db.add(ScoreHistory(
                        game_id=g["id"],
                        home_score=g.get("home_team_score", 0) or 0,
                        visitor_score=g.get("visitor_team_score", 0) or 0,
                        period=g.get("period", 0) or 0,
                        recorded_at=datetime.utcnow()
                    ))

            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error ingesting games: {e}")


def ingest_box_scores():
    global _stats_api_available
    if not has_api_key():
        return
    if _stats_api_available is False:
        return
    try:
        db = SessionLocal()
        try:
            live_games = db.query(DimGame).filter(
                DimGame.status.in_(["Final", "final"])
            ).all()
            for game in live_games:
                existing = db.query(FactBoxScore).filter_by(game_id=game.id).first()
                if existing:
                    continue
                stats = fetch_game_stats(game.id)
                if stats is None:
                    _stats_api_available = False
                    logger.info("Stats API not available, disabling box score ingestion")
                    return
                if not stats:
                    continue
                _store_box_scores(db, game.id, stats)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error ingesting box scores: {e}")


def _store_box_scores(db, game_id, stats):
    for s in stats:
        player_data = s.get("player", {})
        if not player_data.get("id"):
            continue
        existing_p = db.query(DimPlayer).filter_by(id=player_data["id"]).first()
        if not existing_p:
            db.add(DimPlayer(
                id=player_data["id"],
                first_name=player_data.get("first_name", ""),
                last_name=player_data.get("last_name", ""),
                position=player_data.get("position", ""),
                team_id=s.get("team", {}).get("id")
            ))
            try:
                db.flush()
            except Exception:
                db.rollback()

        existing_bs = db.query(FactBoxScore).filter_by(
            game_id=game_id, player_id=player_data["id"]
        ).first()
        if existing_bs:
            continue

        db.add(FactBoxScore(
            game_id=game_id,
            player_id=player_data.get("id"),
            team_id=s.get("team", {}).get("id"),
            min=s.get("min", "0"),
            pts=s.get("pts", 0) or 0,
            reb=s.get("reb", 0) or 0,
            ast=s.get("ast", 0) or 0,
            stl=s.get("stl", 0) or 0,
            blk=s.get("blk", 0) or 0,
            turnover=s.get("turnover", 0) or 0,
            fgm=s.get("fgm", 0) or 0,
            fga=s.get("fga", 0) or 0,
            fg3m=s.get("fg3m", 0) or 0,
            fg3a=s.get("fg3a", 0) or 0,
            ftm=s.get("ftm", 0) or 0,
            fta=s.get("fta", 0) or 0,
            pf=s.get("pf", 0) or 0,
            fg_pct=s.get("fg_pct", 0) or 0,
            fg3_pct=s.get("fg3_pct", 0) or 0,
            ft_pct=s.get("ft_pct", 0) or 0,
        ))


def grade_picks():
    db = SessionLocal()
    try:
        pending = db.query(UserPick).filter_by(result="pending").all()
        for pick in pending:
            game = db.query(DimGame).filter_by(id=pick.game_id).first()
            if not game or game.status not in ("Final", "final"):
                continue

            if pick.pick_type == "moneyline":
                home_team = db.query(DimTeam).filter_by(id=game.home_team_id).first()
                away_team = db.query(DimTeam).filter_by(id=game.visitor_team_id).first()
                winner = home_team if game.home_team_score > game.visitor_team_score else away_team
                if winner and (winner.full_name in pick.selection or winner.abbreviation in pick.selection):
                    pick.result = "win"
                    if pick.odds > 0:
                        pick.payout = pick.stake * (1 + pick.odds / 100)
                    else:
                        pick.payout = pick.stake * (1 + 100 / abs(pick.odds))
                else:
                    pick.result = "loss"
                    pick.payout = 0

            elif pick.pick_type == "player_prop":
                if pick.player_id and pick.stat_type and pick.line is not None:
                    bs = db.query(FactBoxScore).filter_by(
                        game_id=pick.game_id, player_id=pick.player_id
                    ).first()
                    if bs:
                        stat_map = {
                            "PTS": bs.pts, "REB": bs.reb, "AST": bs.ast,
                            "STL": bs.stl, "BLK": bs.blk, "FG3M": bs.fg3m,
                            "PRA": (bs.pts or 0) + (bs.reb or 0) + (bs.ast or 0),
                        }
                        actual = stat_map.get(pick.stat_type.upper())
                        if actual is not None:
                            pick.actual_stat = float(actual)
                            if pick.pick_side == "over":
                                won = actual > pick.line
                            else:
                                won = actual < pick.line
                            if actual == pick.line:
                                pick.result = "push"
                                pick.payout = pick.stake
                            elif won:
                                pick.result = "win"
                                if pick.odds > 0:
                                    pick.payout = pick.stake * (1 + pick.odds / 100)
                                else:
                                    pick.payout = pick.stake * (1 + 100 / abs(pick.odds))
                            else:
                                pick.result = "loss"
                                pick.payout = 0

            pick.graded_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def _get_season_start():
    now = datetime.utcnow()
    year = now.year if now.month >= 10 else now.year - 1
    return f"{year}-10-15"


def _get_current_season():
    now = datetime.utcnow()
    return now.year if now.month >= 10 else now.year - 1


def _store_games_batch(db, games):
    added = 0
    for g in games:
        try:
            home = g.get("home_team", {})
            visitor = g.get("visitor_team", {})

            for t_data in [home, visitor]:
                if t_data.get("id"):
                    existing_team = db.query(DimTeam).filter_by(id=t_data["id"]).first()
                    if not existing_team:
                        db.add(DimTeam(
                            id=t_data["id"],
                            abbreviation=t_data.get("abbreviation", ""),
                            city=t_data.get("city", ""),
                            conference=t_data.get("conference", ""),
                            division=t_data.get("division", ""),
                            full_name=t_data.get("full_name", ""),
                            name=t_data.get("name", "")
                        ))
                        db.flush()

            game_status = g.get("status", "")
            if game_status and "final" in game_status.lower():
                game_status = "Final"

            existing_game = db.query(DimGame).filter_by(id=g["id"]).first()
            if existing_game:
                existing_game.status = game_status or existing_game.status
                existing_game.home_team_score = g.get("home_team_score", 0) or existing_game.home_team_score or 0
                existing_game.visitor_team_score = g.get("visitor_team_score", 0) or existing_game.visitor_team_score or 0
            else:
                db.add(DimGame(
                    id=g["id"],
                    date=g.get("date", "")[:10],
                    season=g.get("season", 2025),
                    status=game_status or "Scheduled",
                    period=g.get("period", 0),
                    time=g.get("time", ""),
                    home_team_id=home.get("id"),
                    visitor_team_id=visitor.get("id"),
                    home_team_score=g.get("home_team_score", 0) or 0,
                    visitor_team_score=g.get("visitor_team_score", 0) or 0,
                    postseason=g.get("postseason", False)
                ))
            db.flush()
            added += 1
        except Exception as e:
            db.rollback()
            logger.debug(f"Skipping game {g.get('id')}: {e}")
    db.commit()
    return added


def seed_historical_games():
    if not has_api_key():
        return
    db = SessionLocal()
    try:
        total_game_count = db.query(DimGame).count()
        if total_game_count >= 800:
            logger.info(f"Already have {total_game_count} games in DB, skipping initial seed")
            _seed_box_scores_for_games(db)
            return

        logger.info("Fetching 2025-26 season games via season endpoint...")
        season = _get_current_season()
        games = fetch_all_season_games(season=season, max_pages=30)
        logger.info(f"Got {len(games)} games from season endpoint")

        added = _store_games_batch(db, games)
        logger.info(f"Stored {added} games from season endpoint")

        total = db.query(DimGame).count()
        final_count = db.query(DimGame).filter(DimGame.status.in_(["Final", "final"])).count()
        logger.info(f"After initial seed: {total} total games, {final_count} final")

        _seed_box_scores_for_games(db)

        from backend.models.ml_models import train_win_probability_model, train_player_prop_model
        result = train_win_probability_model()
        logger.info(f"Win model training result: {result}")
        for prop in ["PTS", "REB", "AST", "STL", "BLK"]:
            r = train_player_prop_model(prop)
            logger.info(f"Player prop {prop} model: {r}")
    except Exception as e:
        logger.error(f"Error seeding historical games: {e}")
    finally:
        db.close()


_backfill_checked_dates = set()


def backfill_calendar_games():
    if not has_api_key():
        return
    db = SessionLocal()
    try:
        from datetime import timedelta
        today = datetime.utcnow().strftime("%Y-%m-%d")

        existing_dates = set()
        all_games = db.query(DimGame.date).distinct().all()
        for (d,) in all_games:
            if d:
                existing_dates.add(d)

        season_start = _get_season_start()
        start = datetime.strptime(season_start, "%Y-%m-%d")
        end = datetime.strptime(today, "%Y-%m-%d")
        missing_dates = []
        current = start
        while current <= end:
            ds = current.strftime("%Y-%m-%d")
            if ds not in existing_dates and ds not in _backfill_checked_dates:
                missing_dates.append(ds)
            current += timedelta(days=1)

        if not missing_dates:
            logger.info("Calendar backfill complete - all dates checked")
            return

        batch = missing_dates[:7]
        logger.info(f"Backfilling {len(batch)} dates (of {len(missing_dates)} remaining): {batch[0]} to {batch[-1]}")
        games = fetch_games_for_dates(batch)
        if games:
            added = _store_games_batch(db, games)
            logger.info(f"Backfill added {added} games")
        else:
            logger.info(f"No games for these dates (off-days)")

        for d in batch:
            _backfill_checked_dates.add(d)

        total = db.query(DimGame).count()
        logger.info(f"After backfill: {total} total games in DB")
    except Exception as e:
        logger.error(f"Error in calendar backfill: {e}")
    finally:
        db.close()


_stats_api_available = None

def _seed_box_scores_for_games(db):
    global _stats_api_available
    if not has_api_key():
        return
    if _stats_api_available is False:
        logger.info("Stats API not available (free tier), skipping box score fetch")
        return

    games_without_bs = db.query(DimGame).filter(
        DimGame.status.in_(["Final", "final"])
    ).all()

    games_needing_bs = []
    for g in games_without_bs:
        has_bs = db.query(FactBoxScore).filter_by(game_id=g.id).first()
        if not has_bs:
            games_needing_bs.append(g)

    if not games_needing_bs:
        return

    logger.info(f"Found {len(games_needing_bs)} games needing box scores, testing first...")
    first_game = games_needing_bs[0]
    stats = fetch_game_stats(first_game.id)
    if stats is None:
        _stats_api_available = False
        logger.info("Stats/box scores API not available (likely requires paid tier). Using season averages for player projections instead.")
        return
    if stats == []:
        logger.info("No box scores for first game, will retry later")
        return

    _stats_api_available = True
    _store_box_scores(db, first_game.id, stats)
    db.commit()

    fetched = 1
    for g in games_needing_bs[1:29]:
        try:
            stats = fetch_game_stats(g.id)
            if stats:
                _store_box_scores(db, g.id, stats)
                db.commit()
                fetched += 1
            _time.sleep(0.5)
        except Exception as e:
            db.rollback()
            logger.debug(f"Error fetching box scores for game {g.id}: {e}")

    logger.info(f"Seeded box scores for {fetched} games")
    bs_count = db.query(FactBoxScore).count()
    player_count = db.query(DimPlayer).count()
    logger.info(f"Total box scores: {bs_count}, Total players: {player_count}")


def seed_team_rosters():
    if not has_api_key():
        return
    db = SessionLocal()
    try:
        teams = db.query(DimTeam).all()
        team_ids_needing_roster = []
        for t in teams:
            player_count = db.query(DimPlayer).filter_by(team_id=t.id).count()
            if player_count < 5:
                team_ids_needing_roster.append(t.id)

        if not team_ids_needing_roster:
            logger.info(f"All {len(teams)} teams have rosters, skipping roster seed")
            return

        logger.info(f"Fetching rosters for {len(team_ids_needing_roster)} teams...")
        fetched = 0
        for tid in team_ids_needing_roster:
            try:
                api_players = fetch_players_by_team(tid)
                for ap in api_players:
                    existing = db.query(DimPlayer).filter_by(id=ap["id"]).first()
                    if not existing:
                        db.add(DimPlayer(
                            id=ap["id"],
                            first_name=ap.get("first_name", ""),
                            last_name=ap.get("last_name", ""),
                            position=ap.get("position", ""),
                            team_id=tid,
                            jersey_number=ap.get("jersey_number"),
                        ))
                db.commit()
                fetched += 1
                _time.sleep(0.3)
            except Exception as e:
                db.rollback()
                logger.debug(f"Error fetching roster for team {tid}: {e}")

        total_players = db.query(DimPlayer).count()
        logger.info(f"Roster seed complete: fetched for {fetched} teams, {total_players} total players")
    except Exception as e:
        logger.error(f"Error seeding rosters: {e}")
    finally:
        db.close()


def daily_retrain():
    try:
        from backend.models.ml_models import train_win_probability_model, train_player_prop_model
        result = train_win_probability_model()
        logger.info(f"Daily retrain - Win model: {result}")
        for prop in ["PTS", "REB", "AST", "STL", "BLK"]:
            r = train_player_prop_model(prop)
            logger.info(f"Daily retrain - {prop} model: {r}")
    except Exception as e:
        logger.error(f"Error in daily retrain: {e}")


def start_scheduler():
    if scheduler.running:
        return

    scheduler.add_job(ingest_live_games, 'interval', seconds=REFRESH_SECONDS, id='ingest_games',
                      replace_existing=True, max_instances=1)
    scheduler.add_job(ingest_box_scores, 'interval', minutes=5, id='ingest_boxscores',
                      replace_existing=True, max_instances=1)
    scheduler.add_job(grade_picks, 'interval', minutes=10, id='grade_picks',
                      replace_existing=True, max_instances=1)
    scheduler.add_job(backfill_calendar_games, 'interval', minutes=2, id='backfill_calendar',
                      replace_existing=True, max_instances=1)
    scheduler.add_job(daily_retrain, 'cron', hour=6, minute=0, id='daily_retrain',
                      replace_existing=True, max_instances=1)
    scheduler.start()
    logger.info("Scheduler started")

    import threading
    threading.Thread(target=seed_historical_games, daemon=True).start()
    threading.Thread(target=seed_team_rosters, daemon=True).start()
