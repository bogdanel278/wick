import { Platform } from 'react-native';
import type { AnalyzeInput, WickAnalysis } from './types';
import { MOCK_ANALYSIS, MOCK_NOT_A_CHART } from './mock';
import { isWickAnalysis } from './validate';

export const USE_MOCK = process.env.EXPO_PUBLIC_USE_MOCK === '1';
const TIMEOUT_MS = 90_000;

export class AnalyzeError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

/**
 * EXPO_PUBLIC_API_URL if set. In dev builds falls back to the emulator
 * loopback address. In release builds a missing URL is a configuration error.
 */
export function getApiUrl(): string {
  const env = process.env.EXPO_PUBLIC_API_URL?.trim();
  if (env) return env.replace(/\/+$/, '');
  if (__DEV__) return Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
  throw new AnalyzeError(
    'config',
    'This build is missing its server address (EXPO_PUBLIC_API_URL). Please reinstall or contact support.',
  );
}

const FRIENDLY: Record<string, string> = {
  bad_image: 'We could not read that image. Please choose a PNG or JPEG screenshot.',
  image_too_large: 'That image is too large (limit 4.5 MB). Try a smaller or cropped screenshot.',
  model_error: 'The analysis service had a problem. Please try again in a moment.',
  rate_limited: 'Too many requests right now. Please wait a while and try again.',
};

const GENERIC = 'Something went wrong. Please try again.';
const READ_ERROR = 'Something went wrong reading the analysis, please try again.';

function errorCode(x: unknown): string | null {
  const e = (x as { error?: { code?: unknown } } | null)?.error;
  return e && typeof e.code === 'string' ? e.code : null;
}

/** `signal` lets the caller cancel (the Cancel button). */
export async function analyzeChart(input: AnalyzeInput, signal?: AbortSignal): Promise<WickAnalysis> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 1200));
    if (signal?.aborted) throw new AnalyzeError('cancelled', 'Cancelled.');
    // Handy for UI work (mock mode only): picking the 1m timeframe shows the not_a_chart state.
    return input.timeframe === '1m' ? MOCK_NOT_A_CHART : MOCK_ANALYSIS;
  }

  const apiUrl = getApiUrl();

  const form = new FormData();
  // React Native's FormData accepts { uri, name, type } for file parts.
  // The image was re-encoded as JPEG by prepareImage().
  form.append('image', { uri: input.imageUri, name: 'image.jpg', type: 'image/jpeg' } as unknown as Blob);
  if (input.instrument?.trim()) form.append('instrument', input.instrument.trim());
  if (input.timeframe?.trim()) form.append('timeframe', input.timeframe.trim());

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, TIMEOUT_MS);
  const onCancel = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', onCancel);

  let status = 0;
  let ok = false;
  let text = '';
  try {
    const res = await fetch(`${apiUrl}/analyze`, { method: 'POST', body: form, signal: controller.signal });
    status = res.status;
    ok = res.ok;
    text = await res.text(); // the timeout also covers reading the body
  } catch (e) {
    if (timedOut) {
      throw new AnalyzeError('timeout', 'The analysis is taking too long. Please try again.');
    }
    if (signal?.aborted || (e as Error)?.name === 'AbortError') {
      throw new AnalyzeError('cancelled', 'Cancelled.');
    }
    throw new AnalyzeError('network', 'Could not reach the Wick service. Check your connection and try again.');
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onCancel);
  }

  let body: unknown = null;
  try {
    body = JSON.parse(text);
  } catch {
    // Non-JSON body (for example an HTML 502 page); handled below.
  }

  if (!ok) {
    const code = errorCode(body);
    if (status === 429) throw new AnalyzeError('rate_limited', FRIENDLY.rate_limited);
    if (status === 413) throw new AnalyzeError('image_too_large', FRIENDLY.image_too_large);
    if (code && FRIENDLY[code]) throw new AnalyzeError(code, FRIENDLY[code]);
    throw new AnalyzeError('http_' + status, GENERIC);
  }
  if (!isWickAnalysis(body)) throw new AnalyzeError('bad_response', READ_ERROR);
  return body;
}
