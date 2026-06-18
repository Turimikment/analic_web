# Integration sandbox

A safe training area for future system analysts.

Goal: let students see how REST, SOAP/WSDL, database, Kafka, Redis, S3 and logs look in one realistic business scenario.

Business case: order processing.

Flow:
1. REST API creates an order.
2. Database stores order state.
3. Redis caches fast order status.
4. Kafka publishes order_created event.
5. S3 stores receipt, return photo or document.
6. SOAP/WSDL sends delivery request to legacy delivery system.
7. Logs connect all steps by request_id.

The module is not about DevOps administration. It is about understanding contracts, payloads, storage responsibilities, integration errors and troubleshooting.
