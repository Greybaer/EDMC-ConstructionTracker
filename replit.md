# EDMC Construction Tracker Plugin

## Overview

This is an Elite Dangerous Market Connector (EDMC) plugin that tracks construction site material requirements for the System Colonisation feature in Elite Dangerous. When a player docks at a construction depot, the plugin monitors journal events to display material requirements, track deliveries, and show completion progress. It supports tracking multiple construction sites, reading Fleet Carrier cargo data, and provides a dark/light mode UI.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Plugin Structure
- **Entry Point**: `EDMCConstructionTracker/load.py` is the main plugin file that EDMC loads. It implements the standard EDMC plugin hooks: `plugin_start3`, `plugin_stop`, `plugin_app`, and `journal_entry`.
- **Tests**: `test_plugin.py` contains unit tests that import directly from the plugin's `load.py` module.

### EDMC Plugin API
The plugin follows EDMC's plugin contract:
- `plugin_start3(plugin_dir)` — Initializes the plugin, loads persisted data, returns the plugin name
- `plugin_stop()` — Cleanup on shutdown
- `plugin_app(parent)` — Builds and returns the tkinter UI frame
- `journal_entry(cmdr, is_beta, system, station, entry, state)` — Processes game journal events in real-time

### Data Model
- **Construction Sites**: Stored in an in-memory dictionary keyed by `MarketID` (integer). Each site contains construction progress, resource requirements (required, provided, carrier amounts), station metadata, and parsed station name components.
- **Carrier Cargo**: A dictionary mapping resource names (lowercase, cleaned) to quantities, read from the game's `FCMaterials.json` file (using the `Stock` field).
- **Selected Site**: Tracks which construction site the user is currently viewing via `selected_site_id`.

### Data Persistence
- **File**: `construction_tracker_data.json` stored in the plugin directory
- **Contents**: Construction sites, selected site ID, and dark mode preference
- **Strategy**: Loaded on startup, saved on every state change. This ensures data survives EDMC restarts.

### UI Architecture
- Built with **tkinter** (not ttk for key widgets, to enable full theming)
- `tk.OptionMenu` for site selection dropdown (replaced ttk.Combobox for better dark/light mode support)
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
`CompletionAmount = RequiredAmount - (ProvidedAmount + CarrierAmount)` — This tells the player how much more of each material is still needed.

### Journal Directory Detection
Uses EDMC's config module (`config.get_str('journaldir')` or `config.default_journal_dir`) to find the Elite Dangerous journal directory where `FCMaterials.json` is located.

## External Dependencies

### Runtime Dependencies
- **EDMC (Elite Dangerous Market Connector)** — The host application that loads this plugin. Provides the plugin API hooks, config module for journal directory, and the parent tkinter window.
- **tkinter** — Python's built-in GUI toolkit, used for all UI rendering. No additional UI libraries needed.
- **Elite Dangerous Journal Files** — The plugin reads game journal events passed through EDMC and directly reads `FCMaterials.json` from the journal directory for Fleet Carrier cargo data.

### No External Packages
The plugin uses only Python standard library modules (`json`, `os`, `logging`, `typing`, `tkinter`). There are no pip dependencies or package manager requirements. The plugin runs entirely within the EDMC process.

### Testing
- Tests use Python's built-in `unittest.mock` and `tempfile` modules
- Tests import the plugin module directly and reset state between test cases
- No test framework beyond the standard library is required