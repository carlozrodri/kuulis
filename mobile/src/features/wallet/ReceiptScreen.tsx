import { useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { Share, StyleSheet, View } from "react-native";

import { ErrorState } from "@/components/ErrorState";
import { Info, Receipt, SearchX, Share2 } from "@/components/icons";
import {
  Button,
  Card,
  EmptyState,
  IconTile,
  Notice,
  Screen,
  Skeleton,
  StatusPill,
  Txt,
} from "@/components/ui";
import { useReceipt } from "@/hooks/useWallet";
import { formatAmount } from "@/lib/money";
import type { Receipt as ReceiptData } from "@/lib/types";
import { receiptShareText } from "@/lib/wallet";
import { fonts, radius, space, useTheme } from "@/theme";

import { FlowHeader, SummaryRow } from "./components";
import { useWalletFormat } from "./format";

/**
 * "Ver recibo" (doc 17): the receipt of a top-up or a paid fee. Kuulis has no company yet, so every receipt
 * is "no fiscal" and says so. Shared as plain text.
 */
export function ReceiptScreen() {
  const { t } = useTranslation();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const receipt = useReceipt(id || undefined);
  const format = useWalletFormat();

  const share = (data: ReceiptData) =>
    void Share.share({
      message: receiptShareText(data, t, format.dateTime),
    }).catch(() => undefined);

  return (
    <Screen
      header={<FlowHeader title={t("wallet.receipt.title")} />}
      footer={
        receipt.data ? (
          <Button
            title={t("wallet.receipt.share")}
            icon={Share2}
            variant="secondary"
            onPress={() => share(receipt.data)}
          />
        ) : null
      }
    >
      {receipt.isPending && id ? (
        <View style={{ gap: space.md }}>
          <Skeleton height={140} radius={radius.card} />
          <Skeleton height={200} radius={radius.card} />
        </View>
      ) : receipt.data ? (
        <ReceiptCard receipt={receipt.data} />
      ) : receipt.error ? (
        <ErrorState error={receipt.error} onRetry={() => receipt.refetch()} />
      ) : (
        <EmptyState icon={SearchX} title={t("errors.receipt_not_found")} />
      )}
    </Screen>
  );
}

function ReceiptCard({ receipt }: { receipt: ReceiptData }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const format = useWalletFormat();
  return (
    <View style={{ gap: space.md }}>
      <Card elevated style={{ gap: space.md }}>
        <View style={styles.top}>
          <IconTile icon={Receipt} tone="primary" size={44} />
          <View style={{ flex: 1, gap: 2 }}>
            <Txt variant="caption" color="muted">
              {receipt.issuer || "Kuulis"}
            </Txt>
            <Txt variant="subtitle" tabular>
              {t("wallet.receipt.number", { number: receipt.number })}
            </Txt>
          </View>
          {!receipt.fiscal ? (
            <StatusPill label={t("wallet.receipt.nonFiscal")} tone="neutral" />
          ) : null}
        </View>
        <View
          accessible
          accessibilityLabel={`${receipt.concept}: ${formatAmount(receipt.amount)} USDT`}
          style={{ gap: 2 }}
        >
          <Txt color="muted">{receipt.concept}</Txt>
          <Txt style={[styles.amount, { color: theme.text }]} tabular>
            {formatAmount(receipt.amount)}{" "}
            <Txt style={[styles.currency, { color: theme.text }]}>USDT</Txt>
          </Txt>
        </View>
      </Card>

      <Card style={{ gap: space.xxs }}>
        <SummaryRow
          label={t("wallet.receipt.balanceAfter")}
          value={`${formatAmount(receipt.balance_after)} USDT`}
        />
        <SummaryRow
          label={t("wallet.receipt.date")}
          value={format.dateTime(receipt.issued_at)}
        />
        {receipt.reference ? (
          <SummaryRow
            label={t("wallet.receipt.reference")}
            value={receipt.reference}
          />
        ) : null}
        <SummaryRow
          label={t("wallet.receipt.driver")}
          value={receipt.driver.name || receipt.driver.email}
        />
      </Card>

      {!receipt.fiscal ? (
        <Notice tone="info" icon={Info}>
          {t("wallet.receipt.nonFiscalBody")}
        </Notice>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: "row", alignItems: "center", gap: space.sm },
  amount: {
    fontFamily: fonts.extrabold,
    fontSize: 32,
    lineHeight: 40,
    letterSpacing: -0.6,
  },
  currency: { fontFamily: fonts.extrabold, fontSize: 16 },
});
