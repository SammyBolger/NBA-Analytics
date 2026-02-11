from datetime import datetime, timedelta
import os
import random
from backend.db.models import (
    SessionLocal, DimTeam, DimPlayer, DimGame, FactBoxScore,
    FactOddsSnapshot, FactPropSnapshot, ScoreHistory, UserPick, init_db
)
from backend.ingest.bdl_client import has_api_key

NBA_TEAMS = [
    (1, "ATL", "Atlanta", "East", "Southeast", "Atlanta Hawks", "Hawks", "#E03A3E", "#C1D32F"),
    (2, "BOS", "Boston", "East", "Atlantic", "Boston Celtics", "Celtics", "#007A33", "#BA9653"),
    (3, "BKN", "Brooklyn", "East", "Atlantic", "Brooklyn Nets", "Nets", "#000000", "#FFFFFF"),
    (4, "CHA", "Charlotte", "East", "Southeast", "Charlotte Hornets", "Hornets", "#1D1160", "#00788C"),
    (5, "CHI", "Chicago", "East", "Central", "Chicago Bulls", "Bulls", "#CE1141", "#000000"),
    (6, "CLE", "Cleveland", "East", "Central", "Cleveland Cavaliers", "Cavaliers", "#6F263D", "#FFB81C"),
    (7, "DAL", "Dallas", "West", "Southwest", "Dallas Mavericks", "Mavericks", "#00538C", "#002B5E"),
    (8, "DEN", "Denver", "West", "Northwest", "Denver Nuggets", "Nuggets", "#0E2240", "#FEC524"),
    (9, "DET", "Detroit", "East", "Central", "Detroit Pistons", "Pistons", "#C8102E", "#006BB6"),
    (10, "GSW", "Golden State", "West", "Pacific", "Golden State Warriors", "Warriors", "#1D428A", "#FFC72C"),
    (11, "HOU", "Houston", "West", "Southwest", "Houston Rockets", "Rockets", "#CE1141", "#000000"),
    (12, "IND", "Indiana", "East", "Central", "Indiana Pacers", "Pacers", "#002D62", "#FDBB30"),
    (13, "LAC", "Los Angeles", "West", "Pacific", "LA Clippers", "Clippers", "#C8102E", "#1D428A"),
    (14, "LAL", "Los Angeles", "West", "Pacific", "Los Angeles Lakers", "Lakers", "#552583", "#FDB927"),
    (15, "MEM", "Memphis", "West", "Southwest", "Memphis Grizzlies", "Grizzlies", "#5D76A9", "#12173F"),
    (16, "MIA", "Miami", "East", "Southeast", "Miami Heat", "Heat", "#98002E", "#F9A01B"),
    (17, "MIL", "Milwaukee", "East", "Central", "Milwaukee Bucks", "Bucks", "#00471B", "#EEE1C6"),
    (18, "MIN", "Minnesota", "West", "Northwest", "Minnesota Timberwolves", "Timberwolves", "#0C2340", "#236192"),
    (19, "NOP", "New Orleans", "West", "Southwest", "New Orleans Pelicans", "Pelicans", "#0C2340", "#C8102E"),
    (20, "NYK", "New York", "East", "Atlantic", "New York Knicks", "Knicks", "#006BB6", "#F58426"),
    (21, "OKC", "Oklahoma City", "West", "Northwest", "Oklahoma City Thunder", "Thunder", "#007AC1", "#EF6100"),
    (22, "ORL", "Orlando", "East", "Southeast", "Orlando Magic", "Magic", "#0077C0", "#C4CED4"),
    (23, "PHI", "Philadelphia", "East", "Atlantic", "Philadelphia 76ers", "76ers", "#006BB6", "#ED174C"),
    (24, "PHX", "Phoenix", "West", "Pacific", "Phoenix Suns", "Suns", "#1D1160", "#E56020"),
    (25, "POR", "Portland", "West", "Northwest", "Portland Trail Blazers", "Trail Blazers", "#E03A3E", "#000000"),
    (26, "SAC", "Sacramento", "West", "Pacific", "Sacramento Kings", "Kings", "#5A2D81", "#63727A"),
    (27, "SAS", "San Antonio", "West", "Southwest", "San Antonio Spurs", "Spurs", "#C4CED4", "#000000"),
    (28, "TOR", "Toronto", "East", "Atlantic", "Toronto Raptors", "Raptors", "#CE1141", "#000000"),
    (29, "UTA", "Utah", "West", "Northwest", "Utah Jazz", "Jazz", "#002B5C", "#00471B"),
    (30, "WAS", "Washington", "East", "Southeast", "Washington Wizards", "Wizards", "#002B5C", "#E31837"),
]

SAMPLE_PLAYERS = [
    (101, "LeBron", "James", "F", 14, "23"),
    (102, "Anthony", "Davis", "F-C", 14, "3"),
    (103, "Stephen", "Curry", "G", 10, "30"),
    (104, "Klay", "Thompson", "G", 7, "11"),
    (105, "Giannis", "Antetokounmpo", "F", 17, "34"),
    (106, "Jayson", "Tatum", "F", 2, "0"),
    (107, "Luka", "Doncic", "G", 7, "77"),
    (108, "Nikola", "Jokic", "C", 8, "15"),
    (109, "Joel", "Embiid", "C", 23, "21"),
    (110, "Shai", "Gilgeous-Alexander", "G", 21, "2"),
    (111, "Kevin", "Durant", "F", 24, "35"),
    (112, "Devin", "Booker", "G", 24, "1"),
    (113, "Ja", "Morant", "G", 15, "12"),
    (114, "Trae", "Young", "G", 1, "11"),
    (115, "Jimmy", "Butler", "F", 16, "22"),
    (116, "Bam", "Adebayo", "C", 16, "13"),
    (117, "Donovan", "Mitchell", "G", 6, "45"),
    (118, "Jalen", "Brunson", "G", 20, "11"),
    (119, "Tyrese", "Haliburton", "G", 12, "0"),
    (120, "Zion", "Williamson", "F", 19, "1"),
]

VENDORS = ["DraftKings", "FanDuel", "BetMGM", "Caesars", "PointsBet"]


def seed_database():
    init_db()
    db = SessionLocal()
    try:
        if db.query(DimTeam).count() == 0:
            for t in NBA_TEAMS:
                db.add(DimTeam(
                    id=t[0], abbreviation=t[1], city=t[2], conference=t[3],
                    division=t[4], full_name=t[5], name=t[6],
                    primary_color=t[7], secondary_color=t[8]
                ))
            for p in SAMPLE_PLAYERS:
                db.add(DimPlayer(
                    id=p[0], first_name=p[1], last_name=p[2],
                    position=p[3], team_id=p[4], jersey_number=p[5]
                ))
            db.commit()

        if not has_api_key():
            _seed_demo_data(db)
    finally:
        db.close()


def _seed_demo_data(db):
    if db.query(DimGame).filter(DimGame.id >= 900000).count() > 0:
        return

    today = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    game_pairs = [(14, 2), (10, 17), (21, 7), (8, 24), (20, 16)]

    for i, (home, away) in enumerate(game_pairs):
        game_id = 900000 + i
        is_live = i < 2
        is_final = i >= 2 and i < 4
        status = "In Progress" if is_live else ("Final" if is_final else "Scheduled")
        period = random.randint(2, 4) if is_live else (4 if is_final else 0)
        h_score = random.randint(70, 120) if (is_live or is_final) else 0
        v_score = random.randint(70, 120) if (is_live or is_final) else 0
        game_date = yesterday if is_final else today

        db.add(DimGame(
            id=game_id, date=game_date, season=2025, status=status,
            period=period, time="8:30 PM ET" if not is_live else f"Q{period} 5:42",
            home_team_id=home, visitor_team_id=away,
            home_team_score=h_score, visitor_team_score=v_score
        ))

        if is_live:
            for q in range(1, period + 1):
                db.add(ScoreHistory(
                    game_id=game_id,
                    home_score=random.randint(20, 35) * q,
                    visitor_score=random.randint(20, 35) * q,
                    period=q,
                    recorded_at=datetime.utcnow() - timedelta(minutes=(period - q) * 12)
                ))

        for vendor in VENDORS:
            spread = round(random.uniform(-8, 8), 1)
            total = round(random.uniform(210, 235), 1)
            for snap in range(3):
                snap_time = datetime.utcnow() - timedelta(minutes=snap * 30)
                mv = random.uniform(-0.5, 0.5)
                db.add(FactOddsSnapshot(
                    game_id=game_id, vendor=vendor, market_type="game",
                    home_line=spread + mv, away_line=-(spread + mv),
                    home_odds=random.randint(-200, 200),
                    away_odds=random.randint(-200, 200),
                    total=total + mv, over_odds=-110, under_odds=-110,
                    snapshot_at=snap_time
                ))

        game_players = [p for p in SAMPLE_PLAYERS if p[4] in (home, away)]
        for pl in game_players:
            for prop_type in ["PTS", "REB", "AST"]:
                base_line = {"PTS": 25.5, "REB": 8.5, "AST": 7.5}[prop_type]
                for vendor in VENDORS[:3]:
                    line = base_line + round(random.uniform(-3, 3), 1)
                    db.add(FactPropSnapshot(
                        game_id=game_id, player_id=pl[0],
                        player_name=f"{pl[1]} {pl[2]}",
                        team_id=pl[4], prop_type=prop_type,
                        line=line,
                        over_odds=random.randint(-130, -100),
                        under_odds=random.randint(-130, -100),
                        vendor=vendor, snapshot_at=datetime.utcnow()
                    ))

            if is_final:
                db.add(FactBoxScore(
                    game_id=game_id, player_id=pl[0], team_id=pl[4],
                    min=f"{random.randint(25, 38)}:00",
                    pts=random.randint(15, 40), reb=random.randint(3, 15),
                    ast=random.randint(2, 12), stl=random.randint(0, 3),
                    blk=random.randint(0, 3), turnover=random.randint(0, 5),
                    fgm=random.randint(5, 15), fga=random.randint(12, 25),
                    fg3m=random.randint(0, 6), fg3a=random.randint(2, 10),
                    ftm=random.randint(2, 10), fta=random.randint(3, 12),
                    pf=random.randint(1, 5),
                    fg_pct=round(random.uniform(0.35, 0.60), 3),
                    fg3_pct=round(random.uniform(0.25, 0.50), 3),
                    ft_pct=round(random.uniform(0.70, 0.95), 3),
                ))

    db.commit()
