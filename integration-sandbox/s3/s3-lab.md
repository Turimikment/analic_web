# S3 object storage lab

## Scenario

A customer attaches a receipt or return photo to an order.

The file itself is stored in object storage. The database stores only metadata and `object_key`.

## Object key example

```text
orders/ord-10001/files/receipt.pdf
returns/ord-10001/photos/damage-001.jpg
```

## Metadata example

```json
{
  "order_id": "ord-10001",
  "object_key": "orders/ord-10001/files/receipt.pdf",
  "file_name": "receipt.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 245000
}
```

## Student tasks

1. Upload a file in the sandbox UI.
2. Find the object key.
3. Find the database row with metadata.
4. Explain why binary file content is not stored directly in the order row.
5. Explain what can go wrong if a bucket is public.

## Questions

1. What is bucket?
2. What is object key?
3. What should be stored in database?
4. Why do systems use signed links for downloads?
