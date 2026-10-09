import { Link } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Body, Button, ErrorText, Field, Screen, Title } from '@/components/ui';
import { errorMessage } from '@/i18n';
import { ApiError } from '@/lib/api';
import { isEmail } from '@/lib/validation';
import { useAuth } from '@/providers/AuthProvider';

export default function LoginScreen() {
  const { t } = useTranslation();
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!isEmail(email)) return setError(t('validation.email'));
    if (!password) return setError(t('validation.required'));
    setLoading(true);
    setError(undefined);
    try {
      await signIn(email.trim(), password);
    } catch (e) {
      setError(e instanceof ApiError ? errorMessage(e.code) : t('errors.network'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen>
      <Title>{t('auth.welcome')}</Title>
      <Field label={t('auth.email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
      <Field label={t('auth.password')} value={password} onChangeText={setPassword} secureTextEntry autoComplete="password" />
      <ErrorText>{error}</ErrorText>
      <Button title={t('auth.login')} onPress={submit} loading={loading} />
      <Link href="/register" style={{ marginTop: 20 }}>
        <Body muted>{t('auth.noAccount')}</Body>
      </Link>
      <Link href="/forgot-password" style={{ marginTop: 12 }}>
        <Body muted>{t('auth.forgot')}</Body>
      </Link>
    </Screen>
  );
}
