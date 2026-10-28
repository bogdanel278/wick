import { Platform } from 'react-native';

export const colors = {
  bg: '#0E1116',
  surface: '#161B22',
  surfaceAlt: '#1D242D',
  border: '#262E38',
  text: '#E8E4DA',
  textMuted: '#A3ACB9', // >= 6.8:1 on bg, surface and surfaceAlt
  accent: '#D9B26F', // warm amber, like candlelight
  // Calm, desaturated directional tones.
  up: '#7FB5A3',
  down: '#C98B84',
  flat: '#9AA6B8',
  unclear: '#9AA4B2', // >= 6.2:1 on bg, surface and surfaceAlt
  danger: '#C98B84',
};

export const fonts = {
  serif: Platform.select({ ios: 'Georgia', android: 'serif', default: 'serif' }),
  mono: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }),
};

export const space = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 };
