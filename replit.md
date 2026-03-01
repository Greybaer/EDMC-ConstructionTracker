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
- **Carrier Cargo**: A dictionary mapping resource names (lowercase, normalized) to quantities. Baseline set from CAPI `/fleetcarrier` endpoint (primary) or `FCMaterials.json` file (fallback on first load). Kept up-to-date incrementally via `CargoTransfer` journal events. Validated against ship cargo deltas for accuracy. Persisted to disk across EDMC restarts.
- **Ship Cargo**: A dictionary tracking the player's current ship inventory, updated from Cargo events (Inventory field or Cargo.json file). Used as ground truth to validate CargoTransfer amounts.
- **Pending Transfers**: A list buffering CargoTransfer events awaiting validation by the next Cargo event.
- **Selected Site**: Tracks which construction site the user is currently viewing via `selected_site_id`.

### Fleet Carrier Cargo Sources (in priority order)
1. **CAPI `/fleetcarrier` endpoint** (primary): Uses the `capi_fleetcarrier(data)` hook. EDMC queries Frontier's API when user opens Carrier Management UI in-game. Requires "Enable Fleetcarrier CAPI Queries" in EDMC Settings → Configuration. Handles multiple data formats: `data['cargo']` as a list (with `commodity`/`quantity` fields) or as a dict (with nested `commodities`/`items` arrays using `name`/`qty` fields). Also reads `orders.commodities.sales` for items listed for sale. Duplicate cargo entries are summed. Has a 15-minute cooldown between queries. **CAPI sanity check**: Before applying CAPI data, the total quantity of the incoming CAPI cargo is compared to the current carrier cargo total. If the CAPI total exceeds the current total (and current is non-zero), the CAPI data is discarded to prevent upward drift. CAPI data is always accepted when carrier cargo is empty (initial load).
2. **FCMaterials.json** (startup + periodic refresh): Always reloaded on plugin startup to get fresh baseline. Also reloaded on Docked/Market/Location/CarrierJump events if the file has been modified since the last read (tracks file modification time). A periodic timer checks every 15 minutes for file changes. Uses `Stock` field from `Items[]`.
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
- Color coding: green for completed materials (remaining = 0), orange for incomplete materials
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
- `ColonisationConstructionDepot` — Updates construction site data with full material requirements
- `ColonisationContribution` — Updates material delivery counts in real-time
- `CargoTransfer` — Incrementally adjusts carrier cargo (`tocarrier` adds, `toship` subtracts), buffers transfer for validation
- `Cargo` — Updates ship cargo inventory, validates any pending CargoTransfer amounts against actual ship delta, corrects carrier cargo if mismatched
- `Docked`, `Market`, `Location`, `CarrierJump` — Reloads FCMaterials.json if the file has been modified since last read (checks file modification time)

### Completion Calculation
`CompletionAmount = RequiredAmount - (ProvidedAmount + CarrierAmount + ShipAmount)` — This tells the player how much more of each material still needs to be collected. ShipAmount comes from the player's current ship inventory (`ship_cargo`). Materials turn green only when both remaining is zero AND provided equals or exceeds required (fully delivered), staying orange when carrier/ship cargo covers the gap but delivery is still pending.

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
- 51 tests covering core logic, event handling, CAPI data (list format, dict format, duplicate entries, sales orders, string values, empty data), CAPI sanity check (discard higher total, accept lower/equal total, allow when empty), ship cargo in remaining calculation, cargo event updates ship in construction sites, CargoTransfer tracking (tocarrier, toship, construction site updates), carrier cargo persistence, ship cargo tracking (Inventory and Cargo.json), CargoTransfer sanity check validation (tocarrier correction, toship correction, no-correction, multiple same-commodity transfers, mixed directions), FCMaterials loading, FCMaterials reload-on-modify, FCMaterials skip-if-not-modified, startup always reloads FCMaterials, name normalization, station name parsing, camel case splitting, editable carrier amounts (update, zero removal, invalid input), hide completed materials, persistence, site removal on full delivery (contribution completes, selects next site, depot arrives pre-completed)

## Recent Changes
- 2026-03-01: Construction sites automatically removed when all materials fully delivered (Provided >= Required); selects next available site if the removed site was selected
- 2026-03-01: Added Ship column to material table; remaining formula changed to `Required - (Provided + Carrier + Ship)` where Ship tracks player's current ship inventory of required materials
- 2026-03-01: Added CAPI sanity check: if CAPI cargo total exceeds current carrier cargo total (and current is non-zero), CAPI data is discarded to prevent upward drift
- 2026-02-24: Theme-aware text colors: Default theme uses black labels and value text; Dark/Transparent uses orange labels and white Type/System values
- 2026-02-24: Removed custom dark/light mode toggle, integrated with EDMC's native theme system via config.get_int('theme')
- 2026-02-21: FCMaterials.json always reloaded on startup for fresh baseline, not relying on stale persisted data
- 2026-02-21: Docked/Market/Location/CarrierJump events reload FCMaterials.json if file modified (tracks mtime)
- 2026-02-21: Added 15-minute periodic timer to check for FCMaterials.json changes and refresh carrier cargo
- 2026-02-21: Timer cleanup on plugin_stop to avoid orphaned callbacks
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
