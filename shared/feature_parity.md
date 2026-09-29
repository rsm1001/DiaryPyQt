# Desktop / Android feature parity

The desktop application and the Android app use different user interfaces; the Android app reads server data through the diary API and keeps an offline SQLite cache. The following describes **implemented features**, not a promise of verified device behavior.

| Feature | Desktop | Android | Remaining boundary |
| --- | --- | --- | --- |
| Create / edit / delete diaries | Available | Available, including offline outbox | Device acceptance pending |
| Search | Desktop text/date search | Cached text and tag search, plus inclusive date and view-count filters | Full-text indexing not yet ported |
| Import / export | JSON and CSV, local database | JSON export and confirmed JSON import, including desktop JSON-array input | Imported historical view counts and IDs are intentionally not restored; CSV transfer pending |
| Multiple selection / delete | Available | Available, uses existing offline outbox | Device acceptance pending |
| Tags | Available | Filter, create, rename, remove and diary editing | Batch tagging pending |
| View counts / weighted random | Available | Offline recorded views, weighted sampling with replacement | Lock-screen behavior must be tested on device |
| Statistics | Available | Server aggregates and cached local aggregates | Heatmap history unavailable: do not synthesize old per-day events |
| Trash | Available | Browse, restore, permanent deletion | Bulk restore pending |
| Audio / background | Available | Two-pass playback, background audio and offline cache | Bluetooth / lock-screen device acceptance pending |
| Sync | Controlled desktop review | Offline outbox and online refresh | Content conflict reconciliation still manual |

Import never overwrites an existing diary: identical date and content are skipped. It queues new local diaries atomically, but does not fake IDs or view histories from backup files. The app does not write directly to server SQLite.
