# RenTA mq-auth-server integration

This directory contains the ACPs-community v2.1.0 `mq-auth-server` source adapted
to RenTA's Python 3.12 runtime. The application behavior and API contracts remain
the official implementation; the only source compatibility change is replacing
the Python 3.12-incompatible `type` alias statement.

RenTA starts this service only when `ACPS_MQ_AUTH_ENABLED=true`. Runtime material
is local and ignored by Git:

- `.env`: Redis, RabbitMQ Management API, and TLS paths.
- `.venv`: Python dependencies.
- `certs/`: CA-issued server and client certificates.
- `logs/` and PID files.

The service exposes mTLS Group API `9007` and RabbitMQ Auth API `9008`. It must be
started after Redis and before enabling RabbitMQ's HTTP authorization backend.
