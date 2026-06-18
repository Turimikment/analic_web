# Redis cache lab

Scenario: order status is cached for fast reads.

Key example:

```text
order:ord-10001:status
```

Value example:

```json
{
  "order_id": "ord-10001",
  "status": "CREATED",
  "cached_at": "2026-06-18T12:00:05Z"
}
```

TTL: 60 seconds.

Student tasks:

1. Read order status from REST.
2. Compare it with database row.
3. Compare it with Redis value.
4. Explain why Redis may show old status for a short time.

Questions:

1. What is TTL?
2. Why can cache be stale?
3. What should analyst write in requirements: real time status or acceptable delay?
