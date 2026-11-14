<?php

declare(strict_types=1);

namespace LegacyBilling\Tests;

use InvalidArgumentException;
use LegacyBilling\InvoiceCalc;
use PHPUnit\Framework\TestCase;

final class InvoiceCalcTest extends TestCase
{
    public function testCalculatesSubtotalDiscountTaxAndTotal(): void
    {
        $calc = new InvoiceCalc(0.10);
        $totals = $calc->calculateTotals([
            ['unit_price' => 25.00, 'quantity' => 2],
            ['unit_price' => 10.00, 'quantity' => 1],
        ], 0.20);

        $this->assertSame(60.0, $totals['subtotal']);
        $this->assertSame(12.0, $totals['discount']);
        $this->assertSame(4.8, $totals['tax']);
        $this->assertSame(52.8, $totals['total']);
    }

    public function testRejectsExcessiveDiscount(): void
    {
        $calc = new InvoiceCalc();
        $this->expectException(InvalidArgumentException::class);
        $calc->calculateTotals([['unit_price' => 10.0, 'quantity' => 1]], 0.75);
    }
}
