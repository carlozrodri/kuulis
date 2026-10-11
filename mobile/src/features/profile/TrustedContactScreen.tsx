import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { ChevronLeft, HeartHandshake, Phone, Trash, User as UserIcon } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Field, IconButton, IconTile, Notice, Row, Screen, Txt } from '@/components/ui';
import { apiErrorMessage } from '@/i18n';
import { api } from '@/lib/api';
import { formatPhoneLocal, normalizePhone } from '@/lib/driver';
import { useAuth } from '@/providers/AuthProvider';
import { space } from '@/theme';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

/** Someone the user trusts: during a ride the share button sends them the trip over WhatsApp. */
export function TrustedContactScreen() {
  const { t } = useTranslation();
  const { user, refreshUser } = useAuth();
  const [name, setName] = useState(user?.trusted_contact_name ?? '');
  const [phone, setPhone] = useState(formatPhoneLocal(user?.trusted_contact_phone));
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);

  const e164 = normalizePhone(phone);
  const nameError = touched && name.trim().length < 2 ? t('validation.required') : undefined;
  const phoneError = touched && !e164 ? t('profile.contact.phoneInvalid') : undefined;
  const hasContact = !!user?.trusted_contact_phone;

  async function persist(body: { trusted_contact_name: string | null; trusted_contact_phone: string | null }, message: string) {
    setSaving(true);
    try {
      await api('/users/me', { method: 'PATCH', body });
      await refreshUser();
      showToast(message, 'success');
      back();
    } catch (error) {
      showToast(apiErrorMessage(error), 'danger');
    } finally {
      setSaving(false);
    }
  }

  function save() {
    setTouched(true);
    if (name.trim().length < 2 || !e164) return;
    void persist({ trusted_contact_name: name.trim(), trusted_contact_phone: e164 }, t('profile.contact.saved'));
  }

  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }
      footer={
        <>
          <Button title={t('common.save')} loading={saving} onPress={save} />
          {hasContact ? (
            <Button
              title={t('profile.contact.remove')}
              variant="ghost"
              icon={Trash}
              disabled={saving}
              onPress={() => void persist({ trusted_contact_name: null, trusted_contact_phone: null }, t('profile.contact.removed'))}
            />
          ) : null}
        </>
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={HeartHandshake} tone="accent" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('profile.contact.title')}
        </Txt>
        <Txt color="muted">{t('profile.contact.subtitle')}</Txt>
      </View>
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
        onSubmitEditing={save}
        error={phoneError}
        hint={t('profile.contact.phoneHint')}
      />
      <Notice tone="info">{t('profile.contact.how')}</Notice>
    </Screen>
  );
}
