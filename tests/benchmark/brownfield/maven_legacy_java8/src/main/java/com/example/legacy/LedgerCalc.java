package com.example.legacy;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class LedgerCalc {

    public static final class Entry {
        private final String accountId;
        private final BigDecimal amount;
        private final String kind;

        public Entry(String accountId, BigDecimal amount, String kind) {
            if (accountId == null || accountId.trim().isEmpty()) {
                throw new IllegalArgumentException("accountId required");
            }
            if (amount == null) {
                throw new IllegalArgumentException("amount required");
            }
            if (!"CREDIT".equals(kind) && !"DEBIT".equals(kind)) {
                throw new IllegalArgumentException("kind must be CREDIT or DEBIT");
            }
            this.accountId = accountId.trim();
            this.amount = amount.setScale(2, RoundingMode.HALF_UP);
            this.kind = kind;
        }

        public String getAccountId() {
            return accountId;
        }

        public BigDecimal getAmount() {
            return amount;
        }

        public String getKind() {
            return kind;
        }
    }

    public BigDecimal netBalance(List<Entry> entries) {
        if (entries == null || entries.isEmpty()) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        BigDecimal total = BigDecimal.ZERO;
        for (Entry entry : entries) {
            if ("CREDIT".equals(entry.getKind())) {
                total = total.add(entry.getAmount());
            } else {
                total = total.subtract(entry.getAmount());
            }
        }
        return total.setScale(2, RoundingMode.HALF_UP);
    }

    public BigDecimal applyMonthlyFee(BigDecimal balance, BigDecimal minimumBalance, BigDecimal fee) {
        if (balance == null || minimumBalance == null || fee == null) {
            throw new IllegalArgumentException("balance, minimumBalance and fee are required");
        }
        if (fee.compareTo(BigDecimal.ZERO) < 0) {
            throw new IllegalArgumentException("fee must be non-negative");
        }
        if (balance.compareTo(minimumBalance) < 0) {
            return balance.subtract(fee).setScale(2, RoundingMode.HALF_UP);
        }
        return balance.setScale(2, RoundingMode.HALF_UP);
    }

    public Map<String, BigDecimal> summarizeByAccount(List<Entry> entries) {
        if (entries == null || entries.isEmpty()) {
            return Collections.emptyMap();
        }
        Map<String, BigDecimal> summary = new LinkedHashMap<String, BigDecimal>();
        for (Entry entry : entries) {
            BigDecimal current = summary.get(entry.getAccountId());
            if (current == null) {
                current = BigDecimal.ZERO;
            }
            if ("CREDIT".equals(entry.getKind())) {
                current = current.add(entry.getAmount());
            } else {
                current = current.subtract(entry.getAmount());
            }
            summary.put(entry.getAccountId(), current.setScale(2, RoundingMode.HALF_UP));
        }
        return summary;
    }
}
