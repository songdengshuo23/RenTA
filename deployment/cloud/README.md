# RenTA Cloud Deployment Files

These files describe the non-secret cloud deployment used by the target host.

## Assumptions

- Application root: `/opt/renta`
- Python environments: `/opt/renta/venv/*`
- Runtime secrets and URLs: `/opt/renta/runtime/*/.env`
- PostgreSQL, Redis, and RabbitMQ run locally.

Copy the `.service` and `.target` files to `/etc/systemd/system/`, then run:

```bash
systemctl daemon-reload
systemctl enable renta.target
systemctl start renta.target
```

`mq-auth-production.toml` supplements the source production settings by keeping
the MQ Auth HTTP listeners on loopback. Copy it to
`sds/mq-auth-server/config/production.toml` only after preserving the source
cache settings already present in that file.

RabbitMQ must enable these plugins in addition to the standard broker package:

```bash
rabbitmq-plugins enable rabbitmq_management rabbitmq_auth_backend_http \
  rabbitmq_auth_backend_cache rabbitmq_auth_mechanism_ssl
```

The SSL mechanism plugin is required for AMQPS client certificates to negotiate
the ACPs v2.1 `EXTERNAL` SASL mechanism.
