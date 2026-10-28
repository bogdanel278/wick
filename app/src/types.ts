// Mirrors contract/analysis.schema.json (WickAnalysis) exactly.

export type Status = 'ok' | 'not_a_chart';
export type ChartType = 'candlestick' | 'line' | 'bar' | 'other';
export type TrendDirection = 'up' | 'down' | 'sideways' | 'unclear';
export type TrendStrength = 'weak' | 'moderate' | 'strong';
export type LevelType = 'support' | 'resistance';
export type ScenarioLabel = 'bullish' | 'bearish' | 'neutral';

export interface ChartInfo {
  instrument: string | null;
  timeframe: string | null;
  chart_type: ChartType;
}

export interface Trend {
  direction: TrendDirection;
  strength: TrendStrength;
  summary: string;
}

export interface Level {
  type: LevelType;
  approx_price: number | null;
  description: string;
}

export interface Pattern {
  name: string;
  description: string;
}

export interface Scenario {
  label: ScenarioLabel;
  description: string;
  trigger: string;
  invalidation: string;
}

export interface Meta {
  model: string;
  prompt_version: string;
}

export interface WickAnalysis {
  id: string;
  status: Status;
  chart: ChartInfo;
  trend: Trend | null;
  levels: Level[];
  patterns: Pattern[];
  scenarios: Scenario[];
  /** 0 to 1: image and pattern clarity, not a market prediction. */
  confidence: number;
  caveats: string[];
  disclaimer: string;
  meta: Meta;
}

export interface ApiErrorBody {
  error: { code: string; message: string };
}

export interface AnalyzeInput {
  /** Already resized and JPEG-encoded by prepareImage(). */
  imageUri: string;
  instrument?: string;
  timeframe?: string;
}
