import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { TrendDirection, WickAnalysis } from '../types';
import { FALLBACK_DISCLAIMER } from '../config';
import { Card, Section } from '../components/Section';
import { colors, fonts, space } from '../theme';

interface Props {
  analysis: WickAnalysis;
  onReset: () => void;
}

const DIRECTION: Record<TrendDirection, { label: string; arrow: string; color: string }> = {
  up: { label: 'Upward', arrow: '↗', color: colors.up },
  down: { label: 'Downward', arrow: '↘', color: colors.down },
  sideways: { label: 'Sideways', arrow: '→', color: colors.flat },
  unclear: { label: 'Unclear', arrow: '?', color: colors.unclear },
};

const STRENGTH_BARS = { weak: 1, moderate: 2, strong: 3 } as const;

function formatPrice(p: number | null): string {
  if (p === null) return 'not legible';
  return Math.abs(p) >= 100 ? p.toFixed(2) : String(Number(p.toPrecision(6)));
}

function clarityLabel(value: number): 'Low' | 'Medium' | 'High' {
  const v = Number.isFinite(value) ? value : 0;
  return v < 0.4 ? 'Low' : v < 0.7 ? 'Medium' : 'High';
}

function ImageClarity({ value }: { value: number }) {
  const label = clarityLabel(value);
  return (
    <View accessible accessibilityLabel={`Image clarity: ${label}. How readable the chart was, not a forecast.`}>
      <Text style={styles.clarityValue}>Image clarity: {label}</Text>
      <Text style={styles.meterNote}>How readable the chart was, not a forecast.</Text>
    </View>
  );
}

export default function ResultScreen({ analysis, onReset }: Props) {
  const a = analysis;
  const caveats = a.caveats ?? [];
  const disclaimer = a.disclaimer?.trim() ? a.disclaimer : FALLBACK_DISCLAIMER;
  const notChart = a.status === 'not_a_chart';
  const dir = a.trend ? DIRECTION[a.trend.direction] : null;
  const meta = [a.chart.instrument, a.chart.timeframe, a.chart.chart_type !== 'other' ? a.chart.chart_type : null]
    .filter(Boolean)
    .join('  ·  ');

  return (
    <View style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.aiLabel} accessibilityRole="text">AI-generated analysis</Text>
        <Text style={styles.topDisclaimer}>
          Educational analysis, not financial advice or a personal recommendation.
        </Text>
        {notChart ? (
          <View style={styles.notChart}>
            <Text style={styles.notChartTitle}>This doesn't look like a chart</Text>
            <Text style={styles.body}>
              Wick reads price charts such as candlestick, line or bar charts. Try a clearer screenshot
              that shows the price axis and a stretch of price history.
            </Text>
            {caveats.map((c, i) => (
              <Text key={i} style={styles.caveat}>{c}</Text>
            ))}
            <Pressable style={styles.button} onPress={onReset} accessibilityRole="button" accessibilityLabel="Try another image">
              <Text style={styles.buttonText}>Try another image</Text>
            </Pressable>
          </View>
        ) : (
          <>
            {meta !== '' && <Text style={styles.meta}>{meta}</Text>}

            {a.trend && dir && (
              <View style={[styles.hero, { borderColor: dir.color }]}>
                <View style={styles.heroTop}>
                  <Text style={[styles.arrow, { color: dir.color }]}>{dir.arrow}</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.heroLabel}>Trend</Text>
                    <Text style={[styles.heroValue, { color: dir.color }]}>{dir.label}</Text>
                  </View>
                  <View style={styles.strength}>
                    <View style={styles.bars}>
                      {[1, 2, 3].map((n) => (
                        <View
                          key={n}
                          style={[
                            styles.bar,
                            { height: 8 + n * 6 },
                            n <= STRENGTH_BARS[a.trend!.strength]
                              ? { backgroundColor: dir.color }
                              : { backgroundColor: colors.border },
                          ]}
                        />
                      ))}
                    </View>
                    <Text style={styles.strengthLabel}>{a.trend.strength}</Text>
                  </View>
                </View>
                <Text style={styles.body}>{a.trend.summary}</Text>
              </View>
            )}

            <Section title="Image clarity">
              <ImageClarity value={a.confidence} />
            </Section>

            {a.levels.length > 0 && (
              <Section title="Support and resistance">
                {a.levels.map((l, i) => (
                  <Card key={i}>
                    <View style={styles.levelHead}>
                      <Text style={styles.levelType}>{l.type === 'support' ? 'Support' : 'Resistance'}</Text>
                      <Text style={[styles.price, l.approx_price === null && { color: colors.unclear }]}>
                        {l.approx_price === null ? 'price not legible' : `~${formatPrice(l.approx_price)}`}
                      </Text>
                    </View>
                    <Text style={styles.body}>{l.description}</Text>
                  </Card>
                ))}
              </Section>
            )}

            {a.patterns.length > 0 && (
              <Section title="Patterns">
                {a.patterns.map((p, i) => (
                  <Card key={i}>
                    <Text style={styles.cardTitle}>{p.name}</Text>
                    <Text style={styles.body}>{p.description}</Text>
                  </Card>
                ))}
              </Section>
            )}

            {a.scenarios.length > 0 && (
              <Section title="Illustrative scenarios">
                {a.scenarios.map((s, i) => (
                  <Card key={i}>
                    <Text style={styles.cardTitle}>
                      {s.label.charAt(0).toUpperCase() + s.label.slice(1)} scenario
                    </Text>
                    <Text style={styles.body}>{s.description}</Text>
                    <Text style={styles.kv}><Text style={styles.k}>Supported if  </Text>{s.trigger}</Text>
                    <Text style={styles.kv}><Text style={styles.k}>Undermined if  </Text>{s.invalidation}</Text>
                  </Card>
                ))}
              </Section>
            )}

            {caveats.length > 0 && (
              <Section title="Caveats">
                {caveats.map((c, i) => (
                  <Text key={i} style={styles.caveat}>{'•'}  {c}</Text>
                ))}
              </Section>
            )}

            <Pressable style={[styles.button, styles.buttonGhost]} onPress={onReset} accessibilityRole="button" accessibilityLabel="Analyze another chart">
              <Text style={[styles.buttonText, { color: colors.accent }]}>Analyze another chart</Text>
            </Pressable>
          </>
        )}
      </ScrollView>

      <View style={styles.disclaimer}>
        <Text style={styles.disclaimerText}>{disclaimer}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: space.lg, paddingBottom: space.xl },
  meta: { color: colors.textMuted, fontSize: 13, letterSpacing: 1, marginBottom: space.md },
  hero: {
    backgroundColor: colors.surface, borderWidth: 1, borderRadius: 16, padding: space.md,
  },
  heroTop: { flexDirection: 'row', alignItems: 'center', marginBottom: space.md },
  arrow: { fontSize: 44, width: 56, fontWeight: '200' },
  heroLabel: { color: colors.textMuted, fontSize: 13, letterSpacing: 1.5, textTransform: 'uppercase' },
  heroValue: { fontFamily: fonts.serif, fontSize: 30 },
  strength: { alignItems: 'center' },
  bars: { flexDirection: 'row', alignItems: 'flex-end', gap: 4, height: 26 },
  bar: { width: 8, borderRadius: 2 },
  strengthLabel: { color: colors.textMuted, fontSize: 13, marginTop: 4 },
  body: { color: colors.text, fontSize: 15, lineHeight: 22 },
  cardTitle: { color: colors.text, fontSize: 16, fontWeight: '600', marginBottom: 4 },
  levelHead: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  levelType: { color: colors.text, fontSize: 16, fontWeight: '600' },
  price: { color: colors.accent, fontFamily: fonts.mono, fontSize: 15 },
  kv: { color: colors.text, fontSize: 14, lineHeight: 20, marginTop: space.sm },
  k: { color: colors.textMuted, fontSize: 13, letterSpacing: 1, textTransform: 'uppercase' },
  clarityValue: { color: colors.text, fontSize: 16, fontWeight: '600' },
  aiLabel: { color: colors.accent, fontSize: 13, letterSpacing: 1, textTransform: 'uppercase', marginBottom: space.xs },
  topDisclaimer: { color: colors.text, fontSize: 14, lineHeight: 20, marginBottom: space.md },
  meterNote: { color: colors.textMuted, fontSize: 13, marginTop: space.sm, lineHeight: 18 },
  caveat: { color: colors.textMuted, fontSize: 14, lineHeight: 21, marginBottom: 4 },
  notChart: { paddingTop: space.xl },
  notChartTitle: { fontFamily: fonts.serif, fontSize: 28, color: colors.text, marginBottom: space.md },
  button: {
    backgroundColor: colors.accent, borderRadius: 12, paddingVertical: 16,
    alignItems: 'center', marginTop: space.lg, minHeight: 44,
  },
  buttonGhost: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.accent },
  buttonText: { color: colors.bg, fontSize: 16, fontWeight: '600', letterSpacing: 0.5 },
  disclaimer: {
    backgroundColor: colors.surfaceAlt, borderTopWidth: 1, borderTopColor: colors.border,
    paddingHorizontal: space.lg, paddingVertical: space.sm + 2,
  },
  disclaimerText: { color: colors.text, fontSize: 14, textAlign: 'center', lineHeight: 20 },
});
