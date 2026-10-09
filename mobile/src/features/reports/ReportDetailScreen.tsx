import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { RefreshControl, StyleSheet, View } from "react-native";

import { Check, CircleX, MessageCircle } from "@/components/icons";
import {
  Button,
  EmptyState,
  IconTile,
  Screen,
  Skeleton,
  StatusPill,
  Txt,
} from "@/components/ui";
import { FlowHeader } from "@/features/wallet/components";
import { useReport } from "@/hooks/useReports";
import { useRide } from "@/hooks/useRides";
import { apiErrorMessage } from "@/i18n";
import {
  isOpenReport,
  isUrgentCategory,
  reportTimeline,
  type TimelineStep,
} from "@/lib/reports";
import type { Report } from "@/lib/types";
import { radius, space, useTheme } from "@/theme";

import {
  CATEGORY_ICONS,
  ReportStatusPill,
  RideContextCard,
  UrgentNote,
} from "./components";

function leave() {
  if (router.canGoBack()) router.back();
  else router.replace("/reports");
}

/** One report: what was sent, its status timeline and the team's answer. */
export function ReportDetailScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const report = useReport(id);
  const ride = useRide(report.data?.ride_id ?? undefined);
  const data = report.data;

  const formatDateTime = (value: string) =>
    new Date(value).toLocaleString(i18n.language, {
      day: "numeric",
      month: "long",
      hour: "numeric",
      minute: "2-digit",
    });

  const refresh = (
    <RefreshControl
      refreshing={report.isRefetching}
      onRefresh={() => void report.refetch()}
      tintColor={theme.primary}
    />
  );

  if (!data) {
    return (
      <Screen
        refreshControl={refresh}
        header={<FlowHeader title={t("reports.detailTitle")} onBack={leave} />}
      >
        {report.isError ? (
          <View>
            <EmptyState
              icon={CircleX}
              title={t("common.error")}
              body={apiErrorMessage(report.error)}
            />
            <Button
              title={t("common.retry")}
              variant="secondary"
              onPress={() => void report.refetch()}
            />
          </View>
        ) : (
          <View style={{ gap: space.sm }}>
            <Skeleton height={72} radius={radius.card} />
            <Skeleton height={120} radius={radius.card} />
            <Skeleton height={160} radius={radius.card} />
          </View>
        )}
      </Screen>
    );
  }

  const urgent = isUrgentCategory(data.category);
  const closed = !isOpenReport(data.status);

  return (
    <Screen
      refreshControl={refresh}
      header={<FlowHeader title={t("reports.detailTitle")} onBack={leave} />}
    >
      <View style={{ gap: space.md }}>
        <View style={[styles.summary, { backgroundColor: theme.surface }]}>
          <IconTile
            icon={CATEGORY_ICONS[data.category]}
            tone={urgent ? "danger" : "primary"}
            size={52}
          />
          <View style={{ flex: 1, gap: 4 }}>
            <Txt variant="subtitle">
              {t(`report.category.${data.category}.title`)}
            </Txt>
            <Txt variant="caption" color="muted">
              {t("reports.sentOn", { date: formatDateTime(data.created_at) })}
            </Txt>
            <View style={styles.pills}>
              <ReportStatusPill status={data.status} />
              {data.priority === "urgent" && !closed ? (
                <StatusPill label={t("reports.priority")} tone="danger" />
              ) : null}
            </View>
          </View>
        </View>

        {closed ? <Resolution report={data} /> : null}

        <View style={[styles.card, { backgroundColor: theme.surface }]}>
          <Txt variant="overline" color="muted">
            {t("reports.progress")}
          </Txt>
          <Timeline
            steps={reportTimeline(data)}
            urgent={data.priority === "urgent"}
            formatDate={formatDateTime}
          />
        </View>

        <View style={[styles.card, { backgroundColor: theme.surface }]}>
          <Txt variant="overline" color="muted">
            {t("reports.youWrote")}
          </Txt>
          <Txt>{data.description}</Txt>
        </View>

        {data.ride_id ? (
          ride.isError ? null : (
            <RideContextCard ride={ride.data} />
          )
        ) : null}

        {urgent && !closed ? <UrgentNote /> : null}
      </View>
    </Screen>
  );
}

/** The team's answer once the report is resolved or dismissed. */
function Resolution({ report }: { report: Report }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const resolved = report.status === "resolved";
  return (
    <View
      accessibilityRole="summary"
      style={[
        styles.card,
        {
          backgroundColor: resolved ? theme.successSoft : theme.surfaceAlt,
        },
      ]}
    >
      <View style={styles.resolutionTitle}>
        <MessageCircle
          size={18}
          color={resolved ? theme.success : theme.muted}
          strokeWidth={2.2}
        />
        <Txt
          variant="bodyStrong"
          style={{ color: resolved ? theme.success : theme.text, flex: 1 }}
        >
          {t("reports.resolution")}
        </Txt>
      </View>
      <Txt>{report.resolution?.trim() || t("reports.noResolution")}</Txt>
    </View>
  );
}

function Timeline({
  steps,
  urgent,
  formatDate,
}: {
  steps: TimelineStep[];
  urgent: boolean;
  formatDate: (value: string) => string;
}) {
  const { t } = useTranslation();
  const theme = useTheme();

  const detail = (step: TimelineStep) => {
    if (step.at) return formatDate(step.at);
    if (step.key === "in_review") {
      if (step.state === "current") return t("reports.timeline.reviewing");
      if (step.state === "upcoming")
        return urgent
          ? t("reports.timeline.waitingUrgent")
          : t("reports.timeline.waiting");
    }
    if (step.state === "upcoming") return t("reports.timeline.pending");
    return null;
  };

  return (
    <View>
      {steps.map((step, index) => {
        const last = index === steps.length - 1;
        const done = step.state === "done";
        const current = step.state === "current";
        const label = t(`reports.timeline.${step.key}`);
        const text = detail(step);
        const dotColor = done
          ? theme.primary
          : current
            ? theme.warning
            : theme.border;
        return (
          <View
            key={step.key}
            style={styles.step}
            accessible
            accessibilityLabel={`${t("reports.timeline.stepA11y", {
              label,
              state: t(`reports.timeline.state.${step.state}`),
            })}${text ? `. ${text}` : ""}`}
          >
            <View style={styles.rail}>
              <View
                style={[
                  styles.dot,
                  {
                    backgroundColor: done ? dotColor : theme.surface,
                    borderColor: dotColor,
                  },
                ]}
              >
                {done ? (
                  <Check size={14} color={theme.onPrimary} strokeWidth={3} />
                ) : current ? (
                  <View
                    style={[styles.innerDot, { backgroundColor: dotColor }]}
                  />
                ) : null}
              </View>
              {!last ? (
                <View
                  style={[
                    styles.line,
                    {
                      backgroundColor:
                        steps[index + 1]?.state === "upcoming"
                          ? theme.border
                          : theme.primary,
                    },
                  ]}
                />
              ) : null}
            </View>
            <View
              style={[styles.stepBody, !last && { paddingBottom: space.md }]}
            >
              <Txt
                variant="bodyStrong"
                color={step.state === "upcoming" ? "muted" : "text"}
              >
                {label}
              </Txt>
              {text ? (
                <Txt variant="caption" color="muted">
                  {text}
                </Txt>
              ) : null}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  summary: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    borderRadius: radius.card,
    padding: space.md,
  },
  pills: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 2 },
  card: { borderRadius: radius.card, padding: space.md, gap: space.sm },
  resolutionTitle: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.xs,
  },
  step: { flexDirection: "row", gap: space.sm },
  rail: { alignItems: "center", width: 24 },
  dot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
  },
  innerDot: { width: 10, height: 10, borderRadius: 5 },
  line: { width: 2, flex: 1, marginVertical: 2, borderRadius: 1 },
  stepBody: { flex: 1, gap: 2, paddingTop: 1 },
});
