import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Image, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Ellipse, Path, Rect } from 'react-native-svg';

import {
  Bike,
  Camera,
  ChevronLeft,
  Glasses,
  type Icon,
  Plus,
  RotateCcw,
  ScanFace,
  Sun,
  UserRoundCheck,
  X,
} from '@/components/icons';
import { Button, Card, EmptyState, ErrorText, IconButton, IconTile, Notice, Row, Screen, Skeleton, type Tone, Txt } from '@/components/ui';
import { useAppConfig, useDriverProfile, useSubmitCheck } from '@/hooks/useDriver';
import { confirmHaptic } from '@/lib/feedback';
import { MAX_VEHICLE_PHOTOS } from '@/lib/driver';
import type { LocalFile } from '@/lib/upload';
import { checkInReview, photosNeeded, requestedCheck } from '@/lib/verification';
import { useMode } from '@/providers/ModeProvider';
import { radius, space, useTheme } from '@/theme';

import { PermissionDenied, pickFile } from './pickFile';
import { connectRequest } from './store';
import { CameraDeniedNotice, uploadErrorMessage } from './useDocumentUpload';

const back = () => (router.canGoBack() ? router.back() : router.replace('/'));

const TIPS: { key: string; icon: Icon; tone: Tone }[] = [
  { key: 'light', icon: Sun, tone: 'accent' },
  { key: 'clear', icon: Glasses, tone: 'info' },
  { key: 'center', icon: ScanFace, tone: 'primary' },
];

/**
 * Live selfie (doc 12): asked at random about once a week when going online, or with new moto photos
 * (re-verification) after reports. Front camera only, never the gallery; moto photos with the back camera.
 * Once sent the driver can go online right away while a verifier compares it with the cédula.
 */
export function SelfieScreen() {
  const { t } = useTranslation();
  const params = useLocalSearchParams<{ checkId?: string; kind?: string }>();
  const profile = useDriverProfile();
  const { config } = useAppConfig();
  const submit = useSubmitCheck();
  const { mode } = useMode();
  const [selfie, setSelfie] = useState<LocalFile | null>(null);
  const [photos, setPhotos] = useState<LocalFile[]>([]);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  // The kind of check just sent (the profile then no longer lists it as requested).
  const [sent, setSent] = useState<'selfie' | 'reverification' | null>(null);
  const [error, setError] = useState<string>();
  const [cameraDenied, setCameraDenied] = useState(false);

  // The check may have been created a moment ago by going online: read it fresh.
  const { refetch } = profile;
  useEffect(() => {
    void refetch();
  }, [refetch]);

  const check = requestedCheck(profile.data, params.checkId);
  // A check from the route that the fresh profile no longer asks for was already sent (e.g. an old push).
  const settled = !!profile.data && !profile.isFetching;
  const checkId = check?.id ?? (settled ? null : params.checkId) ?? null;
  const kind = sent ?? ((check?.kind ?? params.kind) === 'reverification' ? 'reverification' : 'selfie');
  const needed = photosNeeded(kind, config);
  const inReview = checkInReview(profile.data);

  async function take(source: 'selfie' | 'camera') {
    setError(undefined);
    setCameraDenied(false);
    try {
      const file = await pickFile(source);
      if (!file) return;
      if (source === 'selfie') setSelfie(file);
      else setPhotos((list) => [...list, file].slice(0, MAX_VEHICLE_PHOTOS));
    } catch (e) {
      if (e instanceof PermissionDenied) setCameraDenied(true);
      else setError(uploadErrorMessage(e, t));
    }
  }

  async function send() {
    if (!checkId || !selfie) return;
    setError(undefined);
    try {
      await submit.mutateAsync({
        checkId,
        files: [{ kind: 'selfie', file: selfie }, ...photos.map((file) => ({ kind: 'vehicle_photo' as const, file }))],
        onProgress: (done, total) => setProgress({ done, total }),
      });
      confirmHaptic();
      setSent(kind);
    } catch (e) {
      setError(uploadErrorMessage(e, t));
    } finally {
      setProgress(null);
    }
  }

  const header = (
    <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
      <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
    </Row>
  );

  if (sent || (!checkId && inReview)) {
    const canConnect = sent || profile.data?.verification?.can_go_online !== false;
    return (
      <Screen
        header={header}
        footer={
          <>
            {canConnect && mode === 'driver' && profile.data?.status === 'approved' ? (
              <Button
                title={t('verification.selfie.connectNow')}
                onPress={() => {
                  connectRequest.set(Date.now());
                  router.dismissTo('/');
                }}
              />
            ) : null}
            <Button title={t('common.back')} variant="ghost" onPress={back} />
          </>
        }>
        <Hero
          icon={UserRoundCheck}
          tone="info"
          title={t('verification.selfie.sentTitle')}
          body={t(kind === 'reverification' ? 'verification.selfie.sentBodyMoto' : 'verification.selfie.sentBody')}
        />
        <Notice tone="info">{t('verification.selfie.sentNotify')}</Notice>
      </Screen>
    );
  }

  if (!checkId) {
    return (
      <Screen header={header}>
        {profile.isPending || profile.isFetching ? (
          <View style={{ gap: space.md }}>
            <Skeleton height={260} radius={radius.card} />
            <Skeleton height={60} />
          </View>
        ) : (
          <>
            <EmptyState icon={UserRoundCheck} title={t('verification.selfie.nothingTitle')} body={t('verification.selfie.nothingBody')} />
            <Button title={t('common.back')} variant="secondary" onPress={back} />
          </>
        )}
      </Screen>
    );
  }

  const busy = submit.isPending;
  const ready = !!selfie && photos.length >= needed;
  const uploadingLabel = progress
    ? t('verification.selfie.uploading', { done: Math.min(progress.done + 1, progress.total), total: progress.total })
    : undefined;

  if (!selfie) {
    return (
      <Screen
        header={header}
        footer={<Button title={t('verification.selfie.take')} icon={Camera} size="lg" onPress={() => void take('selfie')} />}>
        <Txt variant="title" accessibilityRole="header">
          {t(kind === 'reverification' ? 'verification.selfie.titleMoto' : 'verification.selfie.title')}
        </Txt>
        <Txt color="muted" style={{ marginTop: space.xxs }}>
          {kind === 'reverification'
            ? t('verification.selfie.bodyMoto', { count: needed })
            : t('verification.selfie.body')}
        </Txt>
        <View style={{ alignItems: 'center', marginVertical: space.xl }}>
          <FaceGuide />
        </View>
        <Card style={{ gap: space.md }}>
          {TIPS.map((tip) => (
            <View key={tip.key} style={styles.tip}>
              <IconTile icon={tip.icon} tone={tip.tone} size={44} />
              <View style={{ flex: 1, gap: 2 }}>
                <Txt variant="bodyStrong">{t(`verification.selfie.tips.${tip.key}.title`)}</Txt>
                <Txt variant="caption" color="muted">
                  {t(`verification.selfie.tips.${tip.key}.body`)}
                </Txt>
              </View>
            </View>
          ))}
        </Card>
        {cameraDenied ? <CameraDeniedNotice library={false} style={{ marginTop: space.md }} /> : null}
        <View style={{ marginTop: space.md }}>
          <ErrorText>{error}</ErrorText>
        </View>
      </Screen>
    );
  }

  return (
    <Screen
      header={header}
      footer={
        <>
          {!ready ? (
            <Txt variant="caption" color="muted" align="center">
              {t('verification.selfie.photosMissing', { count: needed - photos.length })}
            </Txt>
          ) : uploadingLabel ? (
            <Txt variant="caption" color="muted" align="center">
              {uploadingLabel}
            </Txt>
          ) : null}
          <Button
            title={t('verification.selfie.send')}
            size="lg"
            loading={busy}
            disabled={!ready}
            accessibilityHint={uploadingLabel}
            onPress={() => void send()}
          />
        </>
      }>
      <Txt variant="title" accessibilityRole="header">
        {t('verification.selfie.reviewTitle')}
      </Txt>
      <Txt color="muted" style={{ marginTop: space.xxs, marginBottom: space.lg }}>
        {t('verification.selfie.reviewBody')}
      </Txt>
      <SelfiePreview uri={selfie.uri} />
      <Button
        title={t('verification.selfie.retake')}
        variant="secondary"
        icon={RotateCcw}
        disabled={busy}
        style={{ marginTop: space.md }}
        onPress={() => void take('selfie')}
      />

      {needed > 0 ? (
        <>
          <Txt variant="overline" color="muted" style={{ marginTop: space.xl, marginBottom: space.xs }}>
            {t('verification.selfie.motoTitle')}
          </Txt>
          <Card style={{ gap: space.md }}>
            <Row>
              <IconTile icon={Bike} tone="accent" />
              <View style={{ flex: 1 }}>
                <Txt variant="bodyStrong">{t('driver.documents.photosCount', { count: photos.length, required: needed })}</Txt>
                <Txt variant="caption" color="muted">
                  {t('verification.selfie.motoHint')}
                </Txt>
              </View>
            </Row>
            {photos.length ? (
              <View style={styles.grid}>
                {photos.map((photo, index) => (
                  <View key={photo.uri} style={styles.thumbWrap}>
                    <Image source={{ uri: photo.uri }} style={styles.thumb} accessibilityIgnoresInvertColors />
                    <RemoveBadge
                      label={t('driver.documents.deletePhoto', { n: index + 1 })}
                      disabled={busy}
                      onPress={() => setPhotos((list) => list.filter((item) => item !== photo))}
                    />
                  </View>
                ))}
              </View>
            ) : null}
            {photos.length < MAX_VEHICLE_PHOTOS ? (
              <Button
                title={photos.length ? t('driver.documents.addPhoto') : t('verification.selfie.motoTake')}
                variant="secondary"
                icon={photos.length ? Plus : Camera}
                disabled={busy}
                onPress={() => void take('camera')}
              />
            ) : null}
          </Card>
        </>
      ) : null}

      {cameraDenied ? <CameraDeniedNotice library={false} style={{ marginTop: space.md }} /> : null}
      <View style={{ marginTop: space.md }}>
        <ErrorText>{error}</ErrorText>
      </View>
      <Notice tone="info" style={{ marginTop: space.xs }}>
        {t('verification.selfie.privacy')}
      </Notice>
    </Screen>
  );
}

/** Round success / review hero, as on the onboarding status screens. */
function Hero({ icon: HeroIcon, tone, title, body }: { icon: Icon; tone: Tone; title: string; body: string }) {
  const theme = useTheme();
  const fg = tone === 'info' ? theme.info : theme.primary;
  const bg = tone === 'info' ? theme.infoSoft : theme.surfaceAlt;
  return (
    <View style={styles.hero}>
      <View style={[styles.ring, { backgroundColor: bg }]}>
        <View style={[styles.ringIcon, { backgroundColor: theme.surface }]}>
          <HeroIcon size={40} color={fg} strokeWidth={2} />
        </View>
      </View>
      <Txt variant="title" align="center" accessibilityRole="header">
        {title}
      </Txt>
      <Txt color="muted" align="center">
        {body}
      </Txt>
    </View>
  );
}

/** Face framing illustration: a dashed oval over a head and shoulders silhouette, with corner marks. */
function FaceGuide() {
  const theme = useTheme();
  const corner = theme.scheme === 'dark' ? theme.accent : theme.primary;
  return (
    <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Svg width={220} height={250} viewBox="0 0 220 250">
        <Rect x={0} y={0} width={220} height={250} rx={32} fill={theme.surfaceAlt} />
        <Path d="M30 250 C36 200 72 184 110 184 C148 184 184 200 190 250 Z" fill={theme.border} />
        <Ellipse cx={110} cy={112} rx={50} ry={62} fill={theme.border} />
        <Ellipse cx={110} cy={112} rx={70} ry={88} fill="none" stroke={theme.primary} strokeWidth={4} strokeDasharray="12 9" strokeLinecap="round" />
        <Path d="M20 50 V28 Q20 20 28 20 H50" fill="none" stroke={corner} strokeWidth={5} strokeLinecap="round" />
        <Path d="M170 20 H192 Q200 20 200 28 V50" fill="none" stroke={corner} strokeWidth={5} strokeLinecap="round" />
        <Path d="M20 180 V202 Q20 210 28 210 H50" fill="none" stroke={corner} strokeWidth={5} strokeLinecap="round" />
        <Path d="M170 210 H192 Q200 210 200 202 V180" fill="none" stroke={corner} strokeWidth={5} strokeLinecap="round" />
      </Svg>
    </View>
  );
}

/** The selfie just taken, framed like the guide. */
function SelfiePreview({ uri }: { uri: string }) {
  const theme = useTheme();
  const { t } = useTranslation();
  return (
    <View style={[styles.preview, { backgroundColor: theme.surfaceAlt, borderColor: theme.primary }]}>
      <Image
        source={{ uri }}
        style={StyleSheet.absoluteFill}
        resizeMode="cover"
        accessibilityLabel={t('verification.selfie.previewA11y')}
        accessibilityIgnoresInvertColors
      />
    </View>
  );
}

function RemoveBadge({ label, disabled, onPress }: { label: string; disabled: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={8}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [styles.remove, { backgroundColor: theme.surface, opacity: pressed || disabled ? 0.6 : 1 }]}>
      <X size={14} color={theme.danger} strokeWidth={2.6} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tip: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  hero: { alignItems: 'center', gap: space.sm, paddingTop: space.xl, paddingBottom: space.lg },
  ring: { width: 128, height: 128, borderRadius: 64, alignItems: 'center', justifyContent: 'center', marginBottom: space.sm },
  ringIcon: { width: 84, height: 84, borderRadius: 42, alignItems: 'center', justifyContent: 'center' },
  preview: {
    alignSelf: 'center',
    width: 220,
    height: 280,
    borderRadius: 110,
    borderWidth: 4,
    overflow: 'hidden',
  },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: space.xs },
  thumbWrap: { width: 92, height: 92 },
  thumb: { width: 92, height: 92, borderRadius: radius.field },
  remove: {
    position: 'absolute',
    top: -6,
    right: -6,
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
