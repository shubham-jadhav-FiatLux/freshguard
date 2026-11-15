package main

// Core logic of the FreshGuard Bifrost plugin, kept free of Bifrost types so it is easy to unit-test.

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// SkipHeader lets callers (including FreshGuard itself) opt a request out of freshness checking.
const SkipHeader = "x-freshguard-skip"

// Config is read from the plugin's "config" block in Bifrost's config.json.
type Config struct {
	// URL of the FreshGuard service check endpoint, e.g. http://localhost:8000/api/check
	CheckURL string `json:"check_url"`
	// Request paths to annotate (default: OpenAI-compatible chat completions).
	Paths []string `json:"paths"`
	// Timeout for the verification call (default 60s). On timeout the response passes through unchanged.
	TimeoutSeconds int `json:"timeout_seconds"`
	// When true, the report is added as a "freshguard" field in the JSON body (headers are always set).
	EmbedReport *bool `json:"embed_report"`
	// Minimum answer length (characters) worth checking (default 40).
	MinChars int `json:"min_chars"`
}

func (c *Config) defaults() {
	if c.CheckURL == "" {
		c.CheckURL = "http://localhost:8000/api/check"
	}
	if len(c.Paths) == 0 {
		c.Paths = []string{"/v1/chat/completions"}
	}
	if c.TimeoutSeconds <= 0 {
		c.TimeoutSeconds = 60
	}
	if c.EmbedReport == nil {
		t := true
		c.EmbedReport = &t
	}
	if c.MinChars <= 0 {
		c.MinChars = 40
	}
}

// Report is the subset of the FreshGuard report the plugin needs; the full JSON is kept raw.
type Report struct {
	OverallFreshness int    `json:"overall_freshness"`
	OverallLabel     string `json:"overall_label"`
	StaleCount       int    `json:"stale_count"`
	Claims           []any  `json:"claims"`
}

// Checker verifies an answer and returns the parsed and raw FreshGuard report.
type Checker func(text string) (*Report, json.RawMessage, error)

// HTTPChecker calls the FreshGuard service.
func HTTPChecker(cfg Config) Checker {
	client := &http.Client{Timeout: time.Duration(cfg.TimeoutSeconds) * time.Second}
	return func(text string) (*Report, json.RawMessage, error) {
		payload, _ := json.Marshal(map[string]string{"answer": text})
		resp, err := client.Post(cfg.CheckURL, "application/json", bytes.NewReader(payload))
		if err != nil {
			return nil, nil, err
		}
		defer resp.Body.Close()
		raw, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, nil, err
		}
		if resp.StatusCode != http.StatusOK {
			return nil, nil, fmt.Errorf("freshguard returned %d: %s", resp.StatusCode, truncate(string(raw), 200))
		}
		var rep Report
		if err := json.Unmarshal(raw, &rep); err != nil {
			return nil, nil, err
		}
		return &rep, raw, nil
	}
}

// ShouldCheck decides whether a request/response pair is eligible for annotation.
func ShouldCheck(cfg Config, path string, headers map[string]string, status int) bool {
	if status != 0 && status != http.StatusOK {
		return false
	}
	for k, v := range headers {
		if strings.EqualFold(k, SkipHeader) && v != "" && v != "0" && !strings.EqualFold(v, "false") {
			return false
		}
	}
	for _, p := range cfg.Paths {
		if strings.HasSuffix(path, p) {
			return true
		}
	}
	return false
}

// AnswerText extracts the assistant text from an OpenAI-compatible chat completion body.
func AnswerText(body []byte) string {
	var cc struct {
		Choices []struct {
			Message struct {
				Content any `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	if json.Unmarshal(body, &cc) != nil || len(cc.Choices) == 0 {
		return ""
	}
	switch c := cc.Choices[0].Message.Content.(type) {
	case string:
		return c
	case []any: // content parts: [{"type":"text","text":"..."}]
		var sb strings.Builder
		for _, part := range c {
			if m, ok := part.(map[string]any); ok {
				if t, ok := m["text"].(string); ok {
					sb.WriteString(t)
				}
			}
		}
		return sb.String()
	}
	return ""
}

// Annotate verifies the answer in body and returns the new body plus headers to set.
// It never fails the request: on any error it returns the original body and an error header.
func Annotate(cfg Config, body []byte, check Checker) ([]byte, map[string]string) {
	text := AnswerText(body)
	if len(strings.TrimSpace(text)) < cfg.MinChars {
		return body, map[string]string{"X-FreshGuard-Status": "skipped"}
	}
	rep, raw, err := check(text)
	if err != nil {
		return body, map[string]string{"X-FreshGuard-Status": "error", "X-FreshGuard-Error": truncate(err.Error(), 120)}
	}
	headers := map[string]string{
		"X-FreshGuard-Status":      "checked",
		"X-FreshGuard-Score":       fmt.Sprint(rep.OverallFreshness),
		"X-FreshGuard-Label":       rep.OverallLabel,
		"X-FreshGuard-Stale-Count": fmt.Sprint(rep.StaleCount),
		"X-FreshGuard-Claims":      fmt.Sprint(len(rep.Claims)),
	}
	if !*cfg.EmbedReport {
		return body, headers
	}
	var obj map[string]json.RawMessage
	if err := json.Unmarshal(body, &obj); err != nil {
		return body, headers
	}
	obj["freshguard"] = raw
	out, err := json.Marshal(obj)
	if err != nil {
		return body, headers
	}
	return out, headers
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
