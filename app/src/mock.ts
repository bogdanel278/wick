import type { WickAnalysis } from './types';

export const MOCK_ANALYSIS: WickAnalysis = {
  id: 'mock-001',
  status: 'ok',
  chart: { instrument: 'EURUSD', timeframe: '4h', chart_type: 'candlestick' },
  trend: {
    direction: 'up',
    strength: 'moderate',
    summary: 'Higher highs and higher lows since the swing low, with momentum slowing near the upper channel line.',
  },
  levels: [
    { type: 'resistance', approx_price: 1.099, description: 'Rejected at this zone last week.' },
    { type: 'support', approx_price: 1.085, description: 'Prior swing low, tested twice.' },
    { type: 'support', approx_price: null, description: 'Lower channel line; price label is not legible.' },
  ],
  patterns: [
    { name: 'Ascending channel', description: 'Price is respecting both channel lines.' },
  ],
  scenarios: [
    {
      label: 'bullish',
      description: 'A breakout continues the uptrend structure.',
      trigger: 'Candle close above 1.0990',
      invalidation: 'Candle close below 1.0850',
    },
    {
      label: 'bearish',
      description: 'A failed breakout turns the channel into a range.',
      trigger: 'Candle close below 1.0850',
      invalidation: 'Candle close above 1.0990',
    },
    {
      label: 'neutral',
      description: 'Price keeps oscillating between the two levels.',
      trigger: 'Repeated closes between 1.0850 and 1.0990',
      invalidation: 'A decisive close outside that range',
    },
  ],
  confidence: 0.62,
  caveats: ['Price labels are partly cut off; levels are approximate.'],
  disclaimer: 'Educational chart analysis, not financial advice.',
  meta: { model: 'mock', prompt_version: 'mock' },
};

export const MOCK_NOT_A_CHART: WickAnalysis = {
  id: 'mock-002',
  status: 'not_a_chart',
  chart: { instrument: null, timeframe: null, chart_type: 'other' },
  trend: null,
  levels: [],
  patterns: [],
  scenarios: [],
  confidence: 0,
  caveats: ['The image does not appear to contain a price chart.'],
  disclaimer: 'Educational chart analysis, not financial advice.',
  meta: { model: 'mock', prompt_version: 'mock' },
};
