import json
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, DateTime, Boolean, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

DATABASE_URL = "sqlite:///nba_pipeline.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RawApiResponse(Base):
    __tablename__ = "raw_api_responses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint = Column(String, index=True)
    params = Column(Text)
    response_json = Column(Text)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class DimTeam(Base):
    __tablename__ = "dim_teams"
    id = Column(Integer, primary_key=True)
    abbreviation = Column(String(10))
    city = Column(String(100))
    conference = Column(String(10))
    division = Column(String(50))
    full_name = Column(String(100))
    name = Column(String(100))
    primary_color = Column(String(7), default="#1a1a2e")
    secondary_color = Column(String(7), default="#e94560")


class DimPlayer(Base):
    __tablename__ = "dim_players"
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    position = Column(String(10))
    team_id = Column(Integer, ForeignKey("dim_teams.id"))
    jersey_number = Column(String(5))


class DimGame(Base):
    __tablename__ = "dim_games"
    id = Column(Integer, primary_key=True)
    date = Column(String(20), index=True)
    season = Column(Integer)
    status = Column(String(50))
    period = Column(Integer, default=0)
    time = Column(String(20))
    home_team_id = Column(Integer, ForeignKey("dim_teams.id"))
    visitor_team_id = Column(Integer, ForeignKey("dim_teams.id"))
    home_team_score = Column(Integer, default=0)
    visitor_team_score = Column(Integer, default=0)
    postseason = Column(Boolean, default=False)
    home_team = relationship("DimTeam", foreign_keys=[home_team_id])
    visitor_team = relationship("DimTeam", foreign_keys=[visitor_team_id])


class FactBoxScore(Base):
    __tablename__ = "fact_boxscores"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("dim_games.id"), index=True)
    player_id = Column(Integer, ForeignKey("dim_players.id"))
    team_id = Column(Integer, ForeignKey("dim_teams.id"))
    min = Column(String(10))
    pts = Column(Integer, default=0)
    reb = Column(Integer, default=0)
    ast = Column(Integer, default=0)
    stl = Column(Integer, default=0)
    blk = Column(Integer, default=0)
    turnover = Column(Integer, default=0)
    fgm = Column(Integer, default=0)
    fga = Column(Integer, default=0)
    fg3m = Column(Integer, default=0)
    fg3a = Column(Integer, default=0)
    ftm = Column(Integer, default=0)
    fta = Column(Integer, default=0)
    pf = Column(Integer, default=0)
    fg_pct = Column(Float, default=0.0)
    fg3_pct = Column(Float, default=0.0)
    ft_pct = Column(Float, default=0.0)


class FactOddsSnapshot(Base):
    __tablename__ = "fact_odds_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("dim_games.id"), index=True)
    vendor = Column(String(100))
    market_type = Column(String(50))
    home_line = Column(Float)
    away_line = Column(Float)
    home_odds = Column(Float)
    away_odds = Column(Float)
    total = Column(Float)
    over_odds = Column(Float)
    under_odds = Column(Float)
    snapshot_at = Column(DateTime, default=datetime.utcnow)


class FactPropSnapshot(Base):
    __tablename__ = "fact_prop_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("dim_games.id"), index=True)
    player_id = Column(Integer, ForeignKey("dim_players.id"))
    player_name = Column(String(200))
    team_id = Column(Integer, ForeignKey("dim_teams.id"))
    prop_type = Column(String(20))
    line = Column(Float)
    over_odds = Column(Float)
    under_odds = Column(Float)
    vendor = Column(String(100))
    snapshot_at = Column(DateTime, default=datetime.utcnow)


class FeatureStore(Base):
    __tablename__ = "feature_store"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(20))
    entity_id = Column(Integer)
    feature_name = Column(String(100))
    feature_value = Column(Float)
    computed_at = Column(DateTime, default=datetime.utcnow)
    game_date = Column(String(20))


class ModelMetrics(Base):
    __tablename__ = "model_metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100))
    metric_name = Column(String(50))
    metric_value = Column(Float)
    sample_size = Column(Integer, default=0)
    trained_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    password_hash = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserPick(Base):
    __tablename__ = "user_picks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("dim_games.id"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    pick_type = Column(String(20))
    selection = Column(String(200))
    odds = Column(Float)
    stake = Column(Float, default=1.0)
    notes = Column(Text, default="")
    result = Column(String(20), default="pending")
    payout = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    graded_at = Column(DateTime, nullable=True)
    player_id = Column(Integer, ForeignKey("dim_players.id"), nullable=True)
    player_name = Column(String(200), nullable=True)
    stat_type = Column(String(20), nullable=True)
    line = Column(Float, nullable=True)
    pick_side = Column(String(10), nullable=True)
    actual_stat = Column(Float, nullable=True)


class ScoreHistory(Base):
    __tablename__ = "score_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("dim_games.id"), index=True)
    home_score = Column(Integer)
    visitor_score = Column(Integer)
    period = Column(Integer)
    recorded_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
