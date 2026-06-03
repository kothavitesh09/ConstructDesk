# Phase 1 Performance Fix Report

## Files Changed

- `database/mongo.py`
  - Replaced request-scoped `MongoClient` creation with a single module-level global client.
  - Added a lock around first client creation to avoid duplicate clients during concurrent startup.
  - Removed the request teardown close helper.
- `app.py`
  - Removed the `close_client` import.
  - Removed `app.teardown_appcontext(close_client)`.

## Before Architecture

- Each request/app context called `get_client()`.
- `get_client()` stored `MongoClient` on Flask `g`.
- Flask teardown called `close_client()`.
- The MongoDB client and its connection pool were closed at the end of the request/app context.
- Result: connection pools could not be reused effectively across requests.

## After Architecture

- `database.mongo` owns one process-global `MongoClient`.
- `get_client()` lazily initializes that client once.
- All requests reuse the same MongoDB client's built-in connection pool.
- No Flask teardown closes the client after each request.
- Routes and services continue calling `get_db()` exactly as before.

## Risks

- The global client is process-scoped, so each server worker process will still have its own pool. This is expected behavior for PyMongo.
- Runtime changes to `MONGO_URI` after the first database access will not create a new client until the process restarts.
- The client is no longer explicitly closed per request; it should be closed by process shutdown. This is the intended PyMongo pooling model.

## Expected Performance Improvement

- Lower per-request latency by avoiding repeated `MongoClient` construction.
- Better connection reuse through PyMongo's connection pool.
- Reduced connection churn against MongoDB.
- More stable throughput under concurrent traffic because requests share warm pooled connections.
