import { router } from 'expo-router';
import { type PropsWithChildren, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { ChevronLeft, LockKeyhole, Mail, User as UserIcon } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Field, IconButton, Notice, Row, Screen, Txt } from '@/components/ui';
import { apiErrorMessage } from '@/i18n';
import { ApiError, api } from '@/lib/api';
import { useAuth } from '@/providers/AuthProvider';
import { space, useTheme } from '@/theme';

import { ProfileAvatar } from './components';
import { useAvatarPicker } from './useAvatarPicker';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

function Header({ title }: { title: string }) {
  const { t } = useTranslation();
  return (
    <Row style={{ justifyContent: 'space-between', paddingTop: space.xs, paddingBottom: space.md }}>
      <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
      <Txt variant="label" color="muted">
        {title}
      </Txt>
      <View style={{ width: 44 }} />
    </Row>
  );
}

function Intro({ title, children }: PropsWithChildren<{ title: string }>) {
  return (
    <View style={{ gap: space.xxs, marginBottom: space.lg }}>
      <Txt variant="title" accessibilityRole="header">
        {title}
      </Txt>
      <Txt color="muted">{children}</Txt>
    </View>
  );
}

/** Name and photo. The email is shown but cannot be changed here (it is the login). */
export function EditProfileScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { user, refreshUser } = useAuth();
  const avatar = useAvatarPicker();
  const [name, setName] = useState(user?.full_name ?? '');
  const [error, setError] = useState<string>();
  const [saving, setSaving] = useState(false);

  const trimmed = name.trim().replace(/\s+/g, ' ');
  const invalid = trimmed.length < 2;
  const unchanged = trimmed === (user?.full_name ?? '').trim();

  async function save() {
    setError(undefined);
    setSaving(true);
    try {
      await api('/users/me', { method: 'PATCH', body: { full_name: trimmed } });
      await refreshUser();
      showToast(t('profile.edit.saved'), 'success');
      back();
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Screen
      header={<Header title={t('profile.edit.title')} />}
      footer={<Button title={t('common.save')} loading={saving} disabled={invalid || unchanged} onPress={() => void save()} />}>
      <Intro title={t('profile.edit.heading')}>{t('profile.edit.subtitle')}</Intro>

      <View style={{ alignItems: 'center', marginBottom: space.xl }}>
        <View style={{ backgroundColor: theme.hero, borderRadius: 999, padding: 2 }}>
          <ProfileAvatar
            name={trimmed || user?.full_name}
            email={user?.email}
            photoUrl={user?.avatar_url}
            busy={avatar.busy}
            onEdit={avatar.open}
            editLabel={t('profile.photo.change')}
          />
        </View>
        <Button title={t('profile.photo.change')} variant="ghost" size="sm" onPress={avatar.open} />
      </View>

      <Field
        label={t('auth.fullName')}
        icon={UserIcon}
        value={name}
        onChangeText={setName}
        autoComplete="name"
        textContentType="name"
        autoCapitalize="words"
        maxLength={150}
        returnKeyType="done"
        onSubmitEditing={() => (!invalid && !unchanged ? void save() : undefined)}
        error={name.length > 0 && invalid ? t('profile.edit.nameTooShort') : undefined}
        hint={t('profile.edit.nameHint')}
      />
      <Field label={t('auth.email')} icon={Mail} value={user?.email ?? ''} editable={false} hint={t('profile.edit.emailHint')} />
      {error ? <Notice tone="danger">{error}</Notice> : null}
      {avatar.sheet}
    </Screen>
  );
}

/** Change password: current one, new one (8+ characters) and confirmation. */
export function PasswordScreen() {
  const { t } = useTranslation();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [error, setError] = useState<string>();
  const [saving, setSaving] = useState(false);

  const tooShort = next.length > 0 && next.length < 8;
  const mismatch = repeat.length > 0 && repeat !== next;
  const sameAsCurrent = next.length > 0 && next === current;
  const ready = current.length > 0 && next.length >= 8 && repeat === next && !sameAsCurrent;

  async function save() {
    setError(undefined);
    setSaving(true);
    try {
      await api('/users/me/password', { method: 'POST', body: { current_password: current, new_password: next } });
      showToast(t('profile.password.saved'), 'success');
      back();
    } catch (e) {
      setError(e instanceof ApiError && e.code === 'invalid_credentials' ? t('profile.password.wrongCurrent') : apiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Screen
      header={<Header title={t('profile.password.title')} />}
      footer={<Button title={t('profile.password.save')} loading={saving} disabled={!ready} onPress={() => void save()} />}>
      <Intro title={t('profile.password.heading')}>{t('profile.password.subtitle')}</Intro>
      <Field
        label={t('profile.password.current')}
        icon={LockKeyhole}
        value={current}
        onChangeText={setCurrent}
        secureToggle
        autoComplete="current-password"
        textContentType="password"
      />
      <Field
        label={t('profile.password.new')}
        icon={LockKeyhole}
        value={next}
        onChangeText={setNext}
        secureToggle
        autoComplete="new-password"
        textContentType="newPassword"
        error={tooShort ? t('validation.password') : sameAsCurrent ? t('profile.password.same') : undefined}
        hint={t('validation.password')}
      />
      <Field
        label={t('profile.password.repeat')}
        icon={LockKeyhole}
        value={repeat}
        onChangeText={setRepeat}
        secureToggle
        autoComplete="new-password"
        textContentType="newPassword"
        returnKeyType="done"
        onSubmitEditing={() => (ready ? void save() : undefined)}
        error={mismatch ? t('profile.password.mismatch') : undefined}
      />
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <Notice tone="info">{t('profile.password.socialNote')}</Notice>
    </Screen>
  );
}
