import { useQuery } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Linking, View } from 'react-native';

import { ChevronLeft, ExternalLink, FileText } from '@/components/icons';
import { Button, IconButton, IconTile, Notice, Row, Screen, Txt } from '@/components/ui';
import { useAppLinks } from '@/hooks/useBootstrap';
import { apiErrorMessage } from '@/i18n';
import { api } from '@/lib/api';
import { isLegalKind, type LegalDocument } from '@/lib/legal';
import { space } from '@/theme';

import { Markdown } from './Markdown';

const back = () => (router.canGoBack() ? router.back() : router.replace('/'));

/** One legal text in the app's language (open to signed-out users too: the sign-up form links here). */
export function LegalDocumentScreen() {
  const { t, i18n } = useTranslation();
  const { kind } = useLocalSearchParams<{ kind: string }>();
  const locale = i18n.language.startsWith('en') ? 'en' : 'es';
  const { data, isLoading, error } = useQuery({
    queryKey: ['legal', kind, locale],
    queryFn: () => api<LegalDocument>(`/legal/${kind}?locale=${locale}`, { auth: false }),
    enabled: isLegalKind(kind),
  });
  // Web copies of the terms and the privacy policy (remote settings, doc 10), when configured.
  const links = useAppLinks();
  const webUrl = kind === 'terms' ? links.terms_url : kind === 'privacy' ? links.privacy_url : '';
  const safeWebUrl = /^https:\/\//i.test(webUrl) ? webUrl : null;

  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={FileText} tone="neutral" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {data?.title ?? (isLegalKind(kind) ? t(`legal.kinds.${kind}`) : t('legal.title'))}
        </Txt>
        {data ? (
          <Txt color="muted">
            {t('legal.versionDate', {
              version: data.version,
              date: new Date(data.published_at).toLocaleDateString(i18n.language, { day: 'numeric', month: 'long', year: 'numeric' }),
            })}
          </Txt>
        ) : null}
      </View>
      {isLoading ? <ActivityIndicator /> : null}
      {error ? <Notice tone="danger">{apiErrorMessage(error)}</Notice> : null}
      {data ? <Markdown source={data.body_md} /> : null}
      {safeWebUrl && (error || data) ? (
        <Button
          title={t('legal.openWeb')}
          variant="ghost"
          size="sm"
          icon={ExternalLink}
          style={{ marginTop: space.lg, alignSelf: 'flex-start' }}
          onPress={() => void Linking.openURL(safeWebUrl).catch(() => undefined)}
        />
      ) : null}
    </Screen>
  );
}
