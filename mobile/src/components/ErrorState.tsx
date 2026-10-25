import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { type StyleProp, View, type ViewStyle } from 'react-native';

import { CircleX, type Icon, SearchX, ServerCrash, WifiOff } from '@/components/icons';
import { Button, EmptyState, Notice, Txt } from '@/components/ui';
import { useIsOffline } from '@/hooks/useOnline';
import { apiErrorMessage } from '@/i18n';
import { type ErrorKind, errorKind, hasSpecificCode } from '@/lib/errorKind';
import { space } from '@/theme';

const ICONS: Record<ErrorKind, Icon> = {
  offline: WifiOff,
  unreachable: WifiOff,
  server: ServerCrash,
  notFound: SearchX,
  generic: CircleX,
};

/** Title and text for a failed load: stock texts per kind, the API's own text when it sent a known code. */
export function useErrorCopy(error: unknown, title?: string) {
  const { t } = useTranslation();
  const kind = errorKind(error, useIsOffline());
  const specific = hasSpecificCode(error) && kind !== 'offline' && kind !== 'server';
  return {
    kind,
    icon: ICONS[kind],
    title: title ?? t(`states.${kind}.title`),
    body: specific ? apiErrorMessage(error) : t(`states.${kind}.body`),
  };
}

/**
 * What a screen or list shows when its data could not load: says whether it is the phone's connection, Kuulis'
 * servers or something that no longer exists, and offers to try again. Queries already refetch by themselves
 * when the connection comes back (`onlineManager` in the root layout). `inline` is the compact version for a
 * section inside a screen that still shows other things.
 */
export function ErrorState({
  error,
  onRetry,
  title,
  inline,
  style,
}: {
  error: unknown;
  onRetry?: () => unknown;
  /** Replaces the stock title, e.g. "No encontramos este viaje". */
  title?: string;
  inline?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { t } = useTranslation();
  const copy = useErrorCopy(error, title);
  const [retrying, setRetrying] = useState(false);

  const retry = async () => {
    if (!onRetry || retrying) return;
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  };

  if (inline) {
    return (
      <Notice tone={copy.kind === 'offline' ? 'warning' : 'danger'} icon={copy.icon} title={copy.title} style={style}>
        <View style={{ gap: space.xs }}>
          <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
            {copy.body}
          </Txt>
          {onRetry ? (
            <Button
              title={t('common.retry')}
              variant="ghost"
              size="sm"
              loading={retrying}
              style={{ alignSelf: 'flex-start' }}
              onPress={() => void retry()}
            />
          ) : null}
        </View>
      </Notice>
    );
  }

  return (
    <View accessibilityLiveRegion="polite" style={style}>
      <EmptyState icon={copy.icon} title={copy.title} body={copy.body} />
      {onRetry ? <Button title={t('common.retry')} variant="secondary" loading={retrying} onPress={() => void retry()} /> : null}
    </View>
  );
}
