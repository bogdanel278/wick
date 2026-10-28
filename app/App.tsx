import React, { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { StatusBar } from 'expo-status-bar';
import HomeScreen from './src/screens/HomeScreen';
import ResultScreen from './src/screens/ResultScreen';
import AcknowledgementScreen from './src/screens/AcknowledgementScreen';
import type { WickAnalysis } from './src/types';
import { colors } from './src/theme';
import { ACK_STORAGE_KEY } from './src/config';

export default function App() {
  const [result, setResult] = useState<WickAnalysis | null>(null);
  // null = still checking storage
  const [acked, setAcked] = useState<boolean | null>(null);

  useEffect(() => {
    AsyncStorage.getItem(ACK_STORAGE_KEY)
      .then((v) => setAcked(v === '1'))
      .catch(() => setAcked(false));
  }, []);

  const accept = () => {
    setAcked(true);
    AsyncStorage.setItem(ACK_STORAGE_KEY, '1').catch(() => {});
  };

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.root}>
        <StatusBar style="light" />
        {acked === null ? (
          <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>
        ) : !acked ? (
          <AcknowledgementScreen onAccept={accept} />
        ) : result ? (
          <ResultScreen analysis={result} onReset={() => setResult(null)} />
        ) : (
          <HomeScreen onResult={setResult} />
        )}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
