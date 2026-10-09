import { type ComponentProps, type PropsWithChildren, type ReactElement, type ReactNode, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  type RefreshControlProps,
  ScrollView,
  type StyleProp,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  type TextStyle,
  View,
  type ViewStyle,
} from 'react-native';
import { useTranslation } from 'react-i18next';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

import { ChevronRight, CircleCheck, Eye, EyeOff, type Icon, Info, TriangleAlert, X } from '@/components/icons';
import { elevation, fonts, radius, space, type Theme, type TypeVariant, type, useTheme } from '@/theme';

/** Space the floating tab bar takes at the bottom of tab screens (bar + gap). */
export const TAB_BAR_HEIGHT = 64;
export const TAB_BAR_SPACE = TAB_BAR_HEIGHT + 32;

type ColorKey = { [K in keyof Theme]: Theme[K] extends string ? K : never }[keyof Theme];

// ── Text ──

export type TxtProps = PropsWithChildren<{
  variant?: TypeVariant;
  color?: ColorKey;
  align?: TextStyle['textAlign'];
  style?: StyleProp<TextStyle>;
  numberOfLines?: number;
  tabular?: boolean;
  accessibilityRole?: ComponentProps<typeof Text>['accessibilityRole'];
}>;

export function Txt({ variant = 'body', color = 'text', align, style, tabular, children, ...rest }: TxtProps) {
  const theme = useTheme();
  return (
    <Text
      maxFontSizeMultiplier={1.6}
      style={[
        type[variant] as TextStyle,
        { color: theme[color], textAlign: align },
        tabular && { fontVariant: ['tabular-nums'] },
        style,
      ]}
      {...rest}>
      {children}
    </Text>
  );
}

export function Title({ children, style }: PropsWithChildren<{ style?: StyleProp<TextStyle> }>) {
  return (
    <Txt variant="title" accessibilityRole="header" style={[{ marginBottom: space.xs }, style]}>
      {children}
    </Txt>
  );
}

export function Body({ children, muted, style }: PropsWithChildren<{ muted?: boolean; style?: StyleProp<TextStyle> }>) {
  return (
    <Txt color={muted ? 'muted' : 'text'} style={style}>
      {children}
    </Txt>
  );
}

export function SectionLabel({ children, style }: PropsWithChildren<{ style?: StyleProp<TextStyle> }>) {
  return (
    <Txt variant="overline" color="muted" style={[{ marginBottom: space.xs, marginTop: space.lg }, style]}>
      {children}
    </Txt>
  );
}

/** Inline error banner for forms. Renders nothing when empty. */
export function ErrorText({ children }: PropsWithChildren) {
  if (!children) return null;
  return (
    <Notice tone="danger" style={{ marginVertical: space.xs }}>
      {children}
    </Notice>
  );
}

// ── Layout ──

export function Screen({
  children,
  scroll = true,
  padded = true,
  tabBar = false,
  footer,
  header,
  edges = ['top', 'left', 'right'],
  refreshControl,
  contentStyle,
  background,
}: PropsWithChildren<{
  scroll?: boolean;
  padded?: boolean;
  /** Leaves room for the floating tab bar. */
  tabBar?: boolean;
  /** Sticky content at the bottom (main call to action). */
  footer?: ReactNode;
  /** Content above the scroll area (step headers). */
  header?: ReactNode;
  edges?: ('top' | 'bottom' | 'left' | 'right')[];
  refreshControl?: ReactElement<RefreshControlProps>;
  contentStyle?: StyleProp<ViewStyle>;
  background?: ColorKey;
}>) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const bottom = tabBar ? TAB_BAR_SPACE + insets.bottom : footer ? space.md : Math.max(insets.bottom, space.md) + space.md;
  const padding = padded ? { paddingHorizontal: space.lg } : null;

  return (
    <SafeAreaView style={[styles.flex, { backgroundColor: theme[background ?? 'background'] }]} edges={edges}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {header ? <View style={padding}>{header}</View> : null}
        {scroll ? (
          <ScrollView
            style={styles.flex}
            contentContainerStyle={[padding, { paddingBottom: bottom, flexGrow: 1 }, contentStyle]}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
            refreshControl={refreshControl}>
            {children}
          </ScrollView>
        ) : (
          <View style={[styles.flex, padding, { paddingBottom: footer ? 0 : bottom }, contentStyle]}>{children}</View>
        )}
        {footer ? (
          <View
            style={[
              styles.footer,
              { paddingBottom: Math.max(insets.bottom, space.md), backgroundColor: theme[background ?? 'background'] },
            ]}>
            {footer}
          </View>
        ) : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function Row({ children, gap = space.sm, style }: PropsWithChildren<{ gap?: number; style?: StyleProp<ViewStyle> }>) {
  return <View style={[{ flexDirection: 'row', alignItems: 'center', gap }, style]}>{children}</View>;
}

export function Spacer({ size = space.md }: { size?: number }) {
  return <View style={{ height: size }} />;
}

// ── Inputs ──

export type FieldProps = TextInputProps & {
  label: string;
  error?: string;
  hint?: string;
  icon?: Icon;
  /** Adds a show/hide toggle for passwords. */
  secureToggle?: boolean;
};

export function Field({ label, error, hint, icon: LeftIcon, secureToggle, style, onFocus, onBlur, ...props }: FieldProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const [focused, setFocused] = useState(false);
  const [hidden, setHidden] = useState(true);
  const borderColor = error ? theme.danger : focused ? theme.primary : theme.border;

  return (
    <View style={styles.field}>
      <Txt variant="label" color="muted" style={{ marginBottom: 6 }}>
        {label}
      </Txt>
      <View style={[styles.inputWrap, { borderColor, backgroundColor: theme.surface }]}>
        {LeftIcon ? <LeftIcon size={20} color={focused ? theme.primary : theme.muted} strokeWidth={2} /> : null}
        <TextInput
          accessibilityLabel={label}
          placeholderTextColor={theme.muted}
          selectionColor={theme.primary}
          cursorColor={theme.primary}
          maxFontSizeMultiplier={1.6}
          style={[styles.input, { color: theme.text }, style]}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
          {...props}
          secureTextEntry={secureToggle ? hidden : props.secureTextEntry}
        />
        {secureToggle ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={hidden ? t('a11y.showPassword') : t('a11y.hidePassword')}
            hitSlop={12}
            onPress={() => setHidden((v) => !v)}>
            {hidden ? <Eye size={20} color={theme.muted} /> : <EyeOff size={20} color={theme.muted} />}
          </Pressable>
        ) : null}
      </View>
      {error ? (
        <Txt variant="caption" color="danger" style={{ marginTop: 6 }}>
          {error}
        </Txt>
      ) : hint ? (
        <Txt variant="caption" color="muted" style={{ marginTop: 6 }}>
          {hint}
        </Txt>
      ) : null}
    </View>
  );
}

// ── Buttons ──

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent';

export function Button({
  title,
  onPress,
  loading,
  disabled,
  variant = 'primary',
  size = 'md',
  icon: LeadingIcon,
  accessibilityLabel,
  accessibilityHint,
  style,
}: {
  title: string;
  onPress?: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: ButtonVariant;
  /** md = 56 px (default); lg = 68 px for driver actions used with gloves; sm = 40 px. */
  size?: 'sm' | 'md' | 'lg';
  icon?: Icon;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const theme = useTheme();
  const inactive = disabled || loading;
  const palette = buttonPalette(theme, variant, !!disabled);
  const height = size === 'lg' ? 68 : size === 'sm' ? 40 : 56;
  const uppercase = variant === 'primary' || variant === 'accent' || (variant === 'danger' && size !== 'sm');

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? title}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: !!inactive, busy: !!loading }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        {
          height,
          paddingHorizontal: size === 'sm' ? space.md : space.xl,
          backgroundColor: pressed ? palette.pressed : palette.bg,
          borderColor: palette.border,
          borderWidth: palette.border === 'transparent' ? 0 : 1.5,
          transform: [{ scale: pressed ? 0.98 : 1 }],
        },
        style,
      ]}>
      {loading ? (
        <ActivityIndicator color={palette.fg} />
      ) : (
        <>
          {LeadingIcon ? <LeadingIcon size={size === 'sm' ? 16 : 20} color={palette.fg} strokeWidth={2.2} /> : null}
          <Text
            maxFontSizeMultiplier={1.3}
            numberOfLines={1}
            style={[
              uppercase ? type.button : { fontFamily: fonts.bold, fontSize: size === 'sm' ? 13 : 15 },
              size === 'lg' && { fontSize: 17, letterSpacing: 1.2 },
              size === 'sm' && uppercase && { fontSize: 12 },
              { color: palette.fg },
            ]}>
            {uppercase ? title.toLocaleUpperCase() : title}
          </Text>
        </>
      )}
    </Pressable>
  );
}

function buttonPalette(theme: Theme, variant: ButtonVariant, disabled: boolean) {
  if (disabled && variant !== 'ghost') {
    return { bg: theme.disabled, pressed: theme.disabled, fg: theme.onDisabled, border: 'transparent' };
  }
  switch (variant) {
    case 'primary':
      return { bg: theme.primary, pressed: theme.primaryPressed, fg: theme.onPrimary, border: 'transparent' };
    case 'accent':
      return { bg: theme.accent, pressed: theme.accent, fg: theme.onAccent, border: 'transparent' };
    case 'secondary':
      return { bg: theme.surface, pressed: theme.surfaceAlt, fg: theme.text, border: theme.border };
    case 'danger':
      return { bg: theme.dangerSoft, pressed: theme.dangerSoft, fg: theme.danger, border: 'transparent' };
    case 'ghost':
    default:
      return {
        bg: 'transparent',
        pressed: theme.surfaceAlt,
        fg: disabled ? theme.muted : theme.scheme === 'dark' ? theme.primary : theme.primaryPressed,
        border: 'transparent',
      };
  }
}

/** Round icon-only button. `label` is required for screen readers. */
export function IconButton({
  icon: IconComponent,
  label,
  onPress,
  tone = 'surface',
  size = 44,
}: {
  icon: Icon;
  label: string;
  onPress?: () => void;
  tone?: 'surface' | 'onHero' | 'plain';
  size?: number;
}) {
  const theme = useTheme();
  const bg = tone === 'surface' ? theme.surface : tone === 'onHero' ? 'rgba(255,255,255,0.16)' : 'transparent';
  const fg = tone === 'onHero' ? theme.onHero : theme.text;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={8}
      onPress={onPress}
      style={({ pressed }) => [
        styles.iconButton,
        { width: size, height: size, backgroundColor: bg, opacity: pressed ? 0.7 : 1 },
        tone === 'surface' && elevation(theme),
      ]}>
      <IconComponent size={22} color={fg} strokeWidth={2.2} />
    </Pressable>
  );
}

// ── Surfaces ──

export function Card({
  children,
  onPress,
  tone = 'surface',
  elevated = false,
  style,
  accessibilityLabel,
  accessibilityHint,
  selected,
}: PropsWithChildren<{
  onPress?: () => void;
  tone?: 'surface' | 'tint' | 'accent';
  elevated?: boolean;
  style?: StyleProp<ViewStyle>;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  selected?: boolean;
}>) {
  const theme = useTheme();
  const bg = tone === 'tint' ? theme.surfaceAlt : tone === 'accent' ? theme.accentSoft : theme.surface;
  const base: StyleProp<ViewStyle> = [
    styles.card,
    { backgroundColor: selected ? theme.surfaceAlt : bg, borderColor: selected ? theme.primary : 'transparent' },
    elevated && elevation(theme),
    style,
  ];
  if (!onPress) return <View style={base}>{children}</View>;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={accessibilityHint}
      accessibilityState={selected !== undefined ? { selected } : undefined}
      onPress={onPress}
      style={({ pressed }) => [base, { transform: [{ scale: pressed ? 0.985 : 1 }], opacity: pressed ? 0.94 : 1 }]}>
      {children}
    </Pressable>
  );
}

export type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'accent' | 'primary';

export function toneColors(theme: Theme, tone: Tone) {
  switch (tone) {
    case 'success':
      return { bg: theme.successSoft, fg: theme.success };
    case 'warning':
      return { bg: theme.warningSoft, fg: theme.warning };
    case 'danger':
      return { bg: theme.dangerSoft, fg: theme.danger };
    case 'info':
      return { bg: theme.infoSoft, fg: theme.info };
    case 'accent':
      return { bg: theme.accent, fg: theme.onAccent };
    case 'primary':
      return { bg: theme.surfaceAlt, fg: theme.scheme === 'dark' ? theme.primary : theme.primaryPressed };
    case 'neutral':
    default:
      return { bg: theme.background, fg: theme.muted };
  }
}

/** Small rounded label for statuses ("En revisión", "Listo"…). */
export function StatusPill({ label, tone = 'neutral', dot }: { label: string; tone?: Tone; dot?: boolean }) {
  const theme = useTheme();
  const colors = toneColors(theme, tone);
  return (
    <View style={[styles.pill, { backgroundColor: colors.bg }]}>
      {dot ? <View style={[styles.pillDot, { backgroundColor: colors.fg }]} /> : null}
      <Txt variant="micro" style={{ color: colors.fg }} numberOfLines={1}>
        {label}
      </Txt>
    </View>
  );
}

export const Badge = StatusPill;

export function Chip({
  label,
  selected,
  onPress,
  icon: ChipIcon,
}: {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  icon?: Icon;
}) {
  const theme = useTheme();
  const fg = selected ? (theme.scheme === 'dark' ? theme.primary : theme.primaryPressed) : theme.text;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: !!selected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        {
          backgroundColor: selected ? theme.surfaceAlt : theme.surface,
          borderColor: selected ? theme.primary : theme.border,
          opacity: pressed ? 0.8 : 1,
        },
      ]}>
      {ChipIcon ? <ChipIcon size={16} color={fg} strokeWidth={2.2} /> : null}
      <Txt variant="label" style={{ color: fg }}>
        {label}
      </Txt>
    </Pressable>
  );
}

/** Rounded square with an icon, used at the start of rows and cards. */
export function IconTile({ icon: TileIcon, tone = 'primary', size = 44 }: { icon: Icon; tone?: Tone; size?: number }) {
  const theme = useTheme();
  const colors = tone === 'accent' ? { bg: theme.accentSoft, fg: theme.onAccentSoft } : toneColors(theme, tone);
  return (
    <View style={[styles.tile, { width: size, height: size, borderRadius: size * 0.32, backgroundColor: colors.bg }]}>
      <TileIcon size={size * 0.48} color={colors.fg} strokeWidth={2} />
    </View>
  );
}

/** Segmented progress bar for multi-step flows. `current` is 1-based. */
export function ProgressSteps({ total, current, label }: { total: number; current: number; label?: string }) {
  const theme = useTheme();
  return (
    <View
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max: total, now: current }}>
      {label ? (
        <Txt variant="label" color="muted" style={{ marginBottom: space.xs }}>
          {label}
        </Txt>
      ) : null}
      <View style={styles.progress}>
        {Array.from({ length: total }, (_, i) => (
          <View
            key={i}
            style={[styles.progressSegment, { backgroundColor: i < current ? theme.primary : theme.border }]}
          />
        ))}
      </View>
    </View>
  );
}

export function ListRow({
  title,
  subtitle,
  icon,
  iconTone = 'primary',
  right,
  onPress,
  chevron = !!onPress,
  divider = false,
  accessibilityLabel,
  accessibilityHint,
}: {
  title: string;
  subtitle?: string | null;
  icon?: Icon;
  iconTone?: Tone;
  right?: ReactNode;
  onPress?: () => void;
  chevron?: boolean;
  divider?: boolean;
  accessibilityLabel?: string;
  accessibilityHint?: string;
}) {
  const theme = useTheme();
  const content = (
    <View style={[styles.row, divider && { borderBottomWidth: 1, borderBottomColor: theme.divider }]}>
      {icon ? <IconTile icon={icon} tone={iconTone} size={40} /> : null}
      <View style={styles.flex}>
        <Txt variant="bodyStrong" numberOfLines={2}>
          {title}
        </Txt>
        {subtitle ? (
          <Txt variant="caption" color="muted">
            {subtitle}
          </Txt>
        ) : null}
      </View>
      {right}
      {chevron ? <ChevronRight size={20} color={theme.muted} strokeWidth={2.2} /> : null}
    </View>
  );
  if (!onPress) return content;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? title}
      accessibilityHint={accessibilityHint}
      onPress={onPress}
      style={({ pressed }) => ({ opacity: pressed ? 0.6 : 1 })}>
      {content}
    </Pressable>
  );
}

export function Notice({
  children,
  title,
  tone = 'info',
  icon,
  style,
}: PropsWithChildren<{ title?: string; tone?: Tone; icon?: Icon; style?: StyleProp<ViewStyle> }>) {
  const theme = useTheme();
  const colors =
    tone === 'accent' ? { bg: theme.accentSoft, fg: theme.onAccentSoft } : toneColors(theme, tone === 'neutral' ? 'neutral' : tone);
  const NoticeIcon = icon ?? (tone === 'danger' || tone === 'warning' ? TriangleAlert : tone === 'success' ? CircleCheck : Info);
  return (
    <View accessibilityRole="alert" style={[styles.notice, { backgroundColor: colors.bg }, style]}>
      <NoticeIcon size={20} color={colors.fg} strokeWidth={2} style={{ marginTop: 1 }} />
      <View style={[styles.flex, { gap: 2 }]}>
        {title ? <Txt variant="bodyStrong" style={{ color: colors.fg }}>{title}</Txt> : null}
        {typeof children === 'string' ? (
          <Txt variant="caption" style={{ color: tone === 'accent' ? colors.fg : theme.text, fontSize: 14, lineHeight: 20 }}>
            {children}
          </Txt>
        ) : (
          children
        )}
      </View>
    </View>
  );
}

export function Divider({ label }: { label?: string }) {
  const theme = useTheme();
  if (!label) return <View style={[styles.hr, { backgroundColor: theme.border }]} />;
  return (
    <Row gap={space.sm} style={{ marginVertical: space.md }}>
      <View style={[styles.hr, styles.flex, { backgroundColor: theme.border }]} />
      <Txt variant="caption" color="muted">
        {label}
      </Txt>
      <View style={[styles.hr, styles.flex, { backgroundColor: theme.border }]} />
    </Row>
  );
}

/** The kuulis. wordmark: the dot is always the accent yellow. */
export function Wordmark({ size = 34, color }: { size?: number; color?: string }) {
  const theme = useTheme();
  return (
    <Text
      accessibilityRole="header"
      accessibilityLabel="Kuulis"
      maxFontSizeMultiplier={1.2}
      style={{ fontFamily: fonts.extrabold, fontSize: size, letterSpacing: -size * 0.03, color: color ?? theme.primary }}>
      kuulis<Text style={{ color: theme.accent }}>.</Text>
    </Text>
  );
}

/** Pulsing placeholder block while data loads. */
export function Skeleton({ height = 20, width = '100%', radius: r = radius.field, style }: {
  height?: number;
  width?: ViewStyle['width'];
  radius?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const theme = useTheme();
  const [opacity] = useState(() => new Animated.Value(0.5));
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.5, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);
  return <Animated.View style={[{ height, width, borderRadius: r, backgroundColor: theme.border, opacity }, style]} />;
}

export function EmptyState({ icon: EmptyIcon, title, body }: { icon: Icon; title: string; body?: string }) {
  const theme = useTheme();
  return (
    <View style={styles.empty}>
      <View style={[styles.emptyIcon, { backgroundColor: theme.surfaceAlt }]}>
        <EmptyIcon size={30} color={theme.primary} strokeWidth={2} />
      </View>
      <Txt variant="subtitle" align="center">
        {title}
      </Txt>
      {body ? (
        <Txt color="muted" align="center">
          {body}
        </Txt>
      ) : null}
    </View>
  );
}

// ── Bottom sheet ──

export type SheetOption = { label: string; icon: Icon; onPress: () => void; hint?: string; destructive?: boolean };

/** Modal bottom sheet with a list of actions (radius 28, handle on top). */
export function Sheet({
  visible,
  title,
  subtitle,
  options,
  onClose,
}: {
  visible: boolean;
  title: string;
  subtitle?: string;
  options: SheetOption[];
  onClose: () => void;
}) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { t } = useTranslation();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t('common.close')}
        style={[StyleSheet.absoluteFill, { backgroundColor: theme.backdrop }]}
        onPress={onClose}
      />
      <View style={[styles.sheet, { backgroundColor: theme.surface, paddingBottom: Math.max(insets.bottom, space.md) + space.xs }]}>
        <View style={[styles.handle, { backgroundColor: theme.border }]} />
        <Row style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <View style={styles.flex}>
            <Txt variant="heading">{title}</Txt>
            {subtitle ? (
              <Txt color="muted" style={{ marginTop: 4 }}>
                {subtitle}
              </Txt>
            ) : null}
          </View>
          <IconButton icon={X} label={t('common.close')} onPress={onClose} tone="plain" size={40} />
        </Row>
        <View style={{ marginTop: space.sm }}>
          {options.map((option, index) => (
            <ListRow
              key={option.label}
              title={option.label}
              subtitle={option.hint}
              icon={option.icon}
              iconTone={option.destructive ? 'danger' : 'primary'}
              divider={index < options.length - 1}
              chevron={false}
              onPress={() => {
                onClose();
                // Let the sheet close before opening a system picker (iOS can't present two modals at once).
                setTimeout(option.onPress, Platform.OS === 'ios' ? 450 : 50);
              }}
            />
          ))}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  footer: { paddingHorizontal: space.lg, paddingTop: space.sm, gap: space.xs },
  field: { marginBottom: space.md },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    minHeight: 52,
    borderWidth: 1.5,
    borderRadius: radius.field,
    paddingHorizontal: 14,
  },
  input: { flex: 1, fontFamily: fonts.medium, fontSize: 16, paddingVertical: 12 },
  button: {
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: space.xs,
    marginTop: space.xs,
  },
  iconButton: { borderRadius: radius.pill, alignItems: 'center', justifyContent: 'center' },
  card: { borderRadius: radius.card, padding: space.lg, borderWidth: 1.5 },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  pillDot: { width: 7, height: 7, borderRadius: 4 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1.5,
    borderRadius: radius.chip,
    paddingHorizontal: 14,
    minHeight: 40,
  },
  tile: { alignItems: 'center', justifyContent: 'center' },
  progress: { flexDirection: 'row', gap: 6 },
  progressSegment: { flex: 1, height: 6, borderRadius: 6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 12, minHeight: 60 },
  notice: { flexDirection: 'row', gap: space.sm, borderRadius: radius.tile, padding: 14 },
  hr: { height: 1 },
  empty: { alignItems: 'center', gap: space.sm, paddingVertical: space.xxxl, paddingHorizontal: space.xl },
  emptyIcon: { width: 72, height: 72, borderRadius: 36, alignItems: 'center', justifyContent: 'center', marginBottom: space.xs },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingHorizontal: space.lg,
    paddingTop: 10,
  },
  handle: { width: 40, height: 5, borderRadius: 5, alignSelf: 'center', marginBottom: space.md },
});
