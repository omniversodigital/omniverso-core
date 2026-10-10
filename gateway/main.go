// Package main implements the OMNIVERSO API Gateway.
// A high-performance reverse proxy and auth layer built with Go + Chi.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/golang-jwt/jwt/v5"
	"github.com/redis/go-redis/v9"
)

// ═══════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════

type Config struct {
	Port             string
	JWTSecret        string
	CORSOrigins      []string
	OrchestratorURL  string
	ModelRouterURL   string
	RAGEngineURL     string
	TradingEngineURL string
	TelegramBotURL   string
	HomeAssistantURL string
	RedisURL         string
}

func LoadConfig() *Config {
	origins := strings.Split(getEnv("CORS_ORIGINS", "http://localhost:3000"), ",")
	return &Config{
		Port:             getEnv("PORT", "8080"),
		JWTSecret:        getEnv("JWT_SECRET", "omniverso-dev-secret"),
		CORSOrigins:      origins,
		OrchestratorURL:  getEnv("ORCHESTRATOR_URL", "http://localhost:8001"),
		ModelRouterURL:   getEnv("MODEL_ROUTER_URL", "http://localhost:8002"),
		RAGEngineURL:     getEnv("RAG_ENGINE_URL", "http://localhost:8003"),
		TradingEngineURL: getEnv("TRADING_ENGINE_URL", "http://localhost:8004"),
		TelegramBotURL:   getEnv("TELEGRAM_BOT_URL", "http://localhost:8005"),
		HomeAssistantURL: getEnv("HOMEASSISTANT_URL", "http://localhost:8123"),
		RedisURL:         getEnv("REDIS_URL", "redis://localhost:6379/0"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ═══════════════════════════════════════════════════════════
// Application
// ═══════════════════════════════════════════════════════════

type App struct {
	config *Config
	redis  *redis.Client
	logger *slog.Logger
	router *chi.Mux
}

func NewApp(cfg *Config) (*App, error) {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))

	// Parse Redis URL
	opt, err := redis.ParseURL(cfg.RedisURL)
	if err != nil {
		return nil, fmt.Errorf("invalid redis URL: %w", err)
	}
	rdb := redis.NewClient(opt)

	// Verify Redis connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := rdb.Ping(ctx).Err(); err != nil {
		logger.Warn("Redis not available, continuing without cache", "error", err)
	}

	app := &App{
		config: cfg,
		redis:  rdb,
		logger: logger,
	}
	app.router = app.buildRouter()
	return app, nil
}

// ═══════════════════════════════════════════════════════════
// Router
// ═══════════════════════════════════════════════════════════

func (a *App) buildRouter() *chi.Mux {
	r := chi.NewRouter()

	// ─── Global Middleware ────────────────────────────────
	r.Use(chimw.RequestID)
	r.Use(chimw.RealIP)
	r.Use(a.structuredLogger)
	r.Use(chimw.Recoverer)
	r.Use(chimw.Compress(5))
	r.Use(chimw.Timeout(30 * time.Second))

	// CORS
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   a.config.CORSOrigins,
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type", "X-API-Key", "X-Request-ID"},
		ExposedHeaders:   []string{"X-Request-ID", "X-RateLimit-Remaining"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	// Rate limiter
	r.Use(a.rateLimiter)

	// ─── Public Routes ───────────────────────────────────
	r.Get("/health", a.handleHealth)
	r.Get("/ready", a.handleReady)
	r.Post("/auth/login", a.handleLogin)
	r.Post("/auth/register", a.handleRegister)

	// ─── API v1 (Authenticated) ──────────────────────────
	r.Route("/api/v1", func(r chi.Router) {
		r.Use(a.authMiddleware)

		// Agent Orchestrator proxy
		r.Route("/agents", func(r chi.Router) {
			r.HandleFunc("/*", a.proxyTo(a.config.OrchestratorURL))
		})

		// Model Router proxy
		r.Route("/models", func(r chi.Router) {
			r.HandleFunc("/*", a.proxyTo(a.config.ModelRouterURL))
		})

		// RAG Engine proxy
		r.Route("/rag", func(r chi.Router) {
			r.HandleFunc("/*", a.proxyTo(a.config.RAGEngineURL))
		})

		// Trading Engine proxy
		r.Route("/trading", func(r chi.Router) {
			r.HandleFunc("/*", a.proxyTo(a.config.TradingEngineURL))
		})

		// Telegram Bot proxy
		r.Route("/bot", func(r chi.Router) {
			r.HandleFunc("/*", a.proxyTo(a.config.TelegramBotURL))
		})

		// Home Assistant proxy
		r.Route("/homeassistant", func(r chi.Router) {
			r.HandleFunc("/*", a.proxyTo(a.config.HomeAssistantURL))
		})

		// Direct endpoints
		r.Get("/status", a.handleStatus)
		r.Get("/me", a.handleMe)
	})

	// ─── API Key Routes (for external consumers) ─────────
	r.Route("/api/ext/v1", func(r chi.Router) {
		r.Use(a.apiKeyMiddleware)

		r.Route("/agents", func(r chi.Router) {
			r.HandleFunc("/*", a.proxyTo(a.config.OrchestratorURL))
		})
		r.Route("/models", func(r chi.Router) {
			r.HandleFunc("/*", a.proxyTo(a.config.ModelRouterURL))
		})
	})

	return r
}

// ═══════════════════════════════════════════════════════════
// Handlers
// ═══════════════════════════════════════════════════════════

type HealthResponse struct {
	Status    string            `json:"status"`
	Service   string            `json:"service"`
	Version   string            `json:"version"`
	Timestamp string            `json:"timestamp"`
	Checks    map[string]string `json:"checks,omitempty"`
}

func (a *App) handleHealth(w http.ResponseWriter, r *http.Request) {
	resp := HealthResponse{
		Status:    "healthy",
		Service:   "omniverso-gateway",
		Version:   "1.0.0",
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}
	writeJSON(w, http.StatusOK, resp)
}

func (a *App) handleReady(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	checks := make(map[string]string)

	// Check Redis
	if err := a.redis.Ping(ctx).Err(); err != nil {
		checks["redis"] = "unhealthy"
	} else {
		checks["redis"] = "healthy"
	}

	// Check downstream services
	for name, svcURL := range map[string]string{
		"orchestrator": a.config.OrchestratorURL,
		"model_router": a.config.ModelRouterURL,
	} {
		client := &http.Client{Timeout: 2 * time.Second}
		resp, err := client.Get(svcURL + "/health")
		if err != nil || resp.StatusCode != http.StatusOK {
			checks[name] = "unhealthy"
		} else {
			checks[name] = "healthy"
			resp.Body.Close()
		}
	}

	status := http.StatusOK
	statusText := "ready"
	for _, v := range checks {
		if v == "unhealthy" {
			status = http.StatusServiceUnavailable
			statusText = "degraded"
			break
		}
	}

	writeJSON(w, status, HealthResponse{
		Status:    statusText,
		Service:   "omniverso-gateway",
		Version:   "1.0.0",
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Checks:    checks,
	})
}

func (a *App) handleLogin(w http.ResponseWriter, r *http.Request) {
	// Placeholder — will connect to user service
	var req struct {
		Email    string `json:"email"`
		Password string `json:"password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	// TODO: validate against DB
	// For now, generate a dev token
	token, err := a.generateToken(req.Email, "user")
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to generate token")
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{
		"token":      token,
		"expires_in": "86400",
	})
}

func (a *App) handleRegister(w http.ResponseWriter, r *http.Request) {
	// Placeholder
	writeJSON(w, http.StatusCreated, map[string]string{
		"message": "registration endpoint — connect to user service",
	})
}

func (a *App) handleStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"ecosystem": "omniverso",
		"version":   "1.0.0",
		"services": map[string]string{
			"gateway":      "running",
			"orchestrator": a.config.OrchestratorURL,
			"model_router": a.config.ModelRouterURL,
		},
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

func (a *App) handleMe(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(ctxKeyClaims).(jwt.MapClaims)
	if !ok {
		writeError(w, http.StatusUnauthorized, "invalid token claims")
		return
	}
	writeJSON(w, http.StatusOK, claims)
}

// ═══════════════════════════════════════════════════════════
// Middleware
// ═══════════════════════════════════════════════════════════

type contextKey string

const ctxKeyClaims contextKey = "claims"

func (a *App) structuredLogger(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		ww := chimw.NewWrapResponseWriter(w, r.ProtoMajor)
		next.ServeHTTP(ww, r)
		a.logger.Info("request",
			"method", r.Method,
			"path", r.URL.Path,
			"status", ww.Status(),
			"duration_ms", time.Since(start).Milliseconds(),
			"bytes", ww.BytesWritten(),
			"request_id", chimw.GetReqID(r.Context()),
		)
	})
}

func (a *App) authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" {
			writeError(w, http.StatusUnauthorized, "missing authorization header")
			return
		}

		tokenStr := strings.TrimPrefix(authHeader, "Bearer ")
		if tokenStr == authHeader {
			writeError(w, http.StatusUnauthorized, "invalid authorization format")
			return
		}

		token, err := jwt.Parse(tokenStr, func(token *jwt.Token) (interface{}, error) {
			if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
				return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
			}
			return []byte(a.config.JWTSecret), nil
		})
		if err != nil || !token.Valid {
			writeError(w, http.StatusUnauthorized, "invalid or expired token")
			return
		}

		claims, ok := token.Claims.(jwt.MapClaims)
		if !ok {
			writeError(w, http.StatusUnauthorized, "invalid token claims")
			return
		}

		ctx := context.WithValue(r.Context(), ctxKeyClaims, claims)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func (a *App) apiKeyMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		apiKey := r.Header.Get("X-API-Key")
		if apiKey == "" {
			apiKey = r.URL.Query().Get("api_key")
		}
		if apiKey == "" {
			writeError(w, http.StatusUnauthorized, "missing API key")
			return
		}

		// TODO: validate API key against DB/Redis cache
		// For now, accept any non-empty key in dev mode
		ctx := context.WithValue(r.Context(), ctxKeyClaims, jwt.MapClaims{
			"sub":  "api_key_user",
			"role": "api",
		})
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func (a *App) rateLimiter(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip rate limiting for health checks
		if r.URL.Path == "/health" || r.URL.Path == "/ready" {
			next.ServeHTTP(w, r)
			return
		}

		ctx := r.Context()
		ip := r.RemoteAddr

		key := fmt.Sprintf("rl:%s", ip)
		count, err := a.redis.Incr(ctx, key).Result()
		if err != nil {
			// Redis down — allow request but log
			a.logger.Warn("rate limiter redis error", "error", err)
			next.ServeHTTP(w, r)
			return
		}

		if count == 1 {
			a.redis.Expire(ctx, key, time.Minute)
		}

		w.Header().Set("X-RateLimit-Remaining", fmt.Sprintf("%d", max(0, 120-count)))

		if count > 120 { // 120 req/min per IP
			writeError(w, http.StatusTooManyRequests, "rate limit exceeded")
			return
		}

		next.ServeHTTP(w, r)
	})
}

// ═══════════════════════════════════════════════════════════
// Reverse Proxy
// ═══════════════════════════════════════════════════════════

func (a *App) proxyTo(target string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		targetURL, err := url.Parse(target)
		if err != nil {
			writeError(w, http.StatusBadGateway, "invalid upstream URL")
			return
		}

		proxy := httputil.NewSingleHostReverseProxy(targetURL)
		proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
			a.logger.Error("proxy error", "target", target, "error", err)
			writeError(w, http.StatusBadGateway, "upstream service unavailable")
		}

		// Rewrite path: strip API version prefixes (/api/v1, /api/ext/v1)
		originalPath := r.URL.Path
		p := r.URL.Path
		p = strings.TrimPrefix(p, "/api/v1")
		p = strings.TrimPrefix(p, "/api/ext/v1")
		if p == "" {
			p = "/"
		}
		r.URL.Path = p
		r.Host = targetURL.Host

		a.logger.Info("proxying request",
			"from", originalPath,
			"to", target+r.URL.Path,
		)

		proxy.ServeHTTP(w, r)
	}
}

// ═══════════════════════════════════════════════════════════
// JWT
// ═══════════════════════════════════════════════════════════

func (a *App) generateToken(subject, role string) (string, error) {
	claims := jwt.MapClaims{
		"sub":  subject,
		"role": role,
		"iat":  time.Now().Unix(),
		"exp":  time.Now().Add(24 * time.Hour).Unix(),
		"iss":  "omniverso-gateway",
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(a.config.JWTSecret))
}

// ═══════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]interface{}{
		"error":     http.StatusText(status),
		"message":   message,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

// ═══════════════════════════════════════════════════════════
// Main
// ═══════════════════════════════════════════════════════════

func main() {
	cfg := LoadConfig()

	app, err := NewApp(cfg)
	if err != nil {
		slog.Error("failed to initialize app", "error", err)
		os.Exit(1)
	}
	defer app.redis.Close()

	server := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      app.router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		app.logger.Info("OMNIVERSO Gateway starting", "port", cfg.Port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			app.logger.Error("server error", "error", err)
			os.Exit(1)
		}
	}()

	<-quit
	app.logger.Info("shutting down gracefully...")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		app.logger.Error("forced shutdown", "error", err)
	}

	app.logger.Info("OMNIVERSO Gateway stopped")
}
