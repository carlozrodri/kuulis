import Constants from 'expo-constants';

type Extra = {
  appEnv: 'local' | 'qa' | 'production';
  apiUrl: string;
  googleWebClientId?: string;
  googleIosClientId?: string;
  eas?: { projectId?: string };
};

const extra = (Constants.expoConfig?.extra ?? {}) as Partial<Extra>;

export const config = {
  appEnv: extra.appEnv ?? 'local',
  apiUrl: extra.apiUrl ?? 'http://localhost:8000/api/v1',
  easProjectId: extra.eas?.projectId,
  googleWebClientId: extra.googleWebClientId || process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID || undefined,
  googleIosClientId: extra.googleIosClientId || process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || undefined,
  /** ws(s)://host/api/v1/ws derived from the REST base URL. */
  get wsUrl() {
    return `${this.apiUrl.replace(/^http/, 'ws')}/ws`;
  },
};
