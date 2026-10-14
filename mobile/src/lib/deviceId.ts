import * as Application from 'expo-application';
import * as Device from 'expo-device';
import { Platform } from 'react-native';

import { secureStorage } from './storage';

const FALLBACK_KEY = 'kuulis.device_id';
/** The API takes X-Device-Id up to 100 characters. */
const MAX_LENGTH = 100;

let cached: string | null = null;
let loading: Promise<string | null> | null = null;

/** Random v4-style id for devices that give us none (web, a failing native call). */
export function randomId(): string {
  const bytes = new Uint8Array(16);
  const crypto = (globalThis as { crypto?: { getRandomValues?: (array: Uint8Array) => Uint8Array } }).crypto;
  if (crypto?.getRandomValues) crypto.getRandomValues(bytes);
  else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

async function nativeId(): Promise<string | null> {
  try {
    if (Platform.OS === 'android') {
      const id = Application.getAndroidId();
      return id ? `android:${id}` : null;
    }
    if (Platform.OS === 'ios') {
      const id = await Application.getIosIdForVendorAsync();
      return id ? `ios:${id}` : null;
    }
  } catch {
    // Older binaries or simulators: fall back to a stored random id.
  }
  return null;
}

async function storedId(): Promise<string | null> {
  try {
    const stored = await secureStorage.get(FALLBACK_KEY);
    if (stored) return stored;
    const created = `app:${randomId()}`;
    await secureStorage.set(FALLBACK_KEY, created);
    return created;
  } catch {
    return null;
  }
}

/**
 * A stable id of this phone (doc 12): the API keeps it per session to spot one phone behind several driver
 * accounts. Android ID or the iOS vendor id, else a random id kept in secure storage. Never throws; null
 * only when nothing works (the header is then left out).
 */
export function getDeviceId(): Promise<string | null> {
  if (cached) return Promise.resolve(cached);
  loading ??= (async () => {
    const id = ((await nativeId()) ?? (await storedId()))?.slice(0, MAX_LENGTH) ?? null;
    cached = id;
    return id;
  })()
    .catch(() => null)
    .finally(() => {
      loading = null;
    });
  return loading;
}

/** {'X-Device-Id': id}, or nothing when it is unknown. */
export async function deviceHeaders(): Promise<Record<string, string>> {
  const id = await getDeviceId().catch(() => null);
  return id ? { 'X-Device-Id': id } : {};
}

/** The API takes X-Device-Model up to 80 characters. */
const MODEL_MAX_LENGTH = 80;

/** {'X-Device-Model': model} for a known model name (trimmed, up to 80 chars), else nothing (doc 16). */
export function modelHeader(modelName: string | null | undefined): Record<string, string> {
  const model = typeof modelName === 'string' ? modelName.trim().slice(0, MODEL_MAX_LENGTH).trim() : '';
  return model ? { 'X-Device-Model': model } : {};
}

/** This phone's model (e.g. "Pixel 7") as a header; empty on web, in tests or when the module fails. */
export function deviceModelHeaders(): Record<string, string> {
  try {
    return modelHeader(Device.modelName);
  } catch {
    return {};
  }
}
