import React, { useRef, useState } from 'react';
import {
  ActivityIndicator, Image, KeyboardAvoidingView, Platform, Pressable,
  ScrollView, StyleSheet, Text, View,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { analyzeChart, AnalyzeError } from '../api';
import { prepareImage } from '../image';
import LegalLinks from '../components/LegalLinks';
import ChipPicker from '../components/ChipPicker';
import { INSTRUMENTS, TIMEFRAMES } from '../options';
import type { WickAnalysis } from '../types';
import { colors, fonts, space } from '../theme';

interface Props {
  onResult: (a: WickAnalysis) => void;
}

export default function HomeScreen({ onResult }: Props) {
  const [asset, setAsset] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [instrument, setInstrument] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const pick = async () => {
    setError(null);
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      setError('Photo access is needed to choose a screenshot. You can enable it in Settings.');
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 1,
    });
    if (!res.canceled && res.assets.length > 0) setAsset(res.assets[0]);
  };

  const analyze = async () => {
    if (!asset || loading) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const imageUri = await prepareImage(asset.uri, asset.width, asset.height);
      if (controller.signal.aborted) return;
      const out = await analyzeChart(
        { imageUri, instrument: instrument ?? undefined, timeframe: timeframe ?? undefined },
        controller.signal,
      );
      onResult(out);
    } catch (e) {
      if (e instanceof AnalyzeError && e.code === 'cancelled') return;
      setError(e instanceof AnalyzeError ? e.message : 'Something went wrong. Please try again.');
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  };

  const cancel = () => abortRef.current?.abort();

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.brand}>Wick</Text>
        <Text style={styles.tagline}>Read the chart. Understand the structure.</Text>

        <Pressable
          style={styles.drop}
          onPress={pick}
          disabled={loading}
          accessibilityRole="button"
          accessibilityLabel={asset ? 'Chart screenshot selected. Double tap to choose a different image' : 'Choose a chart screenshot'}
          accessibilityState={{ disabled: loading }}
        >
          {asset ? (
            <Image
              source={{ uri: asset.uri }}
              style={styles.preview}
              resizeMode="contain"
              accessible
              accessibilityRole="image"
              accessibilityLabel="Preview of the selected chart screenshot"
            />
          ) : (
            <View style={styles.dropEmpty}>
              <Text style={styles.dropIcon}>+</Text>
              <Text style={styles.dropText}>Choose a chart screenshot</Text>
            </View>
          )}
        </Pressable>
        {asset && (
          <Pressable
            onPress={pick}
            disabled={loading}
            hitSlop={8}
            style={styles.changeBtn}
            accessibilityRole="button"
            accessibilityLabel="Choose a different image"
            accessibilityState={{ disabled: loading }}
          >
            <Text style={styles.change}>Choose a different image</Text>
          </Pressable>
        )}

        <ChipPicker
          label="Currency pair (optional)"
          options={INSTRUMENTS}
          value={instrument}
          onChange={setInstrument}
          disabled={loading}
        />
        <ChipPicker
          label="Timeframe (optional)"
          options={TIMEFRAMES}
          value={timeframe}
          onChange={setTimeframe}
          disabled={loading}
        />

        {error && <Text style={styles.error}>{error}</Text>}

        <Pressable
          style={[styles.button, (!asset || loading) && styles.buttonDisabled]}
          onPress={analyze}
          disabled={!asset || loading}
          accessibilityRole="button"
          accessibilityLabel={loading ? 'Reading the chart' : 'Analyze'}
          accessibilityState={{ disabled: !asset || loading, busy: loading }}
        >
          {loading ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color={colors.bg} />
              <Text style={styles.buttonText}>  Reading the chart...</Text>
            </View>
          ) : (
            <Text style={styles.buttonText}>Analyze</Text>
          )}
        </Pressable>
        {loading && (
          <Pressable
            style={styles.cancel}
            onPress={cancel}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel="Cancel analysis"
          >
            <Text style={styles.cancelText}>Cancel</Text>
          </Pressable>
        )}
        <Text style={styles.footnote}>Educational analysis only. Not financial advice.</Text>
        <LegalLinks />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { padding: space.lg, paddingTop: space.xl },
  brand: { fontFamily: fonts.serif, fontSize: 44, color: colors.text, letterSpacing: 1 },
  tagline: { color: colors.textMuted, fontSize: 15, marginTop: space.xs, marginBottom: space.lg },
  drop: {
    height: 260, borderRadius: 16, borderWidth: 1, borderColor: colors.border,
    borderStyle: 'dashed', backgroundColor: colors.surface, overflow: 'hidden',
  },
  dropEmpty: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  dropIcon: { color: colors.accent, fontSize: 40, fontWeight: '200' },
  dropText: { color: colors.textMuted, fontSize: 15, marginTop: space.xs },
  preview: { flex: 1, width: '100%' },
  changeBtn: { minHeight: 44, justifyContent: 'center', marginTop: space.xs },
  change: { color: colors.accent, textAlign: 'center', fontSize: 14 },
  cancel: { minHeight: 44, alignItems: 'center', justifyContent: 'center', marginTop: space.sm },
  cancelText: { color: colors.accent, fontSize: 16 },
  error: { color: colors.danger, marginTop: space.md, fontSize: 14, lineHeight: 20 },
  button: {
    backgroundColor: colors.accent, borderRadius: 12, paddingVertical: 16,
    alignItems: 'center', marginTop: space.lg, minHeight: 44,
  },
  buttonDisabled: { opacity: 0.55 },
  buttonText: { color: colors.bg, fontSize: 16, fontWeight: '600', letterSpacing: 0.5 },
  loadingRow: { flexDirection: 'row', alignItems: 'center' },
  footnote: { color: colors.textMuted, fontSize: 13, textAlign: 'center', marginTop: space.md },
});
