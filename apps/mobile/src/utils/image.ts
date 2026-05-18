import * as ImageManipulator from "expo-image-manipulator";

/**
 * Convert a picker-returned file URI to a JPEG on disk and return the new URI.
 *
 * iPhones save photos as HEIC by default. Even with expo-image-picker's
 * `quality` option set, the returned URI can still be HEIC — which neither
 * Replicate nor Claude Vision can decode. Running it through ImageManipulator
 * with `format: jpeg` guarantees a JPEG file on disk before we upload.
 *
 * Bonus: a `compress` value of 0.85 cuts an iPhone full-res shot from ~5 MB
 * down to ~600 KB, making uploads dramatically faster on cellular.
 */
export async function ensureJpeg(uri: string, compress = 0.85): Promise<string> {
  const result = await ImageManipulator.manipulateAsync(
    uri,
    [], // no transforms — just re-encode
    { compress, format: ImageManipulator.SaveFormat.JPEG },
  );
  return result.uri;
}
