# Start all services
up:
	docker compose up -d

# Stop and remove all services (including volumes)
down:
	docker compose down -v

# Show running containers
ps:
	docker compose ps

# List all Kafka topics
topics:
	docker exec tablewatch-kafka kafka-topics --bootstrap-server localhost:9092 --list

# Describe analytics topic
describe-analytics:
	docker exec tablewatch-kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic blackjack-analytics

# Describe visualization topic
describe-viz:
	docker exec tablewatch-kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic blackjack-visualization

# Consume analytics messages (binary Avro)
consume-analytics:
	docker exec -it tablewatch-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic blackjack-analytics --from-beginning --max-messages 10

# Consume visualization messages (binary Avro)
consume-viz:
	docker exec -it tablewatch-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic blackjack-visualization --from-beginning --max-messages 10

# Count messages in analytics topic
count-analytics:
	docker exec tablewatch-kafka kafka-run-class kafka.tools.GetOffsetShell --bootstrap-server localhost:9092 --topic blackjack-analytics --time -1 | awk -F: '{sum += $$3} END {print "Total messages:", sum}'

# Count messages in visualization topic
count-viz:
	docker exec tablewatch-kafka kafka-run-class kafka.tools.GetOffsetShell --bootstrap-server localhost:9092 --topic blackjack-visualization --time -1 | awk -F: '{sum += $$3} END {print "Total messages:", sum}'

# Delete and recreate topics
reset-topics:
	docker exec tablewatch-kafka kafka-topics --bootstrap-server localhost:9092 --delete --topic blackjack-analytics || true
	docker exec tablewatch-kafka kafka-topics --bootstrap-server localhost:9092 --delete --topic blackjack-visualization || true
	docker compose up -d kafka-setup

# List registered schemas in Schema Registry
schemas:
	curl -s http://localhost:8081/subjects | python -m json.tool

# Get schema for a specific subject
schema-bet:
	curl -s http://localhost:8081/subjects/blackjack-analytics-com.tablewatch.blackjack.BetEvent/versions/latest | python -m json.tool

# Run the game simulation
run:
	python -m src.scripts.test_game

# View logs for all services
logs:
	docker compose logs -f

# View Kafka logs only
logs-kafka:
	docker compose logs -f kafka

# View Schema Registry logs
logs-schema:
	docker compose logs -f schema-registry

# Restart Kafka UI (useful after config changes)
restart-ui:
	docker compose restart kafka-ui
