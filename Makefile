.PHONY: up down logs build

# Start the entire stack with 2 worker replicas and force rebuild
up:
	docker-compose up --build --scale worker=2

# Start the stack in the background (detached)
up-d:
	docker-compose up -d --build --scale worker=2

# Stop and remove containers
down:
	docker-compose down

# Tail logs for gateway and workers
logs:
	docker-compose logs -f gateway worker

# Rebuild images explicitly without starting
build:
	docker-compose build
