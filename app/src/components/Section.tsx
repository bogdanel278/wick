import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, space } from '../theme';

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{title.toUpperCase()}</Text>
      {children}
    </View>
  );
}

export function Card({ children, accent }: { children: React.ReactNode; accent?: string }) {
  return (
    <View style={[styles.card, accent ? { borderLeftColor: accent, borderLeftWidth: 3 } : null]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: space.lg },
  title: { color: colors.textMuted, fontSize: 13, letterSpacing: 1.5, marginBottom: space.sm },
  card: {
    backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1,
    borderColor: colors.border, padding: space.md, marginBottom: space.sm,
  },
});
