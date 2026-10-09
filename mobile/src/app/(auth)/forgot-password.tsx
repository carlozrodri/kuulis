import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { AuthScaffold } from '@/components/AuthScaffold';
import { ChevronLeft, Mail } from '@/components/icons';
import { Button, ErrorText, Field, IconButton, Notice } from '@/components/ui';
import { apiErrorMessage } from '@/i18n';
import { api } from '@/lib/api';
import { isEmail } from '@/lib/validation';

export default function ForgotPasswordScreen() {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [fieldError, setFieldError] = useState<string>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!isEmail(email)) return setFieldError(t('validation.email'));
    setFieldError(undefined);
    setLoading(true);
    setError(undefined);
    try {
      await api('/auth/password-reset', { method: 'POST', body: { email: email.trim() }, auth: false });
      setSent(true);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  const back = () => (router.canGoBack() ? router.back() : router.replace('/login'));

  return (
    <AuthScaffold
      title={t('auth.resetTitle')}
      subtitle={t('auth.resetSubtitle')}
      leading={<IconButton icon={ChevronLeft} label={t('common.back')} tone="onHero" onPress={back} />}>
      {sent ? (
        <Notice tone="success" title={t('auth.resetSentTitle')}>
          {t('auth.resetSent')}
        </Notice>
      ) : (
        <>
          <Field
            label={t('auth.email')}
            icon={Mail}
            value={email}
            onChangeText={setEmail}
            error={fieldError}
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
            placeholder={t('auth.emailPlaceholder')}
            returnKeyType="send"
            onSubmitEditing={submit}
          />
          <ErrorText>{error}</ErrorText>
          <Button title={t('auth.resetSend')} onPress={submit} loading={loading} />
        </>
      )}
      <Button title={t('auth.backToLogin')} variant="ghost" onPress={back} />
    </AuthScaffold>
  );
}
