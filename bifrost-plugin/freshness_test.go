package main

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

const completion = `{"id":"x","choices":[{"message":{"role":"assistant","content":"The latest stable Python release is Python 3.11, released recently."}}]}`

func testCfg(url string) Config {
	c := Config{CheckURL: url}
	c.defaults()
	return c
}

func TestShouldCheck(t *testing.T) {
	c := testCfg("")
	if !ShouldCheck(c, "/v1/chat/completions", nil, 200) {
		t.Fatal("chat completions should be checked")
	}
	if ShouldCheck(c, "/v1/embeddings", nil, 200) {
		t.Fatal("embeddings must not be checked")
	}
	if ShouldCheck(c, "/v1/chat/completions", map[string]string{"X-FreshGuard-Skip": "1"}, 200) {
		t.Fatal("skip header must be honoured (prevents recursion)")
	}
	if ShouldCheck(c, "/v1/chat/completions", nil, 500) {
		t.Fatal("error responses must pass through")
	}
}

func TestAnswerTextFormats(t *testing.T) {
	if got := AnswerText([]byte(completion)); got == "" {
		t.Fatal("string content not extracted")
	}
	parts := `{"choices":[{"message":{"content":[{"type":"text","text":"a"},{"type":"text","text":"b"}]}}]}`
	if got := AnswerText([]byte(parts)); got != "ab" {
		t.Fatalf("content parts: got %q", got)
	}
	if AnswerText([]byte(`not json`)) != "" {
		t.Fatal("invalid JSON should yield empty text")
	}
}

func TestAnnotateAgainstFakeService(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var in map[string]string
		_ = json.NewDecoder(r.Body).Decode(&in)
		if in["answer"] == "" {
			http.Error(w, "missing answer", 400)
			return
		}
		_, _ = w.Write([]byte(`{"overall_freshness":3,"overall_label":"stale","stale_count":1,
			"claims":[{"claim":"Latest Python is 3.11","label":"stale","current_fact":"Python 3.15"}]}`))
	}))
	defer srv.Close()
	c := testCfg(srv.URL)

	body, h := Annotate(c, []byte(completion), HTTPChecker(c))
	if h["X-FreshGuard-Score"] != "3" || h["X-FreshGuard-Label"] != "stale" || h["X-FreshGuard-Stale-Count"] != "1" {
		t.Fatalf("unexpected headers: %v", h)
	}
	var out map[string]any
	if err := json.Unmarshal(body, &out); err != nil {
		t.Fatal(err)
	}
	fg, ok := out["freshguard"].(map[string]any)
	if !ok || fg["overall_label"] != "stale" {
		t.Fatalf("report not embedded: %v", out["freshguard"])
	}
	if out["choices"] == nil {
		t.Fatal("original completion fields must be preserved")
	}
}

func TestAnnotateFailsOpen(t *testing.T) {
	c := testCfg("")
	failing := func(string) (*Report, json.RawMessage, error) { return nil, nil, errors.New("service down") }
	body, h := Annotate(c, []byte(completion), failing)
	if string(body) != completion {
		t.Fatal("body must be unchanged when verification fails")
	}
	if h["X-FreshGuard-Status"] != "error" {
		t.Fatalf("expected error status, got %v", h)
	}
}

func TestShortAnswersSkipped(t *testing.T) {
	c := testCfg("")
	called := false
	chk := func(string) (*Report, json.RawMessage, error) { called = true; return &Report{}, json.RawMessage(`{}`), nil }
	_, h := Annotate(c, []byte(`{"choices":[{"message":{"content":"OK"}}]}`), chk)
	if called || h["X-FreshGuard-Status"] != "skipped" {
		t.Fatal("short answers should be skipped without calling the service")
	}
}
