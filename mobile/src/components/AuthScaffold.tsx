import { type PropsWithChildren, type ReactNode } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { HeroHeader, HeroSheet } from '@/components/HeroHeader';
import { space, useTheme } from '@/theme';

/** Green brand header with a rounded form sheet below, keyboard-aware. Used by login and register. */
export function AuthScaffold({
  title,
  subtitle,
  leading,
  footer,
  children,
}: PropsWithChildren<{ title: string; subtitle?: string; leading?: ReactNode; footer?: ReactNode }>) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.background }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ flexGrow: 1, paddingBottom: insets.bottom + space.xl }}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}>
        <HeroHeader title={title} subtitle={subtitle} leading={leading} />
        <HeroSheet>
          {children}
          {footer ? <View style={{ marginTop: 'auto', paddingTop: space.xl, alignItems: 'center', gap: space.sm }}>{footer}</View> : null}
        </HeroSheet>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
