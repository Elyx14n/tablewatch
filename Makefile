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

# Describe blackjack topic
describe:
	docker exec tablewatch-kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic blackjack

# Consume messages (binary Avro)
consume:
	docker exec -it tablewatch-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic blackjack --from-beginning --max-messages 10

# Count messages in topic
count:
	docker exec tablewatch-kafka kafka-run-class kafka.tools.GetOffsetShell --bootstrap-server localhost:9092 --topic blackjack --time -1 | awk -F: '{sum += $$3} END {print "Total messages:", sum}'

# Delete and recreate topic
reset-topic:
	docker exec tablewatch-kafka kafka-topics --bootstrap-server localhost:9092 --delete --topic blackjack || true
	docker compose up -d kafka-setup

# List registered schemas in Schema Registry
schemas:
	curl -s http://localhost:8081/subjects | python -m json.tool

# Get schema for BetEvent
schema-bet:
	curl -s http://localhost:8081/subjects/blackjack-com.tablewatch.blackjack.BetEvent/versions/latest | python -m json.tool

# Get schema for CardDealtEvent
schema-card:
	curl -s http://localhost:8081/subjects/blackjack-com.tablewatch.blackjack.CardDealtEvent/versions/latest | python -m json.tool

# Get schema for OutcomeEvent
schema-outcome:
	curl -s http://localhost:8081/subjects/blackjack-com.tablewatch.blackjack.OutcomeEvent/versions/latest | python -m json.tool

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