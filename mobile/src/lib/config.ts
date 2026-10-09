import Constants from 'expo-constants';

type Extra = { appEnv: 'local' | 'qa' | 'production'; apiUrl: string; eas?: { projectId?: string } };

const extra = (Constants.expoConfig?.extra ?? {}) as Partial<Extra>;

export const config = {
  appEnv: extra.appEnv ?? 'local',
  apiUrl: extra.apiUrl ?? 'http://localhost:8000/api/v1',
  easProjectId: extra.eas?.projectId,
  /** ws(s)://host/api/v1/ws derived from the REST base URL. */
  get wsUrl() {
    return `${this.apiUrl.replace(/^http/, 'ws')}/ws`;
  },
};
