import * as FileSystem from 'expo-file-system/legacy';
import { Platform } from 'react-native';

/**
 * Small text files in the app's document folder (localStorage on web), for data that may exceed the
 * secure store's 2 KB per value: the last bootstrap and the closed banners. Best-effort: never throws.
 */
const path = (name: string) => (FileSystem.documentDirectory ? `${FileSystem.documentDirectory}${name}` : null);

export const localFile = {
  async read(name: string): Promise<string | null> {
    try {
      if (Platform.OS === 'web') return globalThis.localStorage?.getItem(`kuulis.file.${name}`) ?? null;
      const file = path(name);
      if (!file) return null;
      const info = await FileSystem.getInfoAsync(file);
      return info.exists ? await FileSystem.readAsStringAsync(file) : null;
    } catch {
      return null;
    }
  },
  async write(name: string, contents: string): Promise<void> {
    try {
      if (Platform.OS === 'web') {
        globalThis.localStorage?.setItem(`kuulis.file.${name}`, contents);
        return;
      }
      const file = path(name);
      if (file) await FileSystem.writeAsStringAsync(file, contents);
    } catch {
      // the in-memory copy still works for this session
    }
  },
};
