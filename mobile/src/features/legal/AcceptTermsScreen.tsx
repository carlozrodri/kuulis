import { useQuery } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { FileText, LogOut, ScrollText } from '@/components/icons';
import { Button, Card, ErrorText, IconTile, ListRow, Screen, Txt } from '@/components/ui';
import { apiErrorMessage } from '@/i18n';
import { api } from '@/lib/api';
import { isLegalKind, type LegalKind, type LegalSummary } from '@/lib/legal';
import { useAuth } from '@/providers/AuthProvider';
import { space } from '@/theme';

import { CheckRow } from './CheckRow';

/**
 * Blocking screen while user.pending_legal is not empty: after signing up with Google or Apple, or when
 * Kuulis publishes a version that must be accepted again. Shows what changed and links to each text.
 */
export function AcceptTermsScreen() {
  const { t, i18n } = useTranslation();
  const { user, refreshUser, signOut } = useAuth();
  const locale = i18n.language.startsWith('en') ? 'en' : 'es';
  const pending = (user?.pending_legal ?? []).filter(isLegalKind);
  const { data: documents } = useQuery({
    queryKey: ['legal', 'all', locale],
    queryFn: () => api<LegalSummary[]>(`/legal?locale=${locale}`, { auth: false }),
  });
  const byKind = new Map((documents ?? []).map((d) => [d.kind, d]));
  const updated = pending.some((kind) => (byKind.get(kind)?.version ?? 1) > 1);
  const askAge = pending.includes('terms');

  const [accepted, setAccepted] = useState(false);
  const [adult, setAdult] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  async function accept() {
    setSaving(true);
    setError(undefined);
    try {
      await api<string[]>('/legal/accept', { method: 'POST', body: { kinds: pending } });
      await refreshUser();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const open = (kind: LegalKind) => router.push({ pathname: '/legal/[kind]', params: { kind } });

  return (
    <Screen
      footer={
        <View style={{ gap: space.xs }}>
          <ErrorText>{error}</ErrorText>
          <Button
            title={t('legal.accept')}
            onPress={accept}
            loading={saving}
            disabled={!accepted || (askAge && !adult) || pending.length === 0}
          />
          <Button title={t('auth.logout')} variant="ghost" icon={LogOut} onPress={() => void signOut()} />
        </View>
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginTop: space.xl, marginBottom: space.lg }}>
        <IconTile icon={ScrollText} tone="primary" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {updated ? t('legal.updatedTitle') : t('legal.acceptTitle')}
        </Txt>
        <Txt color="muted">{updated ? t('legal.updatedBody') : t('legal.acceptBody')}</Txt>
      </View>

      <Card style={{ paddingVertical: space.xxs }}>
        {pending.map((kind, index) => {
          const doc = byKind.get(kind);
          const changes = doc && doc.version > 1 && doc.summary ? doc.summary : null;
          return (
            <ListRow
              key={kind}
              icon={FileText}
              iconTone="neutral"
              title={doc?.title ?? t(`legal.kinds.${kind}`)}
              subtitle={changes ?? t('legal.read')}
              divider={index < pending.length - 1}
              onPress={() => open(kind)}
            />
          );
        })}
      </Card>

      <View style={{ marginTop: space.lg, gap: space.xs }}>
        <CheckRow checked={accepted} onChange={setAccepted}>
          {t('legal.acceptCheck')}
        </CheckRow>
        {askAge ? (
          <CheckRow checked={adult} onChange={setAdult}>
            {t('legal.adultCheck')}
          </CheckRow>
        ) : null}
      </View>
    </Screen>
  );
}
