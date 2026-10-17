import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import { MapPin, MapPinned } from '@/components/icons';
import { Button, Notice, Txt } from '@/components/ui';
import type { Localized } from '@/lib/bootstrap';
import { formatDistance } from '@/lib/ride';
import { restrictedMessage, type ZoneCheck, type ZoneSuggestion } from '@/lib/zones';
import { radius, space, useTheme } from '@/theme';

/**
 * Doc 21: under the chosen pickup. In a restricted zone a clear warning (the zone's own message, in the app
 * language) and, when there is one, "Usar {punto}" to move the pickup to the nearest allowed point. Otherwise a
 * light hint with the suggested pickup point of the area.
 */
export function PickupZoneNotice({
  check,
  restricted: restrictedByError = false,
  suggestion: errorSuggestion = null,
  message = null,
  onUse,
}: {
  check: ZoneCheck | null | undefined;
  /** The quote answered 422 pickup_restricted (the check may not have answered). */
  restricted?: boolean;
  suggestion?: ZoneSuggestion | null;
  /** The zone's message from the error details (used when the check did not answer). */
  message?: Partial<Localized> | null;
  onUse: (suggestion: ZoneSuggestion) => void;
}) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const restricted = restrictedByError || !!check?.restricted;
  const suggestion = check?.suggestion ?? errorSuggestion;
  const distance = suggestion ? formatDistance(suggestion.distance_m, i18n.language) : '';

  const use = suggestion ? (
    <Button
      title={t('zones.use', { name: suggestion.name })}
      variant="secondary"
      size="sm"
      icon={MapPin}
      accessibilityHint={t('zones.useHint', { distance })}
      style={styles.use}
      onPress={() => onUse(suggestion)}
    />
  ) : null;

  if (restricted) {
    return (
      <Notice tone="warning" title={t('zones.restrictedTitle')}>
        <Txt variant="caption" style={{ color: theme.text, fontSize: 14, lineHeight: 20 }}>
          {restrictedMessage(check, i18n.language, message) || t('errors.pickup_restricted')}
        </Txt>
        {suggestion ? (
          <Txt variant="caption" style={{ color: theme.text, fontSize: 14, lineHeight: 20 }}>
            {t('zones.nearest', { name: suggestion.name, distance })}
          </Txt>
        ) : null}
        {use}
      </Notice>
    );
  }

  if (!suggestion) return null;
  return (
    <View style={[styles.hint, { backgroundColor: theme.surfaceAlt }]}>
      <View style={styles.hintRow}>
        <MapPinned size={20} color={theme.scheme === 'dark' ? theme.primary : theme.primaryPressed} strokeWidth={2.2} />
        <Txt variant="caption" style={{ color: theme.text, flex: 1, fontSize: 14, lineHeight: 20 }}>
          {t('zones.suggested', { name: suggestion.name, distance })}
        </Txt>
      </View>
      {use}
    </View>
  );
}

const styles = StyleSheet.create({
  hint: { gap: space.xs, borderRadius: radius.tile, padding: space.sm },
  hintRow: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  use: { alignSelf: 'flex-start', marginTop: space.xxs },
});
