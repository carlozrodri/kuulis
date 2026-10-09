import { useTranslation } from "react-i18next";
import { Linking, Pressable, StyleSheet, View } from "react-native";

import {
  Backpack,
  Banknote,
  Bug,
  CircleEllipsis,
  Gauge,
  type Icon,
  MessageCircleWarning,
  PhoneCall,
  ScanFace,
  ShieldAlert,
  Siren,
  UserX,
} from "@/components/icons";
import {
  Button,
  IconTile,
  Skeleton,
  StatusPill,
  type Tone,
  Txt,
} from "@/components/ui";
import { Avatar, PlaceRows } from "@/features/ride/components";
import { heavyHaptic } from "@/lib/feedback";
import { isUrgentCategory } from "@/lib/reports";
import { rideRole } from "@/lib/ride";
import type { ReportCategory, ReportStatus, Ride } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";
import { useMode } from "@/providers/ModeProvider";
import { radius, space, useTheme } from "@/theme";

export const CATEGORY_ICONS: Record<ReportCategory, Icon> = {
  safety: ShieldAlert,
  harassment: MessageCircleWarning,
  driving: Gauge,
  fare: Banknote,
  vehicle_mismatch: ScanFace,
  no_show: UserX,
  lost_item: Backpack,
  app_issue: Bug,
  other: CircleEllipsis,
};

export const REPORT_STATUS_TONE: Record<ReportStatus, Tone> = {
  open: "info",
  in_review: "warning",
  resolved: "success",
  dismissed: "neutral",
};

export function ReportStatusPill({ status }: { status: ReportStatus }) {
  const { t } = useTranslation();
  return (
    <StatusPill
      label={t(`reports.status.${status}`)}
      tone={REPORT_STATUS_TONE[status] ?? "neutral"}
      dot
    />
  );
}

export const callEmergency = () => {
  heavyHaptic();
  void Linking.openURL("tel:911").catch(() => undefined);
};

/** Large tappable card with an icon and a one-line explanation. Safety and harassment are drawn in red. */
export function CategoryCard({
  category,
  selected,
  onPress,
}: {
  category: ReportCategory;
  selected: boolean;
  onPress: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const urgent = isUrgentCategory(category);
  const title = t(`report.category.${category}.title`);
  const body = t(`report.category.${category}.body`);
  const accent = urgent ? theme.danger : theme.primary;
  const background = selected
    ? urgent
      ? theme.dangerSoft
      : theme.surfaceAlt
    : theme.surface;

  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected, checked: selected }}
      accessibilityLabel={`${title}. ${body}`}
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        {
          backgroundColor: background,
          borderColor: selected
            ? accent
            : urgent
              ? theme.dangerSoft
              : "transparent",
          transform: [{ scale: pressed ? 0.985 : 1 }],
        },
      ]}
    >
      <IconTile
        icon={CATEGORY_ICONS[category]}
        tone={urgent ? "danger" : "primary"}
        size={48}
      />
      <View style={{ flex: 1, gap: 2 }}>
        <View style={styles.titleRow}>
          <Txt
            variant="bodyStrong"
            style={[{ flexShrink: 1 }, urgent && { color: theme.danger }]}
          >
            {title}
          </Txt>
          {urgent ? (
            <StatusPill label={t("report.urgentPill")} tone="danger" />
          ) : null}
        </View>
        <Txt variant="caption" color="muted">
          {body}
        </Txt>
      </View>
      <View
        style={[
          styles.radio,
          { borderColor: selected ? accent : theme.border },
        ]}
      >
        {selected ? (
          <View style={[styles.radioDot, { backgroundColor: accent }]} />
        ) : null}
      </View>
    </Pressable>
  );
}

/** "Lo tratamos como urgente… si estás en peligro, llama al 911" with a call button. */
export function UrgentNote({ compact }: { compact?: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <View
      accessibilityRole="alert"
      style={[styles.urgent, { backgroundColor: theme.dangerSoft }]}
    >
      <View style={styles.titleRow}>
        <Siren size={20} color={theme.danger} strokeWidth={2.2} />
        <Txt variant="bodyStrong" style={{ color: theme.danger, flex: 1 }}>
          {t("report.urgent.title")}
        </Txt>
      </View>
      {!compact ? (
        <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
          {t("report.urgent.body")}
        </Txt>
      ) : null}
      <Button
        title={t("report.urgent.call")}
        variant="danger"
        size="sm"
        icon={PhoneCall}
        style={{ alignSelf: "flex-start", backgroundColor: theme.surface }}
        onPress={callEmergency}
      />
    </View>
  );
}

/** Which ride the report is about: date, pickup → dropoff and the other person. */
export function RideContextCard({ ride }: { ride: Ride | undefined }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const { user } = useAuth();
  const { mode } = useMode();

  if (!ride) {
    return (
      <View style={[styles.ride, { backgroundColor: theme.surface }]}>
        <Skeleton height={16} width="50%" />
        <Skeleton height={44} />
      </View>
    );
  }

  const role = rideRole(ride, user?.id, mode ?? "passenger");
  const other = role === "passenger" ? ride.driver : ride.passenger;
  const date = new Date(ride.requested_at);
  return (
    <View style={[styles.ride, { backgroundColor: theme.surface }]}>
      <Txt variant="overline" color="muted">
        {t("report.aboutRide")}
      </Txt>
      <Txt variant="bodyStrong">
        {t("report.rideDate", {
          date: date.toLocaleDateString(i18n.language, {
            weekday: "long",
            day: "numeric",
            month: "long",
          }),
          time: date.toLocaleTimeString(i18n.language, {
            hour: "numeric",
            minute: "2-digit",
          }),
        })}
      </Txt>
      <PlaceRows pickup={ride.pickup} dropoff={ride.dropoff} compact />
      {other ? (
        <View style={[styles.person, { borderTopColor: theme.divider }]}>
          <Avatar
            name={other.first_name}
            photoUrl={role === "passenger" ? ride.driver?.photo_url : null}
            size={32}
          />
          <Txt variant="label" style={{ flex: 1 }}>
            {role === "passenger"
              ? t("report.yourDriver", { name: other.first_name })
              : t("report.yourPassenger", { name: other.first_name })}
          </Txt>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    borderRadius: radius.card,
    borderWidth: 1.5,
    padding: space.md,
    minHeight: 76,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.xs,
    flexWrap: "wrap",
  },
  radio: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
  },
  radioDot: { width: 12, height: 12, borderRadius: 6 },
  urgent: { borderRadius: radius.tile, padding: 14, gap: space.xs },
  ride: { borderRadius: radius.card, padding: space.md, gap: space.xs },
  person: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    borderTopWidth: 1,
    paddingTop: space.sm,
    marginTop: space.xxs,
  },
});
