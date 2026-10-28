import * as ImageManipulator from 'expo-image-manipulator';
import { JPEG_QUALITY, MAX_LONG_SIDE_PX, MAX_UPLOAD_BYTES } from './config';
import { AnalyzeError } from './api';

/**
 * Resize (long side <= 2000 px) and re-encode as JPEG. This also converts HEIC
 * and fixes assets with a null mime type. Throws AnalyzeError('too_large') if
 * the result is still over the 4.5 MB upload cap.
 */
export async function prepareImage(uri: string, width?: number, height?: number): Promise<string> {
  const actions: ImageManipulator.Action[] = [];
  if (width && height && Math.max(width, height) > MAX_LONG_SIDE_PX) {
    actions.push({ resize: width >= height ? { width: MAX_LONG_SIDE_PX } : { height: MAX_LONG_SIDE_PX } });
  }
  let out: ImageManipulator.ImageResult;
  try {
    out = await ImageManipulator.manipulateAsync(uri, actions, {
      compress: JPEG_QUALITY,
      format: ImageManipulator.SaveFormat.JPEG,
    });
  } catch {
    throw new AnalyzeError('bad_image', 'We could not read that image. Please choose a different screenshot.');
  }
  try {
    const blob = await (await fetch(out.uri)).blob();
    if (blob.size > MAX_UPLOAD_BYTES) {
      throw new AnalyzeError('too_large', 'That image is still too large after compression (limit 4.5 MB). Try cropping the screenshot.');
    }
  } catch (e) {
    if (e instanceof AnalyzeError) throw e;
    // Size could not be measured; the server enforces the cap and returns 413.
  }
  return out.uri;
}
