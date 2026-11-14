package com.example.legacy;

import org.junit.Test;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.assertEquals;

public class LedgerCalcTest {

    @Test
    public void netBalanceAndAccountSummary() {
        LedgerCalc calc = new LedgerCalc();
        List<LedgerCalc.Entry> entries = Arrays.asList(
                new LedgerCalc.Entry("acct-1", new BigDecimal("100.00"), "CREDIT"),
                new LedgerCalc.Entry("acct-1", new BigDecimal("25.50"), "DEBIT"),
                new LedgerCalc.Entry("acct-2", new BigDecimal("40.00"), "CREDIT")
        );

        assertEquals(new BigDecimal("114.50"), calc.netBalance(entries));
        Map<String, BigDecimal> summary = calc.summarizeByAccount(entries);
        assertEquals(new BigDecimal("74.50"), summary.get("acct-1"));
        assertEquals(new BigDecimal("40.00"), summary.get("acct-2"));
    }

    @Test
    public void monthlyFeeAppliedBelowMinimumOnly() {
        LedgerCalc calc = new LedgerCalc();
        assertEquals(
                new BigDecimal("45.00"),
                calc.applyMonthlyFee(new BigDecimal("50.00"), new BigDecimal("100.00"), new BigDecimal("5.00"))
        );
        assertEquals(
                new BigDecimal("120.00"),
                calc.applyMonthlyFee(new BigDecimal("120.00"), new BigDecimal("100.00"), new BigDecimal("5.00"))
        );
    }
}
