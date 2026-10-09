import { Link } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Body, Button, ErrorText, Field, Screen, Title } from '@/components/ui';
import { errorMessage } from '@/i18n';
import { ApiError } from '@/lib/api';
import { isEmail, isPassword } from '@/lib/validation';
import { useAuth } from '@/providers/AuthProvider';

export default function RegisterScreen() {
  const { t } = useTranslation();
  const { signUp } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!isEmail(email)) return setError(t('validation.email'));
    if (!isPassword(password)) return setError(t('validation.password'));
    setLoading(true);
    setError(undefined);
    try {
      await signUp(email.trim(), password, fullName.trim());
    } catch (e) {
      setError(e instanceof ApiError ? errorMessage(e.code) : t('errors.network'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen>
      <Title>{t('auth.register')}</Title>
      <Field label={t('auth.fullName')} value={fullName} onChangeText={setFullName} autoComplete="name" />
      <Field label={t('auth.email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
      <Field label={t('auth.password')} value={password} onChangeText={setPassword} secureTextEntry autoComplete="new-password" />
      <ErrorText>{error}</ErrorText>
      <Button title={t('auth.register')} onPress={submit} loading={loading} />
      <Link href="/login" style={{ marginTop: 20 }}>
        <Body muted>{t('auth.haveAccount')}</Body>
      </Link>
    </Screen>
  );
}
