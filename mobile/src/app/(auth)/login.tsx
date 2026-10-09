import { Link } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, View } from 'react-native';

import { AuthScaffold } from '@/components/AuthScaffold';
import { Lock, Mail } from '@/components/icons';
import { SocialButtons } from '@/components/SocialButtons';
import { Button, ErrorText, Field, Txt } from '@/components/ui';
import { apiErrorMessage } from '@/i18n';
import { isEmail } from '@/lib/validation';
import { useAuth } from '@/providers/AuthProvider';

export default function LoginScreen() {
  const { t } = useTranslation();
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [socialBusy, setSocialBusy] = useState(false);

  async function submit() {
    const fieldErrors = {
      email: isEmail(email) ? undefined : t('validation.email'),
      password: password ? undefined : t('validation.required'),
    };
    setErrors(fieldErrors);
    if (fieldErrors.email || fieldErrors.password) return;
    setLoading(true);
    setError(undefined);
    try {
      await signIn(email.trim(), password);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthScaffold
      title={t('auth.welcome')}
      subtitle={t('auth.welcomeSubtitle')}
      footer={
        <Link href="/register" asChild>
          <Pressable accessibilityRole="link" hitSlop={8}>
            <Txt color="muted">
              {t('auth.noAccountPrefix')}{' '}
              <Txt variant="bodyStrong" color="primary">
                {t('auth.noAccountAction')}
              </Txt>
            </Txt>
          </Pressable>
        </Link>
      }>
      <SocialButtons onBusyChange={setSocialBusy} />
      <Field
        label={t('auth.email')}
        icon={Mail}
        value={email}
        onChangeText={setEmail}
        error={errors.email}
        autoCapitalize="none"
        keyboardType="email-address"
        autoComplete="email"
        textContentType="emailAddress"
        returnKeyType="next"
        placeholder={t('auth.emailPlaceholder')}
      />
      <Field
        label={t('auth.password')}
        icon={Lock}
        value={password}
        onChangeText={setPassword}
        error={errors.password}
        secureToggle
        autoComplete="password"
        textContentType="password"
        returnKeyType="go"
        onSubmitEditing={submit}
      />
      <View style={{ alignItems: 'flex-end', marginTop: -4, marginBottom: 8 }}>
        <Link href="/forgot-password" asChild>
          <Pressable accessibilityRole="link" hitSlop={10}>
            <Txt variant="label" color="primary">
              {t('auth.forgot')}
            </Txt>
          </Pressable>
        </Link>
      </View>
      <ErrorText>{error}</ErrorText>
      <Button title={t('auth.login')} onPress={submit} loading={loading} disabled={socialBusy} />
    </AuthScaffold>
  );
}
