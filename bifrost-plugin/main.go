// FreshGuard plugin for Bifrost (native Go, dynamically loaded .so).
//
// After every successful chat completion it sends the assistant's answer to the FreshGuard service,
// which extracts time-sensitive claims and re-verifies them live with Tavily. The response is
// annotated with X-FreshGuard-* headers and (optionally) a "freshguard" report field.
// Failures never break the request: the original response passes through.
package main

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/maximhq/bifrost/core/schemas"
)

var (
	cfg     Config
	checker Checker
)

// Init is called by Bifrost with the plugin's "config" block from config.json.
func Init(config any) error {
	cfg = Config{}
	if config != nil {
		raw, err := json.Marshal(config)
		if err != nil {
			return fmt.Errorf("freshguard: bad config: %w", err)
		}
		if err := json.Unmarshal(raw, &cfg); err != nil {
			return fmt.Errorf("freshguard: bad config: %w", err)
		}
	}
	cfg.defaults()
	checker = HTTPChecker(cfg)
	return nil
}

func GetName() string { return "freshguard" }

func Cleanup() error { return nil }

// HTTPTransportPreHook is a no-op; the plugin only acts on responses.
func HTTPTransportPreHook(ctx *schemas.BifrostContext, req *schemas.HTTPRequest) (*schemas.HTTPResponse, error) {
	return nil, nil
}

// HTTPTransportPostHook annotates non-streaming chat completions with a freshness report.
func HTTPTransportPostHook(ctx *schemas.BifrostContext, req *schemas.HTTPRequest, resp *schemas.HTTPResponse) error {
	if req == nil || resp == nil || !ShouldCheck(cfg, req.Path, req.Headers, resp.StatusCode) {
		return nil
	}
	if strings.Contains(strings.ToLower(resp.Headers["Content-Type"]), "event-stream") {
		return nil
	}
	body, headers := Annotate(cfg, resp.Body, checker)
	resp.Body = body
	if resp.Headers == nil {
		resp.Headers = map[string]string{}
	}
	for k, v := range headers {
		resp.Headers[k] = v
	}
	ctx.Log(schemas.LogLevelInfo, fmt.Sprintf("freshguard: %s score=%s stale=%s",
		headers["X-FreshGuard-Status"], headers["X-FreshGuard-Score"], headers["X-FreshGuard-Stale-Count"]))
	return nil
}
