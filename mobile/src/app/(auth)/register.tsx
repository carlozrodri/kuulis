import { Link, router } from 'expo-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable } from 'react-native';

import { AuthScaffold } from '@/components/AuthScaffold';
import { ChevronLeft, Lock, Mail, User } from '@/components/icons';
import { SocialButtons } from '@/components/SocialButtons';
import { Button, ErrorText, Field, IconButton, Txt } from '@/components/ui';
import { CheckRow } from '@/features/legal/CheckRow';
import { apiErrorMessage, apiFieldErrors } from '@/i18n';
import { track } from '@/lib/analytics';
import type { LegalKind } from '@/lib/legal';
import { isEmail, isPassword } from '@/lib/validation';
import { useAuth } from '@/providers/AuthProvider';

type Errors = { full_name?: string; email?: string; password?: string; legal?: string };

const openLegal = (kind: LegalKind) => router.push({ pathname: '/legal/[kind]', params: { kind } });

export default function RegisterScreen() {
  const { t } = useTranslation();
  const { signUp } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [socialBusy, setSocialBusy] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [adult, setAdult] = useState(false);
  useEffect(() => track('signup_started', { method: 'email' }), []);

  async function submit() {
    const fieldErrors: Errors = {
      full_name: fullName.trim() ? undefined : t('validation.required'),
      email: isEmail(email) ? undefined : t('validation.email'),
      password: isPassword(password) ? undefined : t('validation.password'),
      legal: accepted && adult ? undefined : t('legal.required'),
    };
    setErrors(fieldErrors);
    if (Object.values(fieldErrors).some(Boolean)) return;
    setLoading(true);
    setError(undefined);
    try {
      await signUp(email.trim(), password, fullName.trim(), true);
    } catch (e) {
      setErrors(apiFieldErrors(e));
      setError(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthScaffold
      title={t('auth.registerTitle')}
      subtitle={t('auth.registerSubtitle')}
      leading={
        router.canGoBack() ? (
          <IconButton icon={ChevronLeft} label={t('common.back')} tone="onHero" onPress={() => router.back()} />
        ) : null
      }
      footer={
        <Link href="/login" asChild>
          <Pressable accessibilityRole="link" hitSlop={8}>
            <Txt color="muted">
              {t('auth.haveAccountPrefix')}{' '}
              <Txt variant="bodyStrong" color="primary">
                {t('auth.haveAccountAction')}
              </Txt>
            </Txt>
          </Pressable>
        </Link>
      }>
      <SocialButtons onBusyChange={setSocialBusy} />
      <Field
        label={t('auth.fullName')}
        icon={User}
        value={fullName}
        onChangeText={setFullName}
        error={errors.full_name}
        autoComplete="name"
        textContentType="name"
        autoCapitalize="words"
      />
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
        placeholder={t('auth.emailPlaceholder')}
      />
      <Field
        label={t('auth.password')}
        icon={Lock}
        value={password}
        onChangeText={setPassword}
        error={errors.password}
        hint={t('validation.password')}
        secureToggle
        autoComplete="new-password"
        textContentType="newPassword"
        returnKeyType="go"
        onSubmitEditing={submit}
      />
      <CheckRow checked={accepted} onChange={setAccepted}>
        {t('legal.signUpPrefix')}
        <Txt variant="caption" color="primary" onPress={() => openLegal('terms')}>
          {t('legal.kinds.terms')}
        </Txt>
        {t('legal.signUpAnd')}
        <Txt variant="caption" color="primary" onPress={() => openLegal('privacy')}>
          {t('legal.kinds.privacy')}
        </Txt>
      </CheckRow>
      <CheckRow checked={adult} onChange={setAdult}>
        {t('legal.adultCheck')}
      </CheckRow>
      <ErrorText>{errors.legal ?? error}</ErrorText>
      <Button title={t('auth.register')} onPress={submit} loading={loading} disabled={socialBusy} />
      <Txt variant="caption" color="muted" align="center" style={{ marginTop: 12 }}>
        {t('legal.socialNote')}
      </Txt>
    </AuthScaffold>
  );
}
