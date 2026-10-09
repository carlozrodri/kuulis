import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  ChevronRight,
  CircleX,
  Flag,
  PhoneCall,
  Route,
} from "@/components/icons";
import {
  Button,
  Card,
  EmptyState,
  IconTile,
  ListRow,
  Skeleton,
  Txt,
} from "@/components/ui";
import { FlowHeader } from "@/features/wallet/components";
import { useMyReports } from "@/hooks/useReports";
import { apiErrorMessage } from "@/i18n";
import { isUrgentCategory } from "@/lib/reports";
import type { Report } from "@/lib/types";
import { radius, space, useTheme } from "@/theme";

import { CATEGORY_ICONS, callEmergency, ReportStatusPill } from "./components";

/** Leaves to where it was opened from (profile, suspension panel), else home. */
function leave() {
  if (router.canGoBack()) router.back();
  else router.replace("/");
}

/** "Ayuda y reportes": report a problem, 911, and "Mis reportes" with their status. */
export function ReportsScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const reports = useMyReports();
  const items = reports.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: theme.background,
        paddingTop: insets.top,
      }}
    >
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <ReportRow report={item} />}
        contentContainerStyle={{
          paddingHorizontal: space.lg,
          paddingBottom: Math.max(insets.bottom, space.md) + space.md,
          gap: space.sm,
          flexGrow: 1,
        }}
        refreshControl={
          <RefreshControl
            refreshing={reports.isRefetching && !reports.isFetchingNextPage}
            onRefresh={() => void reports.refetch()}
            tintColor={theme.primary}
          />
        }
        onEndReachedThreshold={0.4}
        onEndReached={() => {
          if (reports.hasNextPage && !reports.isFetchingNextPage)
            void reports.fetchNextPage();
        }}
        ListHeaderComponent={
          <View style={{ gap: space.sm, paddingBottom: space.xs }}>
            <FlowHeader
              title={t("reports.title")}
              subtitle={t("reports.subtitle")}
              onBack={leave}
            />
            <Card
              tone="tint"
              onPress={() => router.push("/report")}
              accessibilityLabel={t("reports.new")}
              accessibilityHint={t("reports.newHint")}
              style={styles.newCard}
            >
              <IconTile icon={Flag} tone="primary" size={48} />
              <View style={{ flex: 1, gap: 2 }}>
                <Txt variant="subtitle">{t("reports.new")}</Txt>
                <Txt variant="caption" color="muted">
                  {t("reports.newHint")}
                </Txt>
              </View>
              <ChevronRight size={20} color={theme.muted} strokeWidth={2.2} />
            </Card>
            <View style={[styles.hint, { backgroundColor: theme.surface }]}>
              <Route size={18} color={theme.muted} strokeWidth={2.2} />
              <Txt variant="caption" color="muted" style={{ flex: 1 }}>
                {t("reports.rideHint")}
              </Txt>
            </View>
            <Card style={{ paddingVertical: space.xxs }}>
              <ListRow
                icon={PhoneCall}
                iconTone="danger"
                title={t("reports.emergency")}
                subtitle={t("reports.emergencyHint")}
                onPress={callEmergency}
              />
            </Card>
            <Txt
              variant="overline"
              color="muted"
              style={{ marginTop: space.md }}
            >
              {t("reports.mine")}
            </Txt>
          </View>
        }
        ListFooterComponent={
          reports.isFetchingNextPage ? (
            <ActivityIndicator
              color={theme.primary}
              style={{ margin: space.md }}
            />
          ) : null
        }
        ListEmptyComponent={
          reports.isPending ? (
            <View style={{ gap: space.sm }}>
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} height={76} radius={radius.card} />
              ))}
            </View>
          ) : reports.isError ? (
            <View>
              <EmptyState
                icon={CircleX}
                title={t("common.error")}
                body={apiErrorMessage(reports.error)}
              />
              <Button
                title={t("common.retry")}
                variant="secondary"
                onPress={() => void reports.refetch()}
              />
            </View>
          ) : (
            <EmptyState
              icon={Flag}
              title={t("reports.empty")}
              body={t("reports.emptyBody")}
            />
          )
        }
      />
    </View>
  );
}

function ReportRow({ report }: { report: Report }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const urgent = isUrgentCategory(report.category);
  const category = t(`report.category.${report.category}.title`);
  const status = t(`reports.status.${report.status}`);
  const date = new Date(report.created_at).toLocaleDateString(i18n.language, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t("reports.itemA11y", { category, status, date })}
      onPress={() =>
        router.push({ pathname: "/reports/[id]", params: { id: report.id } })
      }
      style={({ pressed }) => [
        styles.row,
        {
          backgroundColor: theme.surface,
          transform: [{ scale: pressed ? 0.985 : 1 }],
          opacity: pressed ? 0.94 : 1,
        },
      ]}
    >
      <IconTile
        icon={CATEGORY_ICONS[report.category]}
        tone={urgent ? "danger" : "primary"}
        size={44}
      />
      <View style={{ flex: 1, gap: 4 }}>
        <Txt variant="bodyStrong" numberOfLines={1}>
          {category}
        </Txt>
        <Txt variant="caption" color="muted" numberOfLines={1}>
          {date} ·{" "}
          {report.ride_id ? t("reports.aboutRide") : t("reports.general")}
        </Txt>
        <ReportStatusPill status={report.status} />
      </View>
      <ChevronRight size={20} color={theme.muted} strokeWidth={2.2} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  newCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    padding: space.md,
  },
  hint: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    borderRadius: radius.tile,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    borderRadius: radius.card,
    padding: space.md,
  },
});
