import os
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

async def test_sports_system():
    print("=== Testing Sports Analytics Agent System ===")
    
    # 1. Test Ingestion Worker
    from src.sports.ingestion.odds_worker import OddsIngestionWorker
    worker = OddsIngestionWorker()
    matches = await worker.fetch_and_store_odds()
    print(f"1. Odds Worker: Ingested {len(matches)} matches.")
    if matches:
        m = matches[0]
        print(f"   Match: {m['team1']} vs {m['team2']}, Odds T1: {m['odds_team1']}, Draw: {m['odds_draw']}, T2: {m['odds_team2']}")

    # 2. Test Qdrant Sports Manager
    from src.sports.rag.qdrant_sports_manager import get_qdrant_sports_manager
    qdrant_mgr = get_qdrant_sports_manager()
    success = qdrant_mgr.add_insider_post({
        "text": "СРОЧНО: У Динамо Москва травмировался основной вратарь на тренировке. В стартовом составе выйдет дублер.",
        "source": "@nobel_insider",
        "team1": "Спартак Москва",
        "team2": "Динамо Москва"
    })
    print(f"2. Qdrant Sports Manager: Insider Post added = {success}")

    context = qdrant_mgr.query_match_context("Спартак Москва", "Динамо Москва")
    print(f"   Retrieved {len(context)} context posts from Qdrant sports_context_24h.")

    # 3. Test LangGraph Workflow
    if matches:
        target_match_id = matches[0]["match_id"]
        from src.sports.agent.graph import sports_analytical_graph
        initial_state = {
            "match_id": target_match_id,
            "league": matches[0]["league"],
            "team1": matches[0]["team1"],
            "team2": matches[0]["team2"],
            "commence_time": matches[0]["commence_time"],
            "odds_team1": matches[0]["odds_team1"],
            "odds_draw": matches[0]["odds_draw"],
            "odds_team2": matches[0]["odds_team2"],
            "insider_context": [],
            "context_text": "",
            "ai_prob_team1": 0.33,
            "ai_prob_draw": None,
            "ai_prob_team2": 0.33,
            "ai_reasoning": "",
            "is_value_bet": False,
            "best_outcome": None,
            "selected_team": None,
            "selected_odds": None,
            "selected_prob": None,
            "value_percentage": None,
            "bet_record_id": None
        }

        print("3. Executing LangGraph Analytical Core...")
        res = await sports_analytical_graph.ainvoke(initial_state)
        print(f"   Graph Result -> Is Value Bet: {res['is_value_bet']}")
        print(f"   Best Outcome: {res['best_outcome']}, Odds: {res['selected_odds']}, AI Prob: {res['selected_prob']}, Value: {res['value_percentage']}")
        print(f"   AI Reasoning: {res['ai_reasoning']}")

    print("=== Test Completed Successfully ===")

if __name__ == "__main__":
    asyncio.run(test_sports_system())
