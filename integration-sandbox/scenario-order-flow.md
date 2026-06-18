# Scenario: order processing integration flow

This scenario is used across all sandbox tabs.

## Business story

A customer creates an order. The platform must save it, publish an event, cache the status, attach a receipt file and send a delivery request to a legacy delivery system.

## End-to-end trace

Common correlation field: `request_id`.

Example:

```text
request_id = req-2026-0001
order_id = ord-10001
customer_id = usr-777
```

## Steps

1. Student sends `POST /orders` in Swagger.
2. Student checks that the order row appeared in the database.
3. Student checks Redis key `order:ord-10001:status` and its TTL.
4. Student opens Kafka event `order_created`.
5. Student uploads receipt or return photo into S3-like storage.
6. Student opens WSDL and sends SOAP delivery request.
7. Student searches logs by `request_id` and finds the whole chain.

## Learning outcomes

After this exercise the student should be able to explain:

- REST request and response structure;
- where transactional data is stored;
- why cache can be stale;
- why events are asynchronous;
- why files are stored in S3 and not directly in the database;
- how SOAP/WSDL describes operations and XML types;
- how request_id helps debug distributed systems.
