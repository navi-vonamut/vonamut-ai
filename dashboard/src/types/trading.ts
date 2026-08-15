export interface CircuitStatus {
  status: "online" | "warning" | "offline";
  name: string;
  latency_ms?: number;
  details?: string;
  error?: string;
  collection?: string;
  embedding_model?: string;
  dimension?: number;
  demo?: boolean;
  server_time_ms?: number;
  fast_model?: string;
  deep_model?: string;
  has_api_key?: boolean;
}

export interface SystemStatusResponse {
  timestamp: number;
  all_healthy: boolean;
  circuits: {
    database?: CircuitStatus;
    qdrant?: CircuitStatus;
    bybit?: CircuitStatus;
    gemini_ai?: CircuitStatus;
    redis?: CircuitStatus;
  };
}

export interface WalletBalanceResponse {
  total_equity: number;
  available_margin: number;
  total_margin_balance?: number;
  account_type?: string;
  error?: string;
}

export interface ActivePosition {
  symbol: string;
  side: "Buy" | "Sell";
  size: number;
  entry_price: number;
  mark_price: number;
  leverage: number;
  unrealised_pnl: number;
  cur_realised_pnl?: number;
  stop_loss?: number;
  take_profit?: number;
  position_value?: number;
}

export interface CandlestickData {
  open_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FeeRateInfo {
  symbol: string;
  category: string;
  maker_fee_rate: number;
  taker_fee_rate: number;
  maker_fee_pct: number;
  taker_fee_pct: number;
  roundtrip_taker_fee_pct: number;
}

export interface ScreenerTicker {
  symbol: string;
  last_price: number;
  turnover_24h_usd: number;
  volume_24h: number;
  price_change_24h_pct: number;
  price_change_1h_pct: number;
  open_interest_usd: number;
  oi_change_pct: number;
  is_oi_growing: boolean;
  direction_bias: "BULLISH" | "BEARISH" | "VOLATILE";
  score: number;
  reason: string;
}

export interface ScreenerSnapshot {
  timestamp: number;
  scanned_count: number;
  passed_count: number;
  tickers: ScreenerTicker[];
}

export interface NewsTriageInfo {
  symbol?: string | null;
  is_tradable: boolean;
  impact_score: number;
  sentiment: "BULLISH" | "BEARISH" | "NEUTRAL";
  event_type: "LISTING" | "EXPLOIT" | "PARTNERSHIP" | "TOKENOMICS" | "REGULATORY" | "NOISE";
  summary_en: string;
  summary_ru: string;
}

export interface NewsCatalystEvent {
  id: string;
  news: {
    id: string;
    title: string;
    content: string;
    url: string;
    source: string;
    published_at: string;
  };
  triage: NewsTriageInfo;
  bybit_symbol?: string | null;
  is_available_on_bybit: boolean;
  status: "IGNORED" | "PENDING_ANALYSIS" | "ANALYZED" | "EXECUTED" | "REJECTED_RISK";
  created_at: number;
}

export interface TradingDecision {
  action: "BUY" | "SELL" | "HOLD";
  confidence: number;
  entry_price: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  risk_reward_ratio: number;
  recommended_leverage: number;
  time_horizon: string;
  reasoning_en: string;
  reasoning_ru?: string;
  risk_notes_en: string;
  risk_notes_ru?: string;
}

export interface TechnicalIndicators {
  current_price: number;
  trend: string;
  ema: {
    ema9: number;
    ema21: number;
    ema50: number;
    ema200: number;
  };
  rsi: {
    value: number;
    status: string;
  };
  macd: {
    macd: number;
    signal: number;
    histogram: number;
  };
  bollinger_bands: {
    upper: number;
    middle: number;
    lower: number;
    bandwidth_pct: number;
    percent_b: number;
  };
  atr: number;
  support_level: number;
  resistance_level: number;
  volume_ratio: number;
  orderbook_imbalance: {
    imbalance_ratio: number;
    sentiment: string;
    bid_vol: number;
    ask_vol: number;
    spread: number;
    best_bid: number;
    best_ask: number;
  };
}

export interface TradingSystemLogItem {
  id: number;
  component: string;
  message_en: string;
  message_ru?: string;
  level: string;
  created_at: string;
  details?: any;
}
