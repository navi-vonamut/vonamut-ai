export type LeagueType = "Football" | "Basketball" | "Tennis" | "Esports" | "Hockey";

export interface BookmakerOdds {
  bookmaker: string; // e.g. "Pinnacle", "1xBet", "Bet365", "MarathonBet"
  homeOdds: number;
  drawOdds?: number;
  awayOdds: number;
  marginPercentage: number;
  lastUpdated: string;
}

export interface SportsMatchItem {
  id: string;
  match_id: string;
  sport_key: string;
  sport_title: string;
  league: string;
  team1: string;
  team2: string;
  commence_time: string;
  home_logo?: string;
  away_logo?: string;
  best_odds: {
    home: { value: number; bookmaker: string };
    draw?: { value: number; bookmaker: string };
    away: { value: number; bookmaker: string };
  };
  bookmaker_odds: BookmakerOdds[];
}

export interface ValueBetItem {
  id: string;
  match_id: string;
  league: string;
  team1: string;
  team2: string;
  commence_time: string;
  bet_target: string; // "Home (Real Madrid)" | "Draw" | "Away (Barcelona)"
  bookmaker: string;
  bookmaker_odds: number;
  ai_probability: number; // 0.0 - 1.0 (e.g. 0.58)
  implied_probability: number; // 1 / bookmaker_odds
  value_percentage: number; // EV+ edge e.g. +14.5%
  kelly_stake_percent: number; // e.g. 3.2%
  ai_reasoning: string;
  confidence: "High" | "Medium" | "Low";
  status: "ACTIVE" | "ANALYZING" | "BET_PLACED" | "EXPIRED";
  created_at: string;
}

export interface InsiderNewsItem {
  id: string;
  source: string; // e.g. "@sports_insider_es"
  team1: string;
  team2: string;
  text: string;
  impact: "CRITICAL" | "HIGH" | "MEDIUM" | "NEUTRAL";
  timestamp: string;
  vector_stored: boolean;
}

export interface BetHistoryItem {
  id: string;
  match_id: string;
  match: string;
  league: string;
  bet_target: string;
  odds: number;
  stake: number;
  potential_payout: number;
  ai_probability: number;
  value_percentage: number;
  status: "WON" | "LOST" | "PENDING" | "VOID";
  profit_loss?: number;
  user_action: "ACCEPTED" | "REJECTED" | "AUTO";
  created_at: string;
}

export interface SportsBankrollSummary {
  totalBankroll: number;
  activeStakes: number;
  totalProfit: number;
  roiPercentage: number;
  winRate: number;
  totalBetsPlaced: number;
  successfulValueBets: number;
  monthlyHistory: { date: string; bankroll: number; profit: number }[];
}

export interface MatchAnalysisResult {
  status: string;
  match: string;
  is_value_bet: boolean;
  best_outcome: string | null;
  odds: number | null;
  ai_probability: number | null;
  value_percentage: number | null;
  ai_reasoning: string;
  h2h?: { homeWins: number; draws: number; awayWins: number };
  insider_context_found?: string[];
}
