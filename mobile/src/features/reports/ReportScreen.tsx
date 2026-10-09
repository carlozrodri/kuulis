import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { BackHandler, StyleSheet, TextInput, View } from "react-native";

import { ChevronLeft, CircleCheck, Flag, X } from "@/components/icons";
import {
  Button,
  IconButton,
  Notice,
  ProgressSteps,
  Row,
  Screen,
  Txt,
} from "@/components/ui";
import { useCreateReport } from "@/hooks/useReports";
import { useRide } from "@/hooks/useRides";
import { apiErrorMessage } from "@/i18n";
import { ApiError } from "@/lib/api";
import { confirmHaptic, selectionHaptic } from "@/lib/feedback";
import {
  DESCRIPTION_MAX,
  DESCRIPTION_MIN,
  descriptionLength,
  descriptionProblem,
  existingReportId,
  GENERAL_REPORT_CATEGORIES,
  isReportCategory,
  isUrgentCategory,
  reportCategoriesFor,
} from "@/lib/reports";
import type { Report, ReportCategory } from "@/lib/types";
import { fonts, radius, space, useTheme } from "@/theme";

import {
  CATEGORY_ICONS,
  CategoryCard,
  RideContextCard,
  UrgentNote,
} from "./components";

type Step = "category" | "details" | "sent";

type SubmitError =
  | { kind: "already_open"; reportId: string | null }
  | { kind: "too_many"; message: string }
  | { kind: "ride"; message: string }
  | { kind: "other"; message: string };

/** Leaves the flow: back where it was opened from, else "Mis reportes". */
function leave() {
  if (router.canGoBack()) router.back();
  else router.replace("/reports");
}

/**
 * "Reportar un problema": pick a category (all of them about a ride, only general ones otherwise), describe
 * what happened, and send (POST /reports). Safety and harassment point to 911.
 */
export function ReportScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const params = useLocalSearchParams<{
    ride_id?: string;
    category?: string;
  }>();
  const [rideId, setRideId] = useState<string | undefined>(
    params.ride_id || undefined,
  );
  const ride = useRide(rideId);
  const create = useCreateReport();

  const categories = reportCategoriesFor(!!rideId);
  const initial =
    isReportCategory(params.category) && categories.includes(params.category)
      ? params.category
      : null;
  const [step, setStep] = useState<Step>("category");
  const [category, setCategory] = useState<ReportCategory | null>(initial);
  const [description, setDescription] = useState("");
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<SubmitError | null>(null);
  const [sent, setSent] = useState<Report | null>(null);

  // A ride that never had a driver cannot be reported (409 ride_without_driver).
  const noDriver = !!rideId && !!ride.data && !ride.data.driver;

  const back = useCallback(() => {
    if (step === "details") {
      setStep("category");
      setError(null);
    } else leave();
  }, [step]);

  // Android back: from the description to the categories.
  useFocusEffect(
    useCallback(() => {
      const sub = BackHandler.addEventListener("hardwareBackPress", () => {
        if (step !== "details") return false;
        back();
        return true;
      });
      return () => sub.remove();
    }, [step, back]),
  );

  const choose = (value: ReportCategory) => {
    selectionHaptic();
    setCategory(value);
    setError(null);
  };

  /** Drops the ride (not a participant, no driver): only the general categories remain. */
  const makeGeneral = () => {
    setRideId(undefined);
    setError(null);
    if (!category || !GENERAL_REPORT_CATEGORIES.includes(category)) {
      setCategory(null);
      setStep("category");
    }
  };

  const problem = descriptionProblem(description);
  const length = descriptionLength(description);

  const submit = () => {
    setTouched(true);
    if (!category || problem) return;
    setError(null);
    create.mutate(
      {
        category,
        description: description.trim(),
        ...(rideId ? { ride_id: rideId } : {}),
      },
      {
        onSuccess: (report) => {
          confirmHaptic();
          setSent(report);
          setStep("sent");
        },
        onError: (e) => {
          const code = e instanceof ApiError ? e.code : null;
          if (code === "report_already_open")
            setError({ kind: "already_open", reportId: existingReportId(e) });
          else if (code === "too_many_open_reports")
            setError({ kind: "too_many", message: apiErrorMessage(e) });
          else if (
            code === "not_ride_participant" ||
            code === "ride_without_driver"
          )
            setError({ kind: "ride", message: apiErrorMessage(e) });
          else setError({ kind: "other", message: apiErrorMessage(e) });
        },
      },
    );
  };

  if (step === "sent") {
    const urgent = isUrgentCategory(sent?.category ?? category);
    return (
      <Screen
        footer={
          <>
            {sent?.id ? (
              <Button
                title={t("report.viewReport")}
                onPress={() =>
                  router.replace({
                    pathname: "/reports/[id]",
                    params: { id: sent.id },
                  })
                }
              />
            ) : null}
            <Button
              title={t("common.done")}
              variant={sent?.id ? "ghost" : "primary"}
              onPress={leave}
            />
          </>
        }
      >
        <View style={styles.sent}>
          <View
            style={[styles.sentHalo, { backgroundColor: theme.surfaceAlt }]}
          >
            <View style={[styles.sentIcon, { backgroundColor: theme.primary }]}>
              <CircleCheck
                size={40}
                color={theme.onPrimary}
                strokeWidth={2.2}
              />
            </View>
          </View>
          <Txt variant="title" align="center" accessibilityRole="header">
            {t("report.sentTitle")}
          </Txt>
          <Txt color="muted" align="center">
            {urgent ? t("report.sentBodyUrgent") : t("report.sentBody")}
          </Txt>
          {urgent ? (
            <View style={{ alignSelf: "stretch", marginTop: space.sm }}>
              <UrgentNote compact />
            </View>
          ) : null}
        </View>
      </Screen>
    );
  }

  const rideDate = ride.data
    ? new Date(ride.data.requested_at).toLocaleDateString(i18n.language, {
        day: "numeric",
        month: "long",
      })
    : null;

  const header = (
    <View style={styles.header}>
      <Row style={{ justifyContent: "space-between" }}>
        <IconButton
          icon={step === "details" ? ChevronLeft : X}
          label={step === "details" ? t("common.back") : t("common.close")}
          onPress={back}
        />
        <Txt variant="label" color="muted">
          {t("report.title")}
        </Txt>
        <View style={{ width: 44 }} />
      </Row>
      <ProgressSteps
        total={2}
        current={step === "category" ? 1 : 2}
        label={t("report.step", {
          current: step === "category" ? 1 : 2,
          total: 2,
        })}
      />
    </View>
  );

  if (step === "category") {
    const urgentCategories = categories.filter(isUrgentCategory);
    const otherCategories = categories.filter((c) => !isUrgentCategory(c));
    return (
      <Screen
        header={header}
        footer={
          <Button
            title={t("common.continue")}
            disabled={!category || noDriver}
            onPress={() => {
              setStep("details");
              setTouched(false);
            }}
          />
        }
      >
        <View style={{ gap: space.xxs, marginBottom: space.md }}>
          <Txt variant="title" accessibilityRole="header">
            {t("report.categoryTitle")}
          </Txt>
          <Txt color="muted">
            {rideId
              ? rideDate
                ? t("report.categorySubtitleRide", { date: rideDate })
                : " "
              : t("report.categorySubtitleGeneral")}
          </Txt>
        </View>

        {noDriver ? (
          <Notice tone="warning" style={{ marginBottom: space.md }}>
            <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
              {t("report.noDriver")}
            </Txt>
            <Button
              title={t("report.rideProblem.general")}
              variant="secondary"
              size="sm"
              style={{ alignSelf: "flex-start" }}
              onPress={makeGeneral}
            />
          </Notice>
        ) : null}

        <View accessibilityRole="radiogroup" style={{ gap: space.sm }}>
          {urgentCategories.length ? (
            <>
              <Txt variant="overline" color="muted">
                {t("report.groupSafety")}
              </Txt>
              {urgentCategories.map((c) => (
                <CategoryCard
                  key={c}
                  category={c}
                  selected={category === c}
                  onPress={() => choose(c)}
                />
              ))}
              {isUrgentCategory(category) ? <UrgentNote /> : null}
              <Txt
                variant="overline"
                color="muted"
                style={{ marginTop: space.sm }}
              >
                {t("report.groupOther")}
              </Txt>
            </>
          ) : null}
          {otherCategories.map((c) => (
            <CategoryCard
              key={c}
              category={c}
              selected={category === c}
              onPress={() => choose(c)}
            />
          ))}
        </View>
      </Screen>
    );
  }

  // ── Step 2: description ──
  const CategoryIcon = category ? CATEGORY_ICONS[category] : Flag;
  const urgent = isUrgentCategory(category);
  const showProblem = touched && problem;
  const counterColor =
    length > DESCRIPTION_MAX
      ? theme.danger
      : length >= DESCRIPTION_MIN
        ? theme.muted
        : theme.warning;

  return (
    <Screen
      header={header}
      footer={
        <Button
          title={t("report.submit")}
          icon={Flag}
          loading={create.isPending}
          disabled={!category || (touched && !!problem)}
          onPress={submit}
        />
      }
    >
      <View style={{ gap: space.xxs, marginBottom: space.md }}>
        <Txt variant="title" accessibilityRole="header">
          {t("report.detailsTitle")}
        </Txt>
        <Txt color="muted">{t("report.detailsSubtitle")}</Txt>
      </View>

      <View style={{ gap: space.sm }}>
        <View
          style={[
            styles.chosen,
            { backgroundColor: urgent ? theme.dangerSoft : theme.surfaceAlt },
          ]}
        >
          <CategoryIcon
            size={20}
            color={urgent ? theme.danger : theme.primary}
            strokeWidth={2.2}
          />
          <Txt
            variant="bodyStrong"
            style={{ flex: 1, color: urgent ? theme.danger : theme.text }}
          >
            {category ? t(`report.category.${category}.title`) : ""}
          </Txt>
          <Button
            title={t("report.change")}
            variant="ghost"
            size="sm"
            accessibilityLabel={t("report.changeCategory")}
            style={{ marginTop: 0 }}
            onPress={back}
          />
        </View>

        {urgent ? <UrgentNote /> : null}

        {rideId ? <RideContextCard ride={ride.data} /> : null}

        {error ? (
          <SubmitErrorNotice error={error} onGeneral={makeGeneral} />
        ) : null}

        <View>
          <Txt variant="label" color="muted" style={{ marginBottom: 6 }}>
            {t("report.descriptionLabel")}
          </Txt>
          <TextInput
            accessibilityLabel={t("report.descriptionLabel")}
            accessibilityHint={t("report.minHint", { min: DESCRIPTION_MIN })}
            value={description}
            onChangeText={(text) => {
              setDescription(text);
              if (error?.kind === "other") setError(null);
            }}
            onBlur={() => setTouched(description.length > 0)}
            placeholder={category ? t(`report.placeholder.${category}`) : ""}
            placeholderTextColor={theme.muted}
            selectionColor={theme.primary}
            cursorColor={theme.primary}
            multiline
            maxLength={DESCRIPTION_MAX + 50}
            maxFontSizeMultiplier={1.6}
            textAlignVertical="top"
            style={[
              styles.textarea,
              {
                color: theme.text,
                backgroundColor: theme.surface,
                borderColor: showProblem ? theme.danger : theme.border,
              },
            ]}
          />
          <View style={styles.counterRow}>
            <Txt
              variant="caption"
              style={{
                flex: 1,
                color: showProblem ? theme.danger : theme.muted,
              }}
            >
              {problem === "too_long"
                ? t("report.tooLong", { max: DESCRIPTION_MAX })
                : problem === "too_short"
                  ? t("report.minHint", { min: DESCRIPTION_MIN })
                  : ""}
            </Txt>
            <View
              accessible
              accessibilityLabel={t("report.counterA11y", {
                count: length,
                max: DESCRIPTION_MAX,
              })}
            >
              <Txt variant="caption" tabular style={{ color: counterColor }}>
                {t("report.counter", { count: length, max: DESCRIPTION_MAX })}
              </Txt>
            </View>
          </View>
        </View>
      </View>
    </Screen>
  );
}

function SubmitErrorNotice({
  error,
  onGeneral,
}: {
  error: SubmitError;
  onGeneral: () => void;
}) {
  const { t } = useTranslation();
  if (error.kind === "already_open") {
    return (
      <Notice tone="info" title={t("report.alreadyOpen.title")}>
        <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
          {t("report.alreadyOpen.body")}
        </Txt>
        <Button
          title={
            error.reportId
              ? t("report.alreadyOpen.open")
              : t("report.tooMany.action")
          }
          variant="secondary"
          size="sm"
          style={{ alignSelf: "flex-start" }}
          onPress={() =>
            error.reportId
              ? router.replace({
                  pathname: "/reports/[id]",
                  params: { id: error.reportId },
                })
              : router.replace("/reports")
          }
        />
      </Notice>
    );
  }
  if (error.kind === "too_many") {
    return (
      <Notice tone="warning" title={t("report.tooMany.title")}>
        <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
          {error.message}
        </Txt>
        <Button
          title={t("report.tooMany.action")}
          variant="secondary"
          size="sm"
          style={{ alignSelf: "flex-start" }}
          onPress={() => router.replace("/reports")}
        />
      </Notice>
    );
  }
  if (error.kind === "ride") {
    return (
      <Notice tone="warning" title={t("report.rideProblem.title")}>
        <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
          {error.message}
        </Txt>
        <Button
          title={t("report.rideProblem.general")}
          variant="secondary"
          size="sm"
          style={{ alignSelf: "flex-start" }}
          onPress={onGeneral}
        />
      </Notice>
    );
  }
  return <Notice tone="danger">{error.message}</Notice>;
}

const styles = StyleSheet.create({
  header: { gap: space.md, paddingTop: space.xs, paddingBottom: space.md },
  chosen: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    borderRadius: radius.tile,
    paddingLeft: space.md,
    paddingRight: space.xxs,
    minHeight: 52,
  },
  textarea: {
    minHeight: 160,
    maxHeight: 280,
    borderWidth: 1.5,
    borderRadius: radius.field,
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 12,
    fontFamily: fonts.medium,
    fontSize: 16,
    lineHeight: 22,
  },
  counterRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: space.sm,
    marginTop: 6,
  },
  sent: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: space.sm,
    paddingVertical: space.xxl,
  },
  sentHalo: {
    width: 112,
    height: 112,
    borderRadius: 56,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.sm,
  },
  sentIcon: {
    width: 76,
    height: 76,
    borderRadius: 38,
    alignItems: "center",
    justifyContent: "center",
  },
});
