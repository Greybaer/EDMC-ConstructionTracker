# EDMC Construction Tracker Plugin

## Overview

This is an Elite Dangerous Market Connector (EDMC) plugin that tracks construction site material requirements for the System Colonisation feature in Elite Dangerous. When a player docks at a construction depot, the plugin monitors journal events to display material requirements, track deliveries, and show completion progress. It supports tracking multiple construction sites, reading Fleet Carrier cargo data via CAPI and FCMaterials.json, and provides a dark/light mode UI.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Plugin Structure
- **Entry Point**: `EDMCConstructionTracker/load.py` is the main plugin file that EDMC loads. It implements the standard EDMC plugin hooks: `plugin_start3`, `plugin_stop`, `plugin_app`, `journal_entry`, and `capi_fleetcarrier`.
- **Tests**: `test_plugin.py` contains unit tests that import directly from the plugin's `load.py` module.

### EDMC Plugin API
The plugin follows EDMC's plugin contract:
- `plugin_start3(plugin_dir)` — Initializes the plugin, loads persisted data, returns the plugin name
- `plugin_stop()` — Cleanup on shutdown
- `plugin_app(parent)` — Builds and returns the tkinter UI frame
- `journal_entry(cmdr, is_beta, system, station, entry, state)` — Processes game journal events in real-time
- `capi_fleetcarrier(data)` — Receives Fleet Carrier data from Frontier's Companion API (CAPI)

### Data Model
- **Construction Sites**: Stored in an in-memory dictionary keyed by `MarketID` (integer). Each site contains construction progress, resource requirements (required, provided, carrier amounts), station metadata, and parsed station name components (site_type, site_name, parsed_system).
- **Carrier Cargo**: A dictionary mapping resource names (lowercase, normalized) to quantities. Baseline set once at login from FCMaterials.json (via `LoadGame` event) or CAPI `/fleetcarrier` endpoint. After the initial baseline, only updated incrementally via `CargoTransfer` journal events. Validated against ship cargo deltas for accuracy. Persisted to disk across EDMC restarts.
- **Ship Cargo**: A dictionary tracking the player's current ship inventory, updated from Cargo events (Inventory field or Cargo.json file). Used as ground truth to validate CargoTransfer amounts.
- **Pending Transfers**: A list buffering CargoTransfer events awaiting validation by the next Cargo event.
- **Selected Site**: Tracks which construction site the user is currently viewing via `selected_site_id`.

### Fleet Carrier Cargo Sources (in priority order)
1. **CAPI `/fleetcarrier` endpoint** (first query only): Uses the `capi_fleetcarrier(data)` hook. EDMC queries Frontier's API when user opens Carrier Management UI in-game. Requires "Enable Fleetcarrier CAPI Queries" in EDMC Settings → Configuration. Only the first CAPI query per session is accepted — it fully replaces carrier cargo data. All subsequent CAPI queries are ignored. Handles multiple data formats: `data['cargo']` as a list (with `commodity`/`quantity` fields) or as a dict (with nested `commodities`/`items` arrays using `name`/`qty` fields). Also reads `orders.commodities.sales` for items listed for sale. Duplicate cargo entries are summed. The `capi_received` flag resets on `LoadGame` so each game session gets one fresh CAPI baseline.
2. **FCMaterials.json** (startup + login): Loaded on plugin startup and on `LoadGame` journal event to establish a fresh baseline. Uses `Stock` field from `Items[]`.
3. **CargoTransfer journal events** (incremental updates): Tracks `tocarrier` and `toship` transfers in real-time, adjusting the carrier cargo baseline up or down. Each transfer is buffered as a pending validation until the next Cargo event confirms the ship inventory changed by the expected amount. If there's a mismatch, carrier cargo is auto-corrected based on the actual ship delta.

### Name Normalization
The `_normalize_name()` function handles all commodity name formats consistently:
- `$steel_name;` → `steel` (journal format: strips `$`, trailing `;`, and `_name` suffix)
- `Steel` → `steel` (CAPI format: lowercased)
- `steel` → `steel` (already normalized)

### Data Persistence
- **File**: `construction_tracker_data.json` stored in the plugin directory
- **Contents**: Construction sites, selected site ID, hide-completed preference, and carrier cargo inventory
- **Strategy**: Loaded on startup, saved on every state change. This ensures data survives EDMC restarts.

### UI Architecture
- Built with **tkinter** (not ttk for key widgets, to enable full theming)
- `tk.OptionMenu` for site selection dropdown
- Type: and System: info lines below the site selector showing parsed station name components
- Grid-based material table showing Required, Provided, Carrier, Ship, and Remaining columns
- Color coding: green for fully delivered (remaining=0, provided>=required), yellow/goldenrod (#daa520) for pending delivery (remaining=0 but carrier>0, not yet delivered), light blue (#4dc8ff) for incomplete materials available at the docked station's market, orange for incomplete materials
- Theme-aware colors via `_is_dark_theme()` helper (reads `config.get_int('theme')`), refreshed on every `_update_display()` call:
  - **Default theme (0)**: Labels (Title, Site, Type, System, Progress, material headers) are black; Type/System value strings are black; Progress value is black
  - **Dark (1) / Transparent (2) themes**: Labels are orange (#ff8c00); Type/System value strings are white; Progress value is white
- EDMC's native theme module handles widget backgrounds automatically; plugin registers widgets via `_register_with_theme()`
- "Hide completed materials" checkbox in EDMC Settings tab (Construction Tracker) with data persistence

### Station Name Parsing
Station names come in two formats, both parsed into three variables: `site_type`, `site_name`, and `system_name`:
1. `$EXT_PANEL_SiteType;SiteName - SystemName;` — The `$EXT_PANEL_` prefix and trailing semicolons are trimmed, type extracted from first segment.
2. `Type: SiteName - SystemName` — Plain text with colon separator, used when the game provides localized station names without the `$EXT_PANEL_` format. Type is extracted from before the colon.
The `_split_camel_case()` function splits CamelCase type names (e.g., "OrbitalStation" → "Orbital Station") for display.

### Journal Events Handled
- `LoadGame` — Reloads carrier cargo from FCMaterials.json to establish a fresh baseline at login
- `ColonisationConstructionDepot` — Updates construction site data with full material requirements
- `ColonisationContribution` — Updates material delivery counts in real-time
- `CargoTransfer` — Incrementally adjusts carrier cargo (`tocarrier` adds, `toship` subtracts), buffers transfer for validation
- `Cargo` — Updates ship cargo inventory, validates any pending CargoTransfer amounts against actual ship delta, corrects carrier cargo if mismatched
- `Market` — Loads station commodity list from Market.json; materials available at the docked station display in light blue
- `Undocked` — Clears station commodity data so market-based highlighting reverts to default colors

### Completion Calculation
`CompletionAmount = RequiredAmount - (ProvidedAmount + CarrierAmount + ShipAmount)` — This tells the player how much more of each material still needs to be collected. Materials turn green only when both remaining is zero AND provided equals or exceeds required (fully delivered), yellow/goldenrod when remaining is zero but carrier has stock (pending delivery), staying orange when incomplete.

### Site Auto-Removal
When all materials at a construction site have `provided >= required`, the site is automatically removed from the dataset. This triggers after `ColonisationContribution` events and `ColonisationConstructionDepot` events. If the removed site was the selected site, selection switches to the next available site (or clears if none remain).

### Journal Directory Detection
Uses EDMC's config module (`config.get_str('journaldir')` or `config.default_journal_dir`) to find the Elite Dangerous journal directory where `FCMaterials.json` is located.

## External Dependencies

### Runtime Dependencies
- **EDMC (Elite Dangerous Market Connector)** — The host application that loads this plugin. Provides the plugin API hooks, config module for journal directory, CAPI data, and the parent tkinter window.
- **tkinter** — Python's built-in GUI toolkit, used for all UI rendering. No additional UI libraries needed.
- **Frontier Companion API (CAPI)** — Accessed through EDMC's `capi_fleetcarrier` hook. Provides authoritative Fleet Carrier cargo data.
- **Elite Dangerous Journal Files** — The plugin reads game journal events passed through EDMC and reads `FCMaterials.json` from the journal directory as a fallback for Fleet Carrier cargo data.

### No External Packages
The plugin uses only Python standard library modules (`json`, `os`, `logging`, `typing`, `tkinter`). There are no pip dependencies or package manager requirements. The plugin runs entirely within the EDMC process.

### Testing
- Tests use Python's built-in `unittest.mock` and `tempfile` modules
- Tests import the plugin module directly and reset state between test cases
- No test framework beyond the standard library is required
- 54 tests covering core logic, event handling, CAPI data (list format, dict format, duplicate entries, sales orders, empty data, first-query replace, subsequent-queries ignored, capacity not parsed from CAPI), CarrierStats free space calculation, CargoTransfer tracking (tocarrier, toship, construction site updates), carrier cargo persistence, ship cargo tracking (Inventory and Cargo.json), ship cargo in completion calculation, Cargo event updates ship amounts in sites, sanity check validation (tocarrier correction, toship correction, no-correction, multiple same-commodity transfers, mixed directions), FCMaterials loading, LoadGame carrier reload, Docked does not reload, startup always reloads FCMaterials, name normalization, station name parsing, camel case splitting, editable carrier amounts (update, zero removal, invalid input), hide completed materials, persistence, site auto-removal (on contribution, on depot event, incomplete not removed, selected site switches), market commodity loading, undocked clears commodities, market commodities affect material highlighting

## Recent Changes
- 2026-03-14: Remaining Cargo Space: label now sourced from CarrierStats journal event using TotalCapacity - CargoReserved - Cargo; CAPI no longer used for capacity
- 2026-03-13: Added Fleet Carrier Capacity row to UI showing current cargo load vs total capacity (sourced from CAPI)
- 2026-03-04: Construction sites auto-removed when all materials fully delivered (provided >= required)
- 2026-03-04: Pending delivery color: yellow/goldenrod (#daa520) for materials with remaining=0 but carrier > 0
- 2026-03-04: Added Ship column to material table showing player's current ship inventory per material
- 2026-03-04: Remaining formula changed to `required - (provided + carrier + ship)` to include ship cargo
- 2026-03-04: Cargo events now update ship amounts in construction site materials and refresh display
- 2026-03-01: Carrier cargo now loaded once at login (LoadGame event) then updated only via CargoTransfer; removed periodic timer and Docked/Market/Location/CarrierJump reload triggers to reduce drift
- 2026-02-24: Theme-aware text colors: Default theme uses black labels and value text; Dark/Transparent uses orange labels and white Type/System values
- 2026-02-24: Removed custom dark/light mode toggle, integrated with EDMC's native theme system via config.get_int('theme')
- 2026-02-21: Remaining formula changed to `required - (provided + carrier)`, green color requires both remaining=0 and provided>=required
- 2026-02-21: Added ship cargo tracking from Cargo events (Inventory field and Cargo.json fallback)
- 2026-02-21: Added sanity check: validates CargoTransfer amounts against ship cargo deltas, auto-corrects carrier cargo on mismatch
- 2026-02-21: Carrier cargo now tracked incrementally via CargoTransfer events (tocarrier/toship)
- 2026-02-21: Carrier cargo persisted to save file, survives EDMC restarts
- 2026-02-21: FCMaterials.json only loaded as initial baseline (not reloaded on every event)
- 2026-02-21: Remaining calculation changed to `Required - Provided` (carrier is informational only)
- 2026-02-20: Added `capi_fleetcarrier(data)` hook to receive FC cargo from Frontier's Companion API
- 2026-02-20: Added Type: and System: display lines in the UI below site selector
- 2026-02-20: Improved name normalization with dedicated `_normalize_name()` function
- 2026-02-20: Added Market, Location, CarrierJump events as carrier cargo reload triggers
