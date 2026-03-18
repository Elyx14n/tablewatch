# Start all services
up:
	docker compose up -d --wait

# Stop and remove all services (keeps volumes)
down:
	docker compose down --remove-orphans

# Stop and remove all services AND wipe all volumes (full reset)
nuke:
	docker compose down -v --remove-orphans

# Show running containers
ps:
	docker compose ps

# List all Kafka topics
topics:
	docker exec tablewatch-kafka kafka-topics --bootstrap-server localhost:9092 --list

# Describe topics
describe:
	docker exec tablewatch-kafka kafka-topics --bootstrap-server localhost:9092 --describe

# Run the game simulation
run:
	python -m src.scripts.test_game

# View logs for all services
logs:
	docker compose logs -f

# List running Flink jobs
jobs:
	docker compose exec flink-jobmanager flink list -r