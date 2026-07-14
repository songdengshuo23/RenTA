# RenTA Cloud Deployment Files

These files describe the non-secret cloud deployment used by the target host.

## Assumptions

- Application root: `/opt/renta`
- Python environments: `/opt/renta/venv/*`
- Runtime secrets and URLs: `/opt/renta/runtime/*/.env`
- PostgreSQL, Redis, and RabbitMQ run locally.
- Nginx exposes the primary HTTP entry point on port `80` and proxies the
  existing gateway on `127.0.0.1:8888`. Port `8888` remains available for
  backward compatibility.

Copy the `.service` and `.target` files to `/etc/systemd/system/`, then run:

```bash
systemctl daemon-reload
systemctl enable renta.target
systemctl start renta.target
```

Install and configure the public HTTP entry point before starting the target:

```bash
dnf install -y nginx
cp -a /etc/nginx/nginx.conf /etc/nginx/nginx.conf.package-default
install -m 0644 deployment/cloud/nginx/nginx.conf /etc/nginx/nginx.conf
install -D -m 0644 deployment/cloud/nginx/renta.conf /etc/nginx/conf.d/renta.conf
nginx -t
firewall-cmd --permanent --zone=public --add-service=http
firewall-cmd --reload
systemctl enable --now nginx
```

After deployment, both `http://SERVER_IP/` and
`http://SERVER_IP:8888/` serve the same RenTA homepage and API gateway.

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
