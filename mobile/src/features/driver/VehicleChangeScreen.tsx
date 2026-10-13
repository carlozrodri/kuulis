import { router } from 'expo-router';
import { type ReactNode, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, Image, Pressable, RefreshControl, StyleSheet, View } from 'react-native';

import {
  ArrowLeftRight,
  Bike,
  Calendar,
  Camera,
  ChevronLeft,
  FileText,
  Hourglass,
  Image as ImageIcon,
  Plus,
  RefreshCw,
  X,
} from '@/components/icons';
import { showToast } from '@/components/Toast';
import {
  Button,
  Card,
  ErrorText,
  Field,
  IconButton,
  IconTile,
  Notice,
  Row,
  Screen,
  Sheet,
  type SheetOption,
  Skeleton,
  StatusPill,
  Txt,
} from '@/components/ui';
import { PlateBadge } from '@/features/ride/components';
import {
  useAppConfig,
  useCancelVehicleChange,
  useChangeVehicle,
  useDriverProfile,
} from '@/hooks/useDriver';
import { apiErrorMessage, apiFormErrors } from '@/i18n';
import { ApiError } from '@/lib/api';
import { confirmHaptic } from '@/lib/feedback';
import { maskDateInput, MAX_VEHICLE_PHOTOS } from '@/lib/driver';
import type { Vehicle, VehicleInput } from '@/lib/types';
import type { LocalFile } from '@/lib/upload';
import { parseExpiryInput, pendingVehicleCheck } from '@/lib/verification';
import { radius, space, useTheme } from '@/theme';

import { PermissionDenied, pickFile, type PickSource } from './pickFile';
import { CameraDeniedNotice, uploadErrorMessage } from './useDocumentUpload';
import { VEHICLE_ERROR_FIELDS, VehicleFields, useVehicleForm } from './VehicleFields';

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

const isImage = (file: LocalFile) =>
  (file.mimeType ?? '').startsWith('image/') || /\.(jpe?g|png|webp|heic)$/i.test(file.name ?? file.uri);

/**
 * Perfil → Mi moto → "Cambiar de moto" (doc 12): the new moto, its carnet de circulación with the expiry date
 * and fresh photos go to review while the current moto keeps working. While pending, it can be cancelled.
 */
export function VehicleChangeScreen() {
  const { t } = useTranslation();
  const profile = useDriverProfile();
  const header = (
    <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
      <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
    </Row>
  );

  if (profile.isPending) {
    return (
      <Screen header={header}>
        <View style={{ gap: space.md }}>
          <Skeleton height={34} width="60%" />
          <Skeleton height={96} radius={radius.card} />
          <Skeleton height={220} radius={radius.card} />
        </View>
      </Screen>
    );
  }
  const data = profile.data;
  if (data?.pending_vehicle) {
    return (
      <PendingChange
        current={data.vehicle}
        pending={data.pending_vehicle}
        submittedAt={pendingVehicleCheck(data)?.submitted_at ?? null}
        header={header}
        refreshing={profile.isRefetching}
        onRefresh={() => void profile.refetch()}
      />
    );
  }
  return <ChangeForm current={data?.vehicle ?? null} header={header} />;
}

/** A moto summary card: brand and model, year and color, plate. */
function MotoCard({ vehicle, pill, tone }: { vehicle: Vehicle; pill: string; tone: 'success' | 'info' }) {
  return (
    <Card style={styles.moto}>
      <IconTile icon={Bike} tone={tone === 'success' ? 'accent' : 'info'} size={52} />
      <View style={{ flex: 1, gap: 4 }}>
        <Txt variant="subtitle" numberOfLines={2}>
          {vehicle.brand} {vehicle.model}
        </Txt>
        <Txt variant="caption" color="muted" numberOfLines={1}>
          {[vehicle.year, vehicle.color].filter(Boolean).join(' · ')}
        </Txt>
        <StatusPill label={pill} tone={tone} dot />
      </View>
      <PlateBadge plate={vehicle.plate} />
    </Card>
  );
}

function PendingChange({
  current,
  pending,
  submittedAt,
  header,
  refreshing,
  onRefresh,
}: {
  current: Vehicle | null;
  pending: Vehicle;
  submittedAt: string | null;
  header: ReactNode;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const { t, i18n } = useTranslation();
  const cancel = useCancelVehicleChange();
  const sentOn = submittedAt
    ? new Date(submittedAt).toLocaleDateString(i18n.language, { day: 'numeric', month: 'long' })
    : null;

  const confirmCancel = () =>
    Alert.alert(t('verification.vehicle.cancelTitle'), t('verification.vehicle.cancelBody'), [
      { text: t('common.back'), style: 'cancel' },
      {
        text: t('verification.vehicle.cancel'),
        style: 'destructive',
        onPress: () =>
          cancel.mutate(undefined, {
            onSuccess: () => showToast(t('verification.vehicle.cancelled'), 'success'),
            onError: (error) => showToast(apiErrorMessage(error), 'danger'),
          }),
      },
    ]);

  return (
    <Screen
      header={header}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      footer={<Button title={t('verification.vehicle.cancel')} variant="danger" loading={cancel.isPending} onPress={confirmCancel} />}>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={Hourglass} tone="info" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('verification.vehicle.pendingTitle')}
        </Txt>
        <Txt color="muted">
          {sentOn ? t('verification.vehicle.pendingBodyDate', { date: sentOn }) : t('verification.vehicle.pendingBody')}
        </Txt>
      </View>
      {current ? (
        <>
          <Txt variant="overline" color="muted" style={styles.overline}>
            {t('verification.vehicle.current')}
          </Txt>
          <MotoCard vehicle={current} pill={t('verification.vehicle.inUse')} tone="success" />
        </>
      ) : null}
      <Txt variant="overline" color="muted" style={styles.overline}>
        {t('verification.vehicle.new')}
      </Txt>
      <MotoCard vehicle={pending} pill={t('verification.badge.in_review')} tone="info" />
      <Notice tone="info" style={{ marginTop: space.lg }}>
        {t('verification.vehicle.pendingNotice')}
      </Notice>
    </Screen>
  );
}

type Errors = { registration?: string; expiry?: string; photos?: string };

function ChangeForm({ current, header }: { current: Vehicle | null; header: ReactNode }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const profile = useDriverProfile();
  const { config } = useAppConfig();
  const change = useChangeVehicle();
  const form = useVehicleForm(null, config);
  const [registration, setRegistration] = useState<LocalFile | null>(null);
  const [expiry, setExpiry] = useState('');
  const [photos, setPhotos] = useState<LocalFile[]>([]);
  const [sheet, setSheet] = useState<'registration' | 'photo' | null>(null);
  const [errors, setErrors] = useState<Errors>({});
  const [error, setError] = useState<string>();
  const [cameraDenied, setCameraDenied] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const needed = Math.max(1, config.vehicle_photo_min_count);

  async function choose(target: 'registration' | 'photo', source: PickSource) {
    setError(undefined);
    setCameraDenied(false);
    try {
      const file = await pickFile(source);
      if (!file) return;
      if (target === 'registration') {
        setRegistration(file);
        setErrors((e) => ({ ...e, registration: undefined }));
      } else {
        setPhotos((list) => [...list, file].slice(0, MAX_VEHICLE_PHOTOS));
        setErrors((e) => ({ ...e, photos: undefined }));
      }
    } catch (e) {
      if (e instanceof PermissionDenied) setCameraDenied(true);
      else setError(uploadErrorMessage(e, t));
    }
  }

  function options(target: 'registration' | 'photo'): SheetOption[] {
    const list: SheetOption[] = [
      { label: t('driver.documents.takePhoto'), icon: Camera, onPress: () => choose(target, 'camera') },
      { label: t('driver.documents.fromLibrary'), icon: ImageIcon, onPress: () => choose(target, 'library') },
    ];
    if (target === 'registration') {
      list.push({
        label: t('driver.documents.fromFiles'),
        hint: t('driver.documents.fromFilesHint'),
        icon: FileText,
        onPress: () => choose(target, 'pdf'),
      });
    }
    return list;
  }

  async function submit() {
    setError(undefined);
    const vehicle = form.validate();
    const parsed = parseExpiryInput(expiry);
    const next: Errors = {
      registration: registration ? undefined : t('verification.vehicle.registrationMissing'),
      expiry: parsed.error
        ? t(parsed.error === 'past' ? 'verification.expiry.past' : 'verification.expiry.invalid')
        : undefined,
      photos: photos.length >= needed ? undefined : t('verification.vehicle.photosMissing', { count: needed }),
    };
    setErrors(next);
    if (!vehicle || !registration || !parsed.iso || next.photos) return;
    try {
      await change.mutateAsync({
        vehicle,
        registration,
        expiresOn: parsed.iso,
        photos,
        onProgress: (done, total) => setProgress({ done, total }),
      });
      confirmHaptic();
      showToast(t('verification.vehicle.sent'), 'success');
    } catch (e) {
      if (!(e instanceof ApiError)) {
        setError(uploadErrorMessage(e, t));
        return;
      }
      // Someone (another phone) already sent a change: show it.
      if (e.code === 'vehicle_change_pending') void profile.refetch();
      const { fields, message } = apiFormErrors<keyof VehicleInput>(e, VEHICLE_ERROR_FIELDS);
      form.setErrors(fields);
      setError(message ?? fields.type);
    } finally {
      setProgress(null);
    }
  }

  const busy = change.isPending;
  const uploadingLabel = progress
    ? t('verification.selfie.uploading', { done: Math.min(progress.done + 1, progress.total), total: progress.total })
    : undefined;

  return (
    <Screen
      header={header}
      footer={
        <>
          {uploadingLabel ? (
            <Txt variant="caption" color="muted" align="center">
              {uploadingLabel}
            </Txt>
          ) : null}
          <Button title={t('verification.vehicle.submit')} loading={busy} onPress={() => void submit()} />
        </>
      }>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={ArrowLeftRight} tone="accent" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('verification.vehicle.title')}
        </Txt>
        <Txt color="muted">{t('verification.vehicle.subtitle', { year: form.range.min })}</Txt>
      </View>

      {current ? (
        <>
          <Txt variant="overline" color="muted" style={[styles.overline, { marginTop: 0 }]}>
            {t('verification.vehicle.current')}
          </Txt>
          <MotoCard vehicle={current} pill={t('verification.vehicle.inUse')} tone="success" />
        </>
      ) : null}

      <Txt variant="overline" color="muted" style={styles.overline}>
        {t('verification.vehicle.newData')}
      </Txt>
      <VehicleFields form={form} config={config} />

      <Txt variant="overline" color="muted" style={styles.overline}>
        {t('driver.doc.vehicle_registration.title')}
      </Txt>
      <Card style={{ gap: space.md }}>
        <Row>
          {registration && isImage(registration) ? (
            <Image source={{ uri: registration.uri }} style={styles.fileThumb} accessibilityIgnoresInvertColors />
          ) : (
            <IconTile icon={FileText} tone={registration ? 'primary' : errors.registration ? 'danger' : 'neutral'} />
          )}
          <View style={{ flex: 1 }}>
            <Txt variant="bodyStrong" numberOfLines={1}>
              {registration
                ? isImage(registration)
                  ? t('verification.expiry.photoReady')
                  : registration.name || t('verification.expiry.pdfReady')
                : t('verification.vehicle.registrationHint')}
            </Txt>
            {errors.registration ? (
              <Txt variant="caption" color="danger">
                {errors.registration}
              </Txt>
            ) : (
              <Txt variant="caption" color="muted">
                {t('verification.vehicle.registrationSub')}
              </Txt>
            )}
          </View>
          <Button
            title={registration ? t('verification.vehicle.change') : t('driver.documents.upload')}
            size="sm"
            variant={registration ? 'secondary' : 'primary'}
            icon={registration ? RefreshCw : Camera}
            style={{ marginTop: 0 }}
            disabled={busy}
            onPress={() => setSheet('registration')}
          />
        </Row>
        <Field
          label={t('verification.expiry.label')}
          icon={Calendar}
          value={expiry}
          onChangeText={(text) => {
            setExpiry(maskDateInput(text));
            setErrors((e) => ({ ...e, expiry: undefined }));
          }}
          placeholder={t('verification.expiry.placeholder')}
          keyboardType="number-pad"
          maxLength={10}
          error={errors.expiry}
          hint={t('verification.vehicle.expiryHint')}
        />
      </Card>

      <Txt variant="overline" color="muted" style={styles.overline}>
        {t('driver.doc.vehicle_photo.title')}
      </Txt>
      <Card style={{ gap: space.md }}>
        <View>
          <Txt variant="bodyStrong">{t('driver.documents.photosCount', { count: photos.length, required: needed })}</Txt>
          <Txt variant="caption" color={errors.photos ? 'danger' : 'muted'}>
            {errors.photos ?? t('driver.doc.vehicle_photo.hintCount', { count: needed })}
          </Txt>
        </View>
        {photos.length ? (
          <View style={styles.grid}>
            {photos.map((photo, index) => (
              <View key={photo.uri} style={styles.thumbWrap}>
                <Image source={{ uri: photo.uri }} style={styles.thumb} accessibilityIgnoresInvertColors />
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={t('driver.documents.deletePhoto', { n: index + 1 })}
                  hitSlop={8}
                  disabled={busy}
                  onPress={() => setPhotos((list) => list.filter((item) => item !== photo))}
                  style={({ pressed }) => [styles.remove, { backgroundColor: theme.surface, opacity: pressed || busy ? 0.6 : 1 }]}>
                  <X size={14} color={theme.danger} strokeWidth={2.6} />
                </Pressable>
              </View>
            ))}
          </View>
        ) : null}
        {photos.length < MAX_VEHICLE_PHOTOS ? (
          <Button
            title={photos.length ? t('driver.documents.addPhoto') : t('driver.documents.addFirstPhoto')}
            variant="secondary"
            icon={Plus}
            disabled={busy}
            onPress={() => setSheet('photo')}
          />
        ) : null}
      </Card>

      {cameraDenied ? <CameraDeniedNotice style={{ marginTop: space.md }} /> : null}
      <View style={{ marginTop: space.md }}>
        <ErrorText>{error}</ErrorText>
      </View>
      <Notice tone="info" style={{ marginTop: space.xs }}>
        {t('verification.vehicle.how')}
      </Notice>

      <Sheet
        visible={!!sheet}
        title={sheet === 'registration' ? t('driver.doc.vehicle_registration.title') : t('driver.doc.vehicle_photo.title')}
        subtitle={sheet === 'registration' ? t('verification.vehicle.registrationSub') : t('driver.doc.vehicle_photo.hint')}
        options={sheet ? options(sheet) : []}
        onClose={() => setSheet(null)}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  overline: { marginTop: space.xl, marginBottom: space.xs },
  moto: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  fileThumb: { width: 44, height: 44, borderRadius: radius.field },
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
