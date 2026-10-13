import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Alert, View } from 'react-native';

import { ChevronLeft, HeartHandshake, Phone, Plus, Trash, User as UserIcon } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Card, Field, IconButton, IconTile, ListRow, Notice, Row, Screen, Txt } from '@/components/ui';
import { useDeleteContact, useSaveContact, useTrustedContacts } from '@/hooks/useSafety';
import { apiErrorMessage } from '@/i18n';
import { formatPhoneLocal, normalizePhone } from '@/lib/driver';
import { type AutoShareMode, autoShareFields, autoShareMode, MAX_TRUSTED_CONTACTS } from '@/lib/safety';
import type { TrustedContact } from '@/lib/types';
import { space, useTheme } from '@/theme';

import { Segmented } from './components';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

/** Up to five trusted contacts (doc 11): they get the live ride link, also automatically (by hours) and on SOS. */
export function TrustedContactScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const contacts = useTrustedContacts();
  const [editing, setEditing] = useState<TrustedContact | 'new' | null>(null);

  if (editing) {
    return <ContactForm contact={editing === 'new' ? null : editing} onDone={() => setEditing(null)} />;
  }

  const list = contacts.data ?? [];
  const full = list.length >= MAX_TRUSTED_CONTACTS;
  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }
      footer={
        full ? null : <Button title={t('profile.contact.add')} icon={Plus} disabled={!contacts.data} onPress={() => setEditing('new')} />
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={HeartHandshake} tone="accent" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('profile.contact.title')}
        </Txt>
        <Txt color="muted">{t('profile.contact.subtitle')}</Txt>
      </View>
      {contacts.isPending ? (
        <ActivityIndicator color={theme.primary} />
      ) : contacts.isError ? (
        <Notice tone="danger">{apiErrorMessage(contacts.error)}</Notice>
      ) : list.length ? (
        <Card style={{ paddingVertical: space.xxs, marginBottom: space.md }}>
          {list.map((contact, index) => (
            <ListRow
              key={contact.id}
              icon={UserIcon}
              iconTone="accent"
              title={contact.name}
              subtitle={`${formatPhoneLocal(contact.phone)} · ${t(`profile.contact.auto.${autoShareMode(contact)}Short`)}`}
              divider={index < list.length - 1}
              onPress={() => setEditing(contact)}
            />
          ))}
        </Card>
      ) : null}
      {full ? <Notice tone="info">{t('profile.contact.full', { count: MAX_TRUSTED_CONTACTS })}</Notice> : null}
      <Notice tone="info">{t('profile.contact.how')}</Notice>
    </Screen>
  );
}

function ContactForm({ contact, onDone }: { contact: TrustedContact | null; onDone: () => void }) {
  const { t } = useTranslation();
  const save = useSaveContact();
  const remove = useDeleteContact();
  const [name, setName] = useState(contact?.name ?? '');
  const [phone, setPhone] = useState(formatPhoneLocal(contact?.phone));
  const [mode, setMode] = useState<AutoShareMode>(autoShareMode(contact));
  const [touched, setTouched] = useState(false);

  const e164 = normalizePhone(phone);
  const nameError = touched && name.trim().length < 2 ? t('validation.required') : undefined;
  const phoneError = touched && !e164 ? t('profile.contact.phoneInvalid') : undefined;

  const submit = () => {
    setTouched(true);
    if (name.trim().length < 2 || !e164) return;
    save.mutate(
      { id: contact?.id, name: name.trim(), phone: e164, ...autoShareFields(mode, contact) },
      {
        onSuccess: () => {
          showToast(t('profile.contact.saved'), 'success');
          onDone();
        },
        onError: (error) => showToast(apiErrorMessage(error), 'danger'),
      },
    );
  };

  const confirmRemove = () => {
    if (!contact) return;
    Alert.alert(t('profile.contact.removeTitle', { name: contact.name }), undefined, [
      { text: t('common.back'), style: 'cancel' },
      {
        text: t('profile.contact.remove'),
        style: 'destructive',
        onPress: () =>
          remove.mutate(contact.id, {
            onSuccess: () => {
              showToast(t('profile.contact.removed'));
              onDone();
            },
            onError: (error) => showToast(apiErrorMessage(error), 'danger'),
          }),
      },
    ]);
  };

  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={onDone} />
        </Row>
      }
      footer={
        <>
          <Button title={t('common.save')} loading={save.isPending} onPress={submit} />
          {contact ? (
            <Button title={t('profile.contact.remove')} variant="ghost" icon={Trash} disabled={save.isPending} loading={remove.isPending} onPress={confirmRemove} />
          ) : null}
        </>
      }>
      <Txt variant="title" accessibilityRole="header" style={{ marginBottom: space.lg }}>
        {contact ? t('profile.contact.edit') : t('profile.contact.add')}
      </Txt>
      <Field
        label={t('profile.contact.name')}
        icon={UserIcon}
        value={name}
        onChangeText={setName}
        maxLength={80}
        autoCapitalize="words"
        placeholder={t('profile.contact.namePlaceholder')}
        error={nameError}
      />
      <Field
        label={t('profile.contact.phone')}
        icon={Phone}
        value={phone}
        onChangeText={setPhone}
        keyboardType="phone-pad"
        autoComplete="tel"
        textContentType="telephoneNumber"
        placeholder="0414 123 4567"
        returnKeyType="done"
        onSubmitEditing={submit}
        error={phoneError}
        hint={t('profile.contact.phoneHint')}
      />
      <View style={{ gap: space.xs, marginBottom: space.md }}>
        <Txt variant="label" color="muted">
          {t('profile.contact.auto.title')}
        </Txt>
        <Segmented<AutoShareMode>
          label={t('profile.contact.auto.title')}
          value={mode}
          onChange={setMode}
          options={[
            { value: 'off', label: t('profile.contact.auto.off') },
            { value: 'always', label: t('profile.contact.auto.always') },
            { value: 'night', label: t('profile.contact.auto.night') },
          ]}
        />
        <Txt variant="caption" color="muted">
          {t(`profile.contact.auto.${mode}Hint`)}
        </Txt>
      </View>
    </Screen>
  );
}
