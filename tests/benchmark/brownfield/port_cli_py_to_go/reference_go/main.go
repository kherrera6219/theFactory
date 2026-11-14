package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"
)

type CategoryStats struct {
	Count   int `json:"count"`
	TotalMs int `json:"total_ms"`
}

type Summary struct {
	TotalEvents int                      `json:"total_events"`
	TotalMs     int                      `json:"total_ms"`
	ByCategory  map[string]CategoryStats `json:"by_category"`
}

type rawEvent struct {
	Category string `json:"category"`
	Ms       int    `json:"ms"`
}

func SummarizeEvents(r io.Reader) (Summary, error) {
	summary := Summary{
		ByCategory: make(map[string]CategoryStats),
	}
	scanner := bufio.NewScanner(r)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var evt rawEvent
		if err := json.Unmarshal([]byte(line), &evt); err != nil {
			return Summary{}, err
		}
		cat := strings.TrimSpace(evt.Category)
		if cat == "" {
			return Summary{}, errors.New("category is required")
		}
		if evt.Ms < 0 {
			return Summary{}, errors.New("ms must be non-negative")
		}
		bucket := summary.ByCategory[cat]
		bucket.Count++
		bucket.TotalMs += evt.Ms
		summary.ByCategory[cat] = bucket
		summary.TotalEvents++
		summary.TotalMs += evt.Ms
	}
	if err := scanner.Err(); err != nil {
		return Summary{}, err
	}
	return summary, nil
}

func main() {
	inputPath := flag.String("input", "", "Path to JSONL input file or '-' for stdin")
	flag.Parse()
	if *inputPath == "" {
		fmt.Fprintln(os.Stderr, "--input is required")
		os.Exit(2)
	}

	var reader io.Reader = os.Stdin
	if *inputPath != "-" {
		f, err := os.Open(*inputPath)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		defer f.Close()
		reader = f
	}

	summary, err := SummarizeEvents(reader)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	encoded, err := json.Marshal(summary)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println(string(encoded))
}
