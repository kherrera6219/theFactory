package main

import (
	"strings"
	"testing"
)

func TestSummarizeEvents(t *testing.T) {
	input := strings.NewReader("{\"category\":\"api\",\"ms\":120}\n{\"category\":\"db\",\"ms\":80}\n{\"category\":\"api\",\"ms\":30}\n")
	summary, err := SummarizeEvents(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if summary.TotalEvents != 3 || summary.TotalMs != 230 {
		t.Fatalf("unexpected totals: %+v", summary)
	}
	if summary.ByCategory["api"].Count != 2 || summary.ByCategory["api"].TotalMs != 150 {
		t.Fatalf("unexpected api stats: %+v", summary.ByCategory["api"])
	}
	if summary.ByCategory["db"].Count != 1 || summary.ByCategory["db"].TotalMs != 80 {
		t.Fatalf("unexpected db stats: %+v", summary.ByCategory["db"])
	}
}
