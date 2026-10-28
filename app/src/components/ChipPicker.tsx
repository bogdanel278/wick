import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { colors, space } from '../theme';

interface Props {
  label: string;
  options: readonly string[];
  /** Selected option, or null for "Auto-detect". */
  value: string | null;
  onChange: (v: string | null) => void;
  disabled?: boolean;
}

/** A horizontally scrolling row of chips. The first chip is always "Auto-detect" (no hint sent). */
export default function ChipPicker({ label, options, value, onChange, disabled }: Props) {
  const items: (string | null)[] = [null, ...options];

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={styles.row}
        accessibilityRole="radiogroup"
        accessibilityLabel={label}
      >
        {items.map((item) => {
          const selected = item === value;
          const text = item ?? 'Auto-detect';
          return (
            <Pressable
              key={text}
              onPress={() => onChange(item)}
              disabled={disabled}
              hitSlop={4}
              style={[styles.chip, selected && styles.chipSelected, disabled && styles.chipDisabled]}
              accessibilityRole="radio"
              accessibilityLabel={text}
              accessibilityState={{ selected, disabled: !!disabled }}
            >
              <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{text}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: space.lg },
  label: { color: colors.textMuted, fontSize: 13, marginBottom: space.xs, letterSpacing: 0.5 },
  row: { gap: space.sm, paddingRight: space.lg },
  chip: {
    minHeight: 44, minWidth: 56, paddingHorizontal: 14, borderRadius: 22,
    borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface,
    alignItems: 'center', justifyContent: 'center',
  },
  chipSelected: { borderColor: colors.accent, backgroundColor: colors.surfaceAlt },
  chipDisabled: { opacity: 0.55 },
  chipText: { color: colors.textMuted, fontSize: 15 },
  chipTextSelected: { color: colors.accent, fontWeight: '600' },
});
