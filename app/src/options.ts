// Choices shown in the scrolling pickers. `null` (Auto-detect) means no hint is sent,
// so the model reads the instrument / timeframe from the chart itself.
// Values must match the backend hint rule: max 20 chars, [A-Za-z0-9/._:-].

export const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1D', '1W', '1M'] as const;

export const INSTRUMENTS = [
  // Major pairs
  'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD',
  // Euro crosses
  'EURGBP', 'EURJPY', 'EURCHF', 'EURAUD', 'EURCAD', 'EURNZD',
  // Sterling crosses
  'GBPJPY', 'GBPCHF', 'GBPAUD', 'GBPCAD', 'GBPNZD',
  // Other crosses
  'AUDJPY', 'AUDNZD', 'AUDCAD', 'AUDCHF', 'CADJPY', 'CADCHF', 'CHFJPY', 'NZDJPY', 'NZDCAD', 'NZDCHF',
  // Popular non-currency charts
  'XAUUSD', 'XAGUSD', 'BTCUSD', 'ETHUSD',
] as const;
