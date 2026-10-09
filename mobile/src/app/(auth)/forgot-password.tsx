import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Body, Button, ErrorText, Field, Screen, Title } from '@/components/ui';
import { api } from '@/lib/api';
import { isEmail } from '@/lib/validation';

export default function ForgotPasswordScreen() {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!isEmail(email)) return setError(t('validation.email'));
    setLoading(true);
    setError(undefined);
    try {
      await api('/auth/password-reset', { method: 'POST', body: { email: email.trim() }, auth: false });
      setSent(true);
    } catch {
      setError(t('errors.network'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen>
      <Title>{t('auth.resetTitle')}</Title>
      {sent ? (
        <Body>{t('auth.resetSent')}</Body>
      ) : (
        <>
          <Field label={t('auth.email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" />
          <ErrorText>{error}</ErrorText>
          <Button title={t('auth.resetSend')} onPress={submit} loading={loading} />
        </>
      )}
      <Button title={t('auth.login')} variant="ghost" onPress={() => router.back()} />
    </Screen>
  );
}
