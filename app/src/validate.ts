import type { WickAnalysis } from './types';

type Rec = Record<string, unknown>;

const isRec = (x: unknown): x is Rec => typeof x === 'object' && x !== null && !Array.isArray(x);
const isStr = (x: unknown): x is string => typeof x === 'string';
const isNum = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
const oneOf = (x: unknown, vals: readonly string[]) => isStr(x) && vals.includes(x);
const arr = (x: unknown, each: (i: unknown) => boolean): boolean => Array.isArray(x) && x.every(each);

/** Hand-written runtime check mirroring contract/analysis.schema.json (shape and enums, not maxLength). */
export function isWickAnalysis(x: unknown): x is WickAnalysis {
  if (!isRec(x)) return false;
  if (!isStr(x.id) || !oneOf(x.status, ['ok', 'not_a_chart'])) return false;

  const c = x.chart;
  if (!isRec(c)) return false;
  if (!(c.instrument === null || isStr(c.instrument))) return false;
  if (!(c.timeframe === null || isStr(c.timeframe))) return false;
  if (!oneOf(c.chart_type, ['candlestick', 'line', 'bar', 'other'])) return false;

  const t = x.trend;
  if (t !== null) {
    if (!isRec(t)) return false;
    if (!oneOf(t.direction, ['up', 'down', 'sideways', 'unclear'])) return false;
    if (!oneOf(t.strength, ['weak', 'moderate', 'strong'])) return false;
    if (!isStr(t.summary)) return false;
  }
  if (x.status === 'ok' && t === null) return false;

  const levelOk = (i: unknown) =>
    isRec(i) && oneOf(i.type, ['support', 'resistance']) &&
    (i.approx_price === null || isNum(i.approx_price)) && isStr(i.description);
  const patternOk = (i: unknown) => isRec(i) && isStr(i.name) && isStr(i.description);
  const scenarioOk = (i: unknown) =>
    isRec(i) && oneOf(i.label, ['bullish', 'bearish', 'neutral']) &&
    isStr(i.description) && isStr(i.trigger) && isStr(i.invalidation);
  if (!arr(x.levels, levelOk) || !arr(x.patterns, patternOk) || !arr(x.scenarios, scenarioOk)) return false;

  if (!isNum(x.confidence)) return false;
  if (!arr(x.caveats, isStr)) return false;
  if (!isStr(x.disclaimer)) return false;
  const m = x.meta;
  if (!isRec(m) || !isStr(m.model) || !isStr(m.prompt_version)) return false;
  return true;
}
