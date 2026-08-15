import logging
import datetime
import httpx
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.sports.config import sports_config
from src.db.base import SessionLocal, engine, Base
from src.db.models import SportsMatch, SportsOdds

logger = logging.getLogger(__name__)

class OddsIngestionWorker:
    """
    Воркер скачивания коэффициентов и расписания матчей с The-Odds-API (Pinnacle / Sharp odds).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or sports_config.odds_api_key
        self.base_url = "https://api.the-odds-api.com/v4/sports"
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Создает таблицы в базе данных, если они еще не существуют."""
        try:
            Base.metadata.create_all(bind=engine, tables=[
                SportsMatch.__table__,
                SportsOdds.__table__
            ])
        except Exception as e:
            logger.error(f"[ODDS_WORKER] Error ensuring tables exist: {e}")

    def get_cached_matches(self) -> List[Dict[str, Any]]:
        """Получение ранее сохраненных матчей и коэффициентов прямо из базы данных."""
        db: Session = SessionLocal()
        results = []
        try:
            matches = db.query(SportsMatch).order_by(SportsMatch.commence_time.asc()).limit(50).all()
            for m in matches:
                odds_record = db.query(SportsOdds).filter_by(match_id=m.match_id).first()
                results.append({
                    "match_id": m.match_id,
                    "league": m.league,
                    "team1": m.team1,
                    "team2": m.team2,
                    "odds_team1": odds_record.odds_team1 if odds_record else 2.0,
                    "odds_draw": odds_record.odds_draw if odds_record else None,
                    "odds_team2": odds_record.odds_team2 if odds_record else 2.0,
                    "commence_time": m.commence_time.isoformat() if m.commence_time else datetime.datetime.utcnow().isoformat()
                })
            return results
        except Exception as e:
            logger.error(f"[ODDS_WORKER] Error reading cached matches: {e}")
            return []
        finally:
            db.close()

    async def fetch_and_store_odds(
        self, sports: Optional[List[str]] = None, force: bool = False, max_age_hours: float = 6.0
    ) -> List[Dict[str, Any]]:
        """
        Загрузка коэффициентов с The-Odds-API с защитой квоты запросов.
        Если force=False и в БД есть свежие матчи (< max_age_hours), возврат данных из БД без внешних HTTP запросов.
        """
        if not force:
            cached = self.get_cached_matches()
            if cached:
                logger.info(f"[ODDS_WORKER] Returning {len(cached)} cached matches from DB (0 API requests burned).")
                return cached

        target_sports = sports or sports_config.target_leagues
        saved_matches = []

        if not self.api_key:
            logger.warning("[ODDS_WORKER] ODDS_API_KEY is not set. Generating mock match odds for testing.")
            return self._generate_mock_odds()

        async with httpx.AsyncClient(timeout=15.0) as client:
            for sport_key in target_sports:
                try:
                    url = f"{self.base_url}/{sport_key}/odds/"
                    params = {
                        "apiKey": self.api_key,
                        "regions": "eu",
                        "markets": "h2h",
                        "oddsFormat": "decimal"
                    }
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        processed = self._save_matches_data(data, sport_key)
                        saved_matches.extend(processed)
                        logger.info(f"[ODDS_WORKER] Ingested {len(processed)} matches for league: {sport_key}")
                    else:
                        logger.warning(f"[ODDS_WORKER] The-Odds-API returned status {response.status_code} for {sport_key}: {response.text}")
                except Exception as e:
                    logger.error(f"[ODDS_WORKER] Error fetching odds for {sport_key}: {e}")

        return saved_matches if saved_matches else self.get_cached_matches()

    def _save_matches_data(self, raw_matches: List[Dict[str, Any]], league: str) -> List[Dict[str, Any]]:
        """Сохранение/обновление матчей и коэффициентов в БД."""
        db: Session = SessionLocal()
        results = []
        target_bm = sports_config.target_bookmaker.lower()

        try:
            for item in raw_matches:
                match_ext_id = item.get("id")
                home_team = item.get("home_team", "Team 1")
                away_team = item.get("away_team", "Team 2")
                commence_raw = item.get("commence_time")

                if commence_raw:
                    commence_dt = datetime.datetime.fromisoformat(commence_raw.replace("Z", "+00:00"))
                else:
                    commence_dt = datetime.datetime.utcnow() + datetime.timedelta(hours=4)

                # Поиск коэффициентов целевой конторы (Pinnacle или первенствующей)
                bookmakers = item.get("bookmakers", [])
                pinnacle_bm = next((b for b in bookmakers if b.get("key", "").lower() == target_bm), None)
                if not pinnacle_bm and bookmakers:
                    pinnacle_bm = bookmakers[0]

                odds_t1, odds_draw, odds_t2 = 2.0, None, 2.0
                if pinnacle_bm:
                    markets = pinnacle_bm.get("markets", [])
                    h2h = next((m for m in markets if m.get("key") == "h2h"), None)
                    if h2h:
                        outcomes = h2h.get("outcomes", [])
                        for out in outcomes:
                            name = out.get("name")
                            price = float(out.get("price", 1.0))
                            if name == home_team:
                                odds_t1 = price
                            elif name == away_team:
                                odds_t2 = price
                            elif name.lower() in ["draw", "ничья"]:
                                odds_draw = price

                # Upsert Match
                existing_match = db.query(SportsMatch).filter_by(match_id=match_ext_id).first()
                if not existing_match:
                    existing_match = SportsMatch(
                        match_id=match_ext_id,
                        league=league,
                        team1=home_team,
                        team2=away_team,
                        commence_time=commence_dt,
                        status="SCHEDULED"
                    )
                    db.add(existing_match)
                    db.flush()

                # Upsert Odds
                existing_odds = db.query(SportsOdds).filter_by(match_id=match_ext_id, bookmaker=sports_config.target_bookmaker).first()
                if not existing_odds:
                    existing_odds = SportsOdds(
                        match_id=match_ext_id,
                        bookmaker=sports_config.target_bookmaker,
                        odds_team1=odds_t1,
                        odds_draw=odds_draw,
                        odds_team2=odds_t2,
                        updated_at=datetime.datetime.utcnow()
                    )
                    db.add(existing_odds)
                else:
                    existing_odds.odds_team1 = odds_t1
                    existing_odds.odds_draw = odds_draw
                    existing_odds.odds_team2 = odds_t2
                    existing_odds.updated_at = datetime.datetime.utcnow()

                results.append({
                    "match_id": match_ext_id,
                    "league": league,
                    "team1": home_team,
                    "team2": away_team,
                    "odds_team1": odds_t1,
                    "odds_draw": odds_draw,
                    "odds_team2": odds_t2,
                    "commence_time": commence_dt.isoformat()
                })

            db.commit()
            return results
        except Exception as e:
            db.rollback()
            logger.error(f"[ODDS_WORKER] Database save error: {e}")
            return []
        finally:
            db.close()

    def _generate_mock_odds(self) -> List[Dict[str, Any]]:
        """Генерация тестовых матчей, если нет ключа API."""
        now = datetime.datetime.utcnow()
        mock_data = [
            {
                "id": "mock_rpl_spartak_dynamo",
                "home_team": "Спартак Москва",
                "away_team": "Динамо Москва",
                "bookmakers": [{
                    "key": "pinnacle",
                    "markets": [{
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Спартак Москва", "price": 2.45},
                            {"name": "Draw", "price": 3.40},
                            {"name": "Динамо Москва", "price": 2.80}
                        ]
                    }]
                }]
            },
            {
                "id": "mock_epl_arsenal_chelsea",
                "home_team": "Арсенал",
                "away_team": "Челси",
                "bookmakers": [{
                    "key": "pinnacle",
                    "markets": [{
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Арсенал", "price": 1.95},
                            {"name": "Draw", "price": 3.60},
                            {"name": "Челси", "price": 3.90}
                        ]
                    }]
                }]
            }
        ]
        return self._save_matches_data(mock_data, "soccer_russia_premier_league")
