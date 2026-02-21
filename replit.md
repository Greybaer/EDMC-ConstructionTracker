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
- **Carrier Cargo**: A dictionary mapping resource names (lowercase, normalized) to quantities. Populated from CAPI `/fleetcarrier` endpoint (primary) or `FCMaterials.json` file (fallback).
- **Selected Site**: Tracks which construction site the user is currently viewing via `selected_site_id`.

### Fleet Carrier Cargo Sources (in priority order)
1. **CAPI `/fleetcarrier` endpoint** (primary): Uses the `capi_fleetcarrier(data)` hook. EDMC queries Frontier's API when user opens Carrier Management UI in-game. Requires "Enable Fleetcarrier CAPI Queries" in EDMC Settings → Configuration. Handles multiple data formats: `data['cargo']` as a list (with `commodity`/`quantity` fields) or as a dict (with nested `commodities`/`items` arrays using `name`/`qty` fields). Also reads `orders.commodities.sales` for items listed for sale. Duplicate cargo entries are summed. Has a 15-minute cooldown between queries.
2. **FCMaterials.json** (fallback): Read from the Elite Dangerous journal directory. Updated when the player opens their carrier's commodity market interface. Uses `Stock` field from `Items[]`. Triggered on Docked, Cargo, CargoTransfer, Market, Location, and CarrierJump journal events.

### Name Normalization
The `_normalize_name()` function handles all commodity name formats consistently:
- `$steel_name;` → `steel` (journal format: strips `$`, trailing `;`, and `_name` suffix)
- `Steel` → `steel` (CAPI format: lowercased)
- `steel` → `steel` (already normalized)

### Data Persistence
- **File**: `construction_tracker_data.json` stored in the plugin directory
- **Contents**: Construction sites, selected site ID, and dark mode preference
- **Strategy**: Loaded on startup, saved on every state change. This ensures data survives EDMC restarts.

### UI Architecture
- Built with **tkinter** (not ttk for key widgets, to enable full theming)
- `tk.OptionMenu` for site selection dropdown (replaced ttk.Combobox for better dark/light mode support)
- Type: and System: info lines below the site selector showing parsed station name components
- Grid-based material table showing Required, Provided, Carrier, and Remaining columns
- Color coding: green for completed materials (remaining = 0), orange for incomplete materials
- Dark/light mode toggle button that themes all widgets including headers, labels, buttons, material table, and combobox

### Station Name Parsing
Station names come in the format `$EXT_PANEL_SiteType;SiteName - SystemName;` and are parsed into three variables: `site_type`, `site_name`, and `system_name`. The `$EXT_PANEL_` prefix and trailing semicolons are trimmed.

### Journal Events Handled
- `ColonisationConstructionDepot` — Updates construction site data with full material requirements
- `ColonisationContribution` — Updates material delivery counts in real-time
- `Docked`, `Cargo`, `CargoTransfer`, `Market`, `Location`, `CarrierJump` — Triggers reload of Fleet Carrier cargo from `FCMaterials.json`

### Completion Calculation
`CompletionAmount = RequiredAmount - ProvidedAmount` — This tells the player how much more of each material is still needed. Carrier cargo is displayed as an informational column but does not factor into the remaining calculation.

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
- 24 tests covering core logic, event handling, CAPI data (list format, dict format, duplicate entries, sales orders, empty data), FCMaterials loading, name normalization, station name parsing, dark mode, persistence

## Recent Changes
- 2026-02-20: Added `capi_fleetcarrier(data)` hook to receive FC cargo from Frontier's Companion API
- 2026-02-20: Added Type: and System: display lines in the UI below site selector
- 2026-02-20: Improved name normalization with dedicated `_normalize_name()` function
- 2026-02-20: Added Market, Location, CarrierJump events as carrier cargo reload triggers
