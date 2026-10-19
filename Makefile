# Everyday commands. Run from the repository root.
SERVER = cd server &&
COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: up down migrate ingest pipeline train eval api worker web test lint llm export openapi

up:            ## start PostgreSQL (pgvector) and the private GPU Ollama
	$(COMPOSE) up -d db
	scripts/ollama-local.sh start

down:
	$(COMPOSE) down
	scripts/ollama-local.sh stop

migrate:
	$(SERVER) uv run alembic upgrade head

ingest:        ## gazetteer, the collected corpus, then today's RBI press releases
	$(SERVER) uv run finpulse gazetteer seed && uv run finpulse ingest corpus && uv run finpulse ingest rbi

pipeline:      ## every stage in order, one model on the GPU at a time
	$(SERVER) uv run finpulse pipeline

train:         ## classical baselines, then the neural models
	$(SERVER) uv run finpulse sentiment train --model tfidf && uv run finpulse ner train --model crf
	$(SERVER) uv run finpulse sentiment train --model finbert && uv run finpulse ner train --model transformer

eval:          ## score every stage against the gold passages
	$(SERVER) uv run finpulse gold eval --llm

api:
	$(SERVER) uv run finpulse serve

worker:
	$(SERVER) uv run finpulse worker

web:
	cd web && bun run dev

llm:           ## pull the two local models
	scripts/ollama-local.sh pull

export:        ## the DataPort package, annotations only
	$(SERVER) uv run finpulse export

openapi:       ## regenerate the API contract
	$(SERVER) uv run finpulse openapi

test:
	$(SERVER) uv run pytest
	cd web && bun run lint

lint:
	$(SERVER) uv run ruff check . && uv run ruff format --check .
