# RenTA frontend source

This directory is the maintainable Vue 3/Vite source for `../frontend`, which is the production runtime served by the RenTA gateway.

## Development

```bash
npm ci
npm run dev
```

## Production build

```bash
npm run build:runtime
```

`build:runtime` builds the application, replaces hashed files under `../frontend/assets`, and updates the runtime entry point and required shared images. It preserves unrelated legacy static files in `../frontend` so existing external links are not broken.

The ACPs 02.01 registration extension is maintained in `public/assets/agent-apply-bridge.*`. Keep those source files and their generated copies under `../frontend/assets` synchronized; the bridge contains the certificate, AMQP, EAB, and 02.00 compatibility paths.
