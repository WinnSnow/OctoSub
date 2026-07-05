# OctoSub Frontend

Vite + React 19 frontend for the OctoSub dashboard.

## Commands

```bash
npm install
npm start
npm test
npm run build
```

- `npm start` starts Vite on `0.0.0.0`.
- `npm test` runs the Vitest suite once.
- `npm run build` writes the production build to `dist/`.

## Structure

```text
src/
├── api/          # axios client and domain-specific API functions
├── components/   # reusable UI and message components
├── pages/        # route-level page components
├── App.jsx       # layout and routes
└── index.jsx     # app entry
```

Pages should call functions from `src/api/` instead of importing `axios` directly. The shared client in `src/api/client.js` owns 401 handling.
