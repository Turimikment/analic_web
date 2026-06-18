# Kafka sandbox

## Topic

```text
orders.events.v1
```

## Event: order_created

```json
{
  "event_id": "evt-0001",
  "event_type": "order_created",
  "request_id": "req-2026-0001",
  "order_id": "ord-10001",
  "customer_id": "usr-777",
  "created_at": "2026-06-18T12:00:00Z"
}
```

## What student should notice

- REST is synchronous: caller waits for response.
- Kafka event is asynchronous: consumers may process it later.
- `event_id` is needed for idempotency and duplicate detection.
- `request_id` connects REST request, database row, event and logs.

## Questions

1. What can happen if consumer receives the same event twice?
2. Why should event schema be stable?
3. Why is `order_created` better than vague `order_changed` for this case?
