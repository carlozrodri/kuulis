import { type PropsWithChildren } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useTheme } from '@/theme';

export function Screen({ children }: PropsWithChildren) {
  const theme = useTheme();
  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: theme.background }]} edges={['top', 'left', 'right']}>
      {children}
    </SafeAreaView>
  );
}

export function Title({ children }: PropsWithChildren) {
  const theme = useTheme();
  return <Text style={[styles.title, { color: theme.text }]}>{children}</Text>;
}

export function Body({ children, muted }: PropsWithChildren<{ muted?: boolean }>) {
  const theme = useTheme();
  return <Text style={[styles.body, { color: muted ? theme.muted : theme.text }]}>{children}</Text>;
}

export function ErrorText({ children }: PropsWithChildren) {
  const theme = useTheme();
  if (!children) return null;
  return <Text style={[styles.body, { color: theme.danger }]}>{children}</Text>;
}

export function Field({ label, error, ...props }: TextInputProps & { label: string; error?: string }) {
  const theme = useTheme();
  return (
    <View style={styles.field}>
      <Text style={[styles.label, { color: theme.muted }]}>{label}</Text>
      <TextInput
        placeholderTextColor={theme.muted}
        style={[styles.input, { color: theme.text, borderColor: error ? theme.danger : theme.border, backgroundColor: theme.surface }]}
        {...props}
      />
      {error ? <Text style={[styles.hint, { color: theme.danger }]}>{error}</Text> : null}
    </View>
  );
}

export function Button({
  title,
  onPress,
  loading,
  variant = 'primary',
}: {
  title: string;
  onPress: () => void;
  loading?: boolean;
  variant?: 'primary' | 'ghost';
}) {
  const theme = useTheme();
  const primary = variant === 'primary';
  return (
    <Pressable
      accessibilityRole="button"
      disabled={loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: primary ? theme.primary : 'transparent', opacity: pressed || loading ? 0.7 : 1 },
      ]}>
      {loading ? (
        <ActivityIndicator color={primary ? '#fff' : theme.primary} />
      ) : (
        <Text style={[styles.buttonText, { color: primary ? '#fff' : theme.primary }]}>{title}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, paddingHorizontal: 20 },
  title: { fontSize: 26, fontWeight: '700', marginVertical: 16 },
  body: { fontSize: 15, lineHeight: 22 },
  field: { marginBottom: 14 },
  label: { fontSize: 13, marginBottom: 6 },
  input: { borderWidth: 1, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  hint: { fontSize: 12, marginTop: 4 },
  button: { borderRadius: 10, paddingVertical: 14, alignItems: 'center', marginTop: 8 },
  buttonText: { fontSize: 16, fontWeight: '600' },
});
