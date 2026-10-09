import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { StyleSheet, View } from "react-native";

import { CalendarClock, LifeBuoy, LockKeyhole } from "@/components/icons";
import { Button, Txt } from "@/components/ui";
import { suspensionEnd } from "@/lib/suspension";
import type { Suspension } from "@/lib/types";
import { radius, space, useTheme } from "@/theme";

/** "Hasta el 12 de octubre, 3:00 p. m.", "Hoy a las 6:00 p. m." or "Indefinida". */
export function useSuspensionUntil() {
  const { t, i18n } = useTranslation();
  return (suspension: Pick<Suspension, "until">) => {
    const end = suspensionEnd(suspension);
    if (end.kind === "indefinite") return t("suspension.indefinite");
    const time = end.date.toLocaleTimeString(i18n.language, {
      hour: "numeric",
      minute: "2-digit",
    });
    if (end.sameDay) return t("suspension.todayAt", { time });
    const date = end.date.toLocaleDateString(i18n.language, {
      day: "numeric",
      month: "long",
      ...(end.date.getFullYear() !== new Date().getFullYear()
        ? { year: "numeric" as const }
        : {}),
    });
    return `${date}, ${time}`;
  };
}

/**
 * Replaces the request-ride UI (passenger, calm) or the go-online button (driver, red) while the account is
 * suspended: why, until when, and a way to reach the team.
 */
export function SuspendedPanel({
  suspension,
  variant,
}: {
  suspension: Suspension;
  variant: "passenger" | "driver";
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const untilText = useSuspensionUntil();
  const driver = variant === "driver";
  const fg = driver ? theme.danger : theme.text;
  const indefinite = !suspension.until;

  return (
    <View style={{ gap: space.sm }}>
      <View
        accessibilityRole="alert"
        style={[
          styles.panel,
          { backgroundColor: driver ? theme.dangerSoft : theme.background },
        ]}
      >
        <View style={styles.titleRow}>
          <View
            style={[
              styles.icon,
              { backgroundColor: driver ? theme.surface : theme.surfaceAlt },
            ]}
          >
            <LockKeyhole
              size={22}
              color={driver ? theme.danger : theme.primary}
              strokeWidth={2.2}
            />
          </View>
          <Txt
            variant="heading"
            style={{ color: fg, flex: 1 }}
            accessibilityRole="header"
          >
            {t("suspension.title")}
          </Txt>
        </View>
        <Txt>
          {driver ? t("suspension.driverBody") : t("suspension.passengerBody")}
        </Txt>

        <View style={[styles.facts, { backgroundColor: theme.surface }]}>
          {suspension.reason ? (
            <View
              style={[styles.fact, { borderBottomColor: theme.divider }]}
              accessible
              accessibilityLabel={`${t("suspension.reason")}: ${suspension.reason}`}
            >
              <Txt variant="micro" color="muted">
                {t("suspension.reason")}
              </Txt>
              <Txt variant="bodyStrong">{suspension.reason}</Txt>
            </View>
          ) : null}
          <View
            style={[styles.fact, styles.factRow, { borderBottomWidth: 0 }]}
            accessible
            accessibilityLabel={`${indefinite ? t("suspension.duration") : t("suspension.until")}: ${untilText(suspension)}`}
          >
            <CalendarClock size={18} color={theme.muted} strokeWidth={2.2} />
            <View style={{ flex: 1 }}>
              <Txt variant="micro" color="muted">
                {indefinite ? t("suspension.duration") : t("suspension.until")}
              </Txt>
              <Txt variant="bodyStrong" tabular>
                {untilText(suspension)}
              </Txt>
            </View>
          </View>
        </View>
      </View>

      <Txt variant="caption" color="muted" align="center">
        {t("suspension.helpHint")}
      </Txt>
      <Button
        title={t("suspension.help")}
        variant="secondary"
        size={driver ? "lg" : "md"}
        icon={LifeBuoy}
        onPress={() => router.push("/reports")}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { borderRadius: radius.card, padding: space.md, gap: space.sm },
  titleRow: { flexDirection: "row", alignItems: "center", gap: space.sm },
  icon: {
    width: 44,
    height: 44,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  facts: { borderRadius: radius.tile, paddingHorizontal: space.md },
  fact: { paddingVertical: space.sm, gap: 2, borderBottomWidth: 1 },
  factRow: { flexDirection: "row", alignItems: "center", gap: space.sm },
});
