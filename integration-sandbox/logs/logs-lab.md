# Logs lab

## Scenario

Every integration step writes logs with the same `request_id`.

## Example log lines

```json
{"ts":"2026-06-18T12:00:00Z","level":"INFO","service":"order-api","request_id":"req-2026-0001","message":"POST /orders accepted","order_id":"ord-10001"}
{"ts":"2026-06-18T12:00:01Z","level":"INFO","service":"orders-db","request_id":"req-2026-0001","message":"order row inserted","order_id":"ord-10001"}
{"ts":"2026-06-18T12:00:02Z","level":"INFO","service":"events","request_id":"req-2026-0001","message":"order_created published","topic":"orders.events.v1"}
{"ts":"2026-06-18T12:00:03Z","level":"INFO","service":"delivery-soap","request_id":"req-2026-0001","message":"CreateDelivery called","order_id":"ord-10001"}
```

## Student tasks

1. Search all logs by `request_id`.
2. Restore the integration chain.
3. Find the failed step in a broken example.
4. Explain which team should investigate the problem.

## Questions

1. Why is request_id important?
2. What is the difference between business error and technical error?
3. What fields should analyst require in integration logs?
