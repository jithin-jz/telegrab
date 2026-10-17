# Telegrab website

Marketing site and installation guide for Telegrab, live at https://telegrab.web.app.

Built with React, TypeScript, Vite and Tailwind CSS. Download links and the version number are read from the latest GitHub release at runtime.

## Development

```bash
npm ci
npm run dev     # http://localhost:5173
npm run lint
npm run build   # outputs to dist/
```

## Deployment

Every push to `main` that changes `website/` runs `.github/workflows/website.yml`, which lints, builds and deploys to Firebase Hosting (project `telegrab-app`, site `telegrab`). Hosting settings live in `firebase.json` at the repository root.

To deploy manually from the repository root:

```bash
npm --prefix website run build
firebase deploy --only hosting
```
