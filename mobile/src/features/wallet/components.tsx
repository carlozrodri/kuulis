import { router } from "expo-router";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { StyleSheet, View } from "react-native";

import { ChevronLeft, Copy, type Icon } from "@/components/icons";
import { IconButton, Row, Txt } from "@/components/ui";
import { fonts, radius, space, useTheme } from "@/theme";

import { copyText } from "./format";

/** Leaves a wallet flow: back when there is history, else the wallet tab. */
export function leaveFlow() {
  if (router.canGoBack()) router.back();
  else router.replace("/wallet");
}

/** Back button, an optional step counter and the title of a wallet flow screen. */
export function FlowHeader({
  title,
  subtitle,
  step,
  onBack = leaveFlow,
}: {
  title: string;
  subtitle?: string | null;
  step?: string | null;
  onBack?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <View
      style={{ gap: space.md, paddingTop: space.xs, paddingBottom: space.md }}
    >
      <Row>
        <IconButton
          icon={ChevronLeft}
          label={t("common.back")}
          onPress={onBack}
        />
        {step ? (
          <Txt variant="label" color="muted">
            {step}
          </Txt>
        ) : null}
      </Row>
      <View style={{ gap: space.xxs }}>
        <Txt variant="title" accessibilityRole="header">
          {title}
        </Txt>
        {subtitle ? <Txt color="muted">{subtitle}</Txt> : null}
      </View>
    </View>
  );
}

/** Numbered instructions ("1 Abre Binance…"). */
export function Steps({ items }: { items: ReactNode[] }) {
  const theme = useTheme();
  return (
    <View style={{ gap: space.sm }}>
      {items.map((item, index) => (
        <View key={index} style={styles.step}>
          <View
            style={[styles.stepNumber, { backgroundColor: theme.surfaceAlt }]}
          >
            <Txt
              variant="micro"
              style={{
                color:
                  theme.scheme === "dark"
                    ? theme.primary
                    : theme.primaryPressed,
              }}
            >
              {index + 1}
            </Txt>
          </View>
          <View style={{ flex: 1 }}>
            {typeof item === "string" ? <Txt>{item}</Txt> : item}
          </View>
        </View>
      ))}
    </View>
  );
}

/** A value the driver has to type elsewhere (Kuulis' Pay ID), big and with a copy button. */
export function CopyValue({
  label,
  value,
  copiedMessage,
  icon: ValueIcon,
}: {
  label: string;
  value: string;
  copiedMessage: string;
  icon?: Icon;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <View style={[styles.copy, { backgroundColor: theme.background }]}>
      {ValueIcon ? (
        <ValueIcon size={22} color={theme.primary} strokeWidth={2} />
      ) : null}
      <View
        style={{ flex: 1 }}
        accessible
        accessibilityLabel={`${label}: ${value.split("").join(" ")}`}
      >
        <Txt variant="micro" color="muted">
          {label}
        </Txt>
        <Txt style={[styles.copyValue, { color: theme.text }]} tabular>
          {value}
        </Txt>
      </View>
      <IconButton
        icon={Copy}
        label={t("wallet.copyLabel", { label })}
        onPress={() => void copyText(value, copiedMessage)}
      />
    </View>
  );
}

/** Label / value line in summaries. */
export function SummaryRow({
  label,
  value,
  strong,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <View style={styles.summary}>
      <Txt color="muted" style={{ flex: 1 }}>
        {label}
      </Txt>
      <Txt variant={strong ? "subtitle" : "bodyStrong"} tabular align="right">
        {value}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  step: { flexDirection: "row", gap: space.sm, alignItems: "flex-start" },
  stepNumber: {
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 1,
  },
  copy: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    borderRadius: radius.tile,
    paddingLeft: space.md,
    paddingRight: space.xs,
    paddingVertical: space.xs,
  },
  copyValue: {
    fontFamily: fonts.extrabold,
    fontSize: 24,
    lineHeight: 30,
    letterSpacing: 0.5,
  },
  summary: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    minHeight: 32,
  },
});
