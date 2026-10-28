# Wick app (Expo / React Native)

Upload a chart screenshot, get educational, AI-generated trend analysis from the Wick API (see `../CONTRACT.md`). Not financial advice.

## Run

```bash
cd app
npm install
cp .env.example .env     # then edit
npx expo start           # press i (iOS sim), a (Android), or scan QR with Expo Go
```

## Config (Expo public env vars)

| var | default | notes |
|---|---|---|
| `EXPO_PUBLIC_API_URL` | dev only: `http://localhost:8000` (iOS), `http://10.0.2.2:8000` (Android) | **Physical device: set it to your computer's LAN IP**, e.g. `http://192.168.1.20:8000`; localhost and 10.0.2.2 only work in simulators/emulators. **Release builds must set it, and it must be `https://`** (iOS App Transport Security and Android block cleartext HTTP). If it is missing in a non-dev build with mock off, the app shows a configuration error instead of calling anything. |
| `EXPO_PUBLIC_USE_MOCK` | `0` | `1` returns a canned response, no backend needed. Type `nochart` as the instrument to preview the not_a_chart screen. |

Restart `expo start` (with `-c`) after changing env vars.

## Behaviour notes

- First launch shows an acknowledgement screen (AI-generated, not financial advice, can be wrong). Acceptance is stored with AsyncStorage (`wick.ack.v1`).
- Terms and Privacy URLs in `src/config.ts` are **PLACEHOLDERS**. Replace them before store submission.
- Before upload the image is resized to at most 2000 px on the long side and re-encoded as JPEG (quality 0.85) with expo-image-manipulator, then checked against the 4.5 MB cap.
- Requests time out after 90 s (covers reading the body) and can be cancelled. Responses are checked by `src/validate.ts` before display.
- `confidence` is shown as "Image clarity: Low / Medium / High" (below 0.4 / below 0.7 / else), never as a probability.

## Layout

- `App.tsx` - acknowledgement gate, then Home -> Result
- `src/config.ts` - legal URLs, fallback disclaimer, upload limits
- `src/types.ts` - types mirroring `contract/analysis.schema.json`
- `src/validate.ts` - runtime type guard for API responses
- `src/image.ts` - resize/re-encode/size check
- `src/api.ts` - multipart client, error mapping, mock toggle
- `src/mock.ts` - canned responses
- `src/screens/`, `src/components/`, `src/theme.ts`

Typecheck: `npx tsc --noEmit` (after `npm install`)
