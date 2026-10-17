import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, StyleSheet, View } from 'react-native';

import { ChevronRight, StickyNote, UserRound, X } from '@/components/icons';
import { Button, Chip, Field, Txt } from '@/components/ui';
import { useTrustedContacts } from '@/hooks/useSafety';
import { formatPhoneLocal, normalizePhone } from '@/lib/driver';
import { selectionHaptic } from '@/lib/feedback';
import { useStore } from '@/lib/store';
import { radius, space, useTheme } from '@/theme';

import { rideDraft, setDraftNote, setDraftRider } from './store';

export const NOTE_MAX = 140;

/**
 * Doc 23, on the quote screen: "¿Para quién es?" (the passenger, or someone else with name and phone; trusted
 * contacts are one tap) and "Nota para el motorizado" (up to 140 characters, shown to the driver before accepting).
 */
export function RideExtras() {
  const { t } = useTranslation();
  const draft = useStore(rideDraft);
  const [open, setOpen] = useState<'rider' | 'note' | null>(null);
  return (
    <View style={{ gap: space.xs }}>
      {open === 'rider' ? (
        <RiderForm onDone={() => setOpen(null)} />
      ) : (
        <ExtraRow
          icon={UserRound}
          title={draft.rider ? t('quote.rider.for', { name: draft.rider.name }) : t('quote.rider.me')}
          subtitle={draft.rider ? formatPhoneLocal(draft.rider.phone) : t('quote.rider.someoneElse')}
          onPress={() => setOpen('rider')}
          onClear={draft.rider ? () => setDraftRider(null) : undefined}
          clearLabel={t('quote.rider.clear')}
        />
      )}
      {open === 'note' ? (
        <NoteForm onDone={() => setOpen(null)} />
      ) : (
        <ExtraRow
          icon={StickyNote}
          title={draft.note.trim() ? draft.note.trim() : t('quote.note.add')}
          subtitle={draft.note.trim() ? t('quote.note.title') : t('quote.note.hint')}
          onPress={() => setOpen('note')}
          onClear={draft.note.trim() ? () => setDraftNote('') : undefined}
          clearLabel={t('quote.note.clear')}
        />
      )}
    </View>
  );
}

function ExtraRow({
  icon: Glyph,
  title,
  subtitle,
  onPress,
  onClear,
  clearLabel,
}: {
  icon: typeof UserRound;
  title: string;
  subtitle: string;
  onPress: () => void;
  onClear?: () => void;
  clearLabel: string;
}) {
  const theme = useTheme();
  return (
    <View style={[styles.row, { borderColor: theme.border, backgroundColor: theme.surface }]}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${title}. ${subtitle}`}
        onPress={onPress}
        style={({ pressed }) => [styles.rowMain, { opacity: pressed ? 0.7 : 1 }]}>
        <Glyph size={20} color={theme.primary} strokeWidth={2.2} />
        <View style={{ flex: 1 }}>
          <Txt variant="bodyStrong" numberOfLines={1}>
            {title}
          </Txt>
          <Txt variant="caption" color="muted" numberOfLines={1}>
            {subtitle}
          </Txt>
        </View>
        {onClear ? null : <ChevronRight size={18} color={theme.muted} />}
      </Pressable>
      {onClear ? (
        <Pressable accessibilityRole="button" accessibilityLabel={clearLabel} hitSlop={10} onPress={onClear} style={styles.clear}>
          <X size={18} color={theme.muted} strokeWidth={2.4} />
        </Pressable>
      ) : null}
    </View>
  );
}

function RiderForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const current = useStore(rideDraft).rider;
  const contacts = useTrustedContacts().data ?? [];
  const [name, setName] = useState(current?.name ?? '');
  const [phone, setPhone] = useState(current ? formatPhoneLocal(current.phone) : '');
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    const e164 = normalizePhone(phone);
    if (!name.trim()) return setError(t('quote.rider.nameRequired'));
    if (!e164) return setError(t('quote.rider.phoneInvalid'));
    selectionHaptic();
    setDraftRider({ name: name.trim().slice(0, 60), phone: e164 });
    onDone();
  };

  return (
    <View style={{ gap: space.sm }}>
      <Txt variant="overline" color="muted">
        {t('quote.rider.title')}
      </Txt>
      {contacts.length ? (
        <View style={styles.chips}>
          {contacts.map((contact) => (
            <Chip
              key={contact.id}
              label={contact.name}
              icon={UserRound}
              selected={normalizePhone(phone) === contact.phone}
              onPress={() => {
                setName(contact.name);
                setPhone(formatPhoneLocal(contact.phone));
                setError(null);
              }}
            />
          ))}
        </View>
      ) : null}
      <Field label={t('quote.rider.name')} value={name} onChangeText={setName} maxLength={60} autoCapitalize="words" />
      <Field
        label={t('quote.rider.phone')}
        value={phone}
        onChangeText={(value) => {
          setPhone(value);
          setError(null);
        }}
        keyboardType="phone-pad"
        placeholder="0414 123 4567"
        hint={t('quote.rider.phoneHint')}
        error={error ?? undefined}
      />
      <View style={styles.actions}>
        <Button title={t('common.cancel')} variant="secondary" size="sm" style={{ flex: 1 }} onPress={onDone} />
        <Button title={t('quote.rider.save')} size="sm" style={{ flex: 1 }} onPress={save} />
      </View>
    </View>
  );
}

function NoteForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const [note, setNote] = useState(useStore(rideDraft).note);
  return (
    <View style={{ gap: space.sm }}>
      <Field
        label={t('quote.note.title')}
        value={note}
        onChangeText={setNote}
        maxLength={NOTE_MAX}
        placeholder={t('quote.note.placeholder')}
        hint={t('quote.note.count', { count: note.length, max: NOTE_MAX })}
        multiline
        autoFocus
      />
      <View style={styles.actions}>
        <Button title={t('common.cancel')} variant="secondary" size="sm" style={{ flex: 1 }} onPress={onDone} />
        <Button
          title={t('quote.note.save')}
          size="sm"
          style={{ flex: 1 }}
          onPress={() => {
            setDraftNote(note.trim());
            onDone();
          }}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: radius.tile, minHeight: 56 },
  rowMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingHorizontal: 14, paddingVertical: 10 },
  clear: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.xs },
  actions: { flexDirection: 'row', gap: space.xs },
});
