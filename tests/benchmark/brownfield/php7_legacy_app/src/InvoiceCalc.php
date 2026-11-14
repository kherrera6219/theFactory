<?php

declare(strict_types=1);

namespace LegacyBilling;

use InvalidArgumentException;

class InvoiceCalc
{
    /** @var float */
    private $defaultTaxRate;

    public function __construct(float $defaultTaxRate = 0.0825)
    {
        if ($defaultTaxRate < 0.0 || $defaultTaxRate > 1.0) {
            throw new InvalidArgumentException('Tax rate must be between 0.0 and 1.0');
        }
        $this->defaultTaxRate = $defaultTaxRate;
    }

    /**
     * @param array<int, array<string, mixed>> $lineItems
     * @return array<string, float>
     */
    public function calculateTotals(array $lineItems, float $discountRate = 0.0): array
    {
        if ($discountRate < 0.0 || $discountRate > 0.5) {
            throw new InvalidArgumentException('Discount rate must be between 0.0 and 0.5');
        }

        $subtotal = 0.0;
        foreach ($lineItems as $item) {
            $unitPrice = (float) ($item['unit_price'] ?? 0.0);
            $qty = (int) ($item['quantity'] ?? 0);
            if ($unitPrice < 0.0 || $qty <= 0) {
                throw new InvalidArgumentException('Invalid line item price or quantity');
            }
            $subtotal += $unitPrice * $qty;
        }

        $discount = round($subtotal * $discountRate, 2);
        $taxable = max(0.0, round($subtotal - $discount, 2));
        $tax = round($taxable * $this->defaultTaxRate, 2);
        $total = round($taxable + $tax, 2);

        return [
            'subtotal' => round($subtotal, 2),
            'discount' => $discount,
            'tax' => $tax,
            'total' => $total,
        ];
    }
}
