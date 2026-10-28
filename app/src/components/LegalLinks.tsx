import React from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { PRIVACY_URL, TERMS_URL } from '../config';
import { colors, space } from '../theme';

function open(url: string) {
  Linking.openURL(url).catch(() => {});
}

export default function LegalLinks() {
  return (
    <View style={styles.row}>
      <Pressable onPress={() => open(TERMS_URL)} accessibilityRole="link" accessibilityLabel="Terms of Use" hitSlop={8} style={styles.link}>
        <Text style={styles.text}>Terms</Text>
      </Pressable>
      <Text style={styles.sep}>·</Text>
      <Pressable onPress={() => open(PRIVACY_URL)} accessibilityRole="link" accessibilityLabel="Privacy Policy" hitSlop={8} style={styles.link}>
        <Text style={styles.text}>Privacy</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: space.sm },
  link: { minHeight: 44, minWidth: 44, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.md },
  text: { color: colors.accent, fontSize: 14, textDecorationLine: 'underline' },
  sep: { color: colors.textMuted, fontSize: 14 },
});
