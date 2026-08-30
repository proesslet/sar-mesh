# SARMesh UI

React + TypeScript, built by Vite straight into `../src/sarmesh/web/static` so a
wheel ships the UI as ordinary static files. Nothing Node-related runs in
production.

```
npm run dev            # Vite dev server, proxying /api /events /tiles to :8000
npm run build          # tsc -b && vite build, into the Python package
npm run lint           # oxlint
npm run format         # prettier --write .
```

Run the backend alongside `npm run dev` with `sarmesh app --offline --browser`,
which serves stored data without needing a radio attached.

## Layout

| Directory        | Holds                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------- |
| `api/`           | `types.ts` mirrors the server's models; `client.ts` is the only place that talks HTTP |
| `hooks/`         | Reusable stateful behaviour, not tied to one screen                                   |
| `lib/`           | Pure functions -- formatting, error text, derived views                               |
| `components/`    | Presentation shared across features                                                   |
| `components/ui/` | The primitives every screen builds from                                               |
| `features/`      | One directory per area of the app: trackers, teams, incidents, settings               |
| `map/`           | Everything Leaflet-facing                                                             |

## Conventions

**Styling is CSS Modules.** `index.css` is the only global stylesheet, and it
holds nothing but the design tokens and the page reset. Everything else lives in
a `*.module.css` beside the component that uses it, so a class name cannot
collide with one somewhere else. Colours come from the `--` custom properties;
do not hardcode hex values outside `index.css`.

**Build from the primitives in `components/ui/`** -- `Section`, `Field`, `Form`,
`Actions`, `Button`, `CopyButton`, `List`, `Message` -- rather than restyling a
bare `<button>` or `<input>`. Reach for a new primitive when a pattern turns up
in a third place, not on its first.

**External URLs are shown, not linked.** The desktop build hosts the UI in a
bare `QWebEngineView` with no `createWindow` override, so `target="_blank"` does
nothing and a same-window link navigates the app off its own interface with no
way back. Render a URL as `<code>` beside a `CopyButton`, the way the Files and
About panels do.

**Mutations go through `useAsyncAction`.** It owns the `busy` flag, the error
message and the try/catch, so a failed request can never leave a dialog stuck
busy. Call `run(action, onSuccess)`; `onSuccess` fires only when the action
resolved.

**Server state is refetched, never patched.** The server decides what is active,
so after a change a dialog calls its `onChanged` prop and lets `useOverview`
re-read rather than editing local copies. This is why deletes return the
remaining records.

**Elapsed time takes a `now` argument.** Components get it from `useNow` instead
of calling `Date.now()` as they render, so a label depends on the tick interval
rather than on when React happened to re-render.

## Adding a screen

To add a **settings category**, write the panel in `features/settings/` and add
an entry to `CATEGORIES` in `SettingsModal.tsx`. Panels there stay mounted and
are hidden when not selected, so switching category cannot abandon work in
progress -- a map pack import runs for minutes and unmounting would abort it.

To add a **screen**:
create `features/<area>/`, build the UI from `components/ui/`, add any new
endpoint to `api/client.ts` and its shape to `api/types.ts`, and mount it from
`App.tsx`. If it is a dialog, add its name to the `OpenDialog` union there --
only one dialog is open at a time.
