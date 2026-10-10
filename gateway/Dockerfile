# ─── Build Stage ──────────────────────────────────────────
FROM golang:1.24-alpine AS builder

RUN apk add --no-cache git ca-certificates

WORKDIR /build
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o gateway .

# ─── Runtime Stage ────────────────────────────────────────
FROM alpine:3.21

RUN apk add --no-cache ca-certificates wget
RUN adduser -D -u 1000 appuser

COPY --from=builder /build/gateway /usr/local/bin/gateway

USER appuser
EXPOSE 8080

ENTRYPOINT ["gateway"]
