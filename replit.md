# EDMC Construction Tracker Plugin

## Overview
An Elite Dangerous Market Connector (EDMC) plugin that tracks construction site material requirements for the System Colonisation feature. It monitors journal events when docking at construction depots, tracks Fleet Carrier cargo, and displays material progress in a tkinter UI within EDMC.

## Project Structure
```
EDMCConstructionTracker/
  load.py                              - Main plugin file (EDMC entry point)
  construction_tracker_data.json       - Persistent data file (auto-generated)
test_plugin.py                         - Unit tests for plugin logic
```

## Key Features
- Tracks multiple construction sites via dropdown selector
- Monitors ColonisationConstructionDepot and ColonisationContribution journal events
- Reads Fleet Carrier cargo from Cargo.json for CarrierAmount
- Calculates CompletionAmount = RequiredAmount - (ProvidedAmount + CarrierAmount)
- Displays material table with Required, Provided, Carrier, Remaining columns
- Updates in real-time as materials are delivered
- Trims $EXT_PANEL_ prefix from station names in dropdown display
- Reloads carrier cargo on every Docked event
- Dark/Light mode toggle with full widget theming (header, labels, button, material table, combobox)
- Persistent data storage across EDMC restarts (construction sites, selected site, dark mode preference)

## Architecture
- **Plugin API**: Uses EDMC plugin_start3, plugin_stop, plugin_app, journal_entry hooks
- **Data Storage**: In-memory dictionary keyed by MarketID, persisted to JSON file in plugin directory
- **Persistence**: construction_tracker_data.json stores construction sites, selected site ID, and dark mode preference; loaded on startup, saved on every state change
- **UI**: tkinter with ttk.Combobox for site selection, grid-based material table, dark/light mode toggle
- **Carrier Tracking**: Reads Cargo.json from Elite Dangerous journal directory on Docked, Cargo, and CargoTransfer events

## Recent Changes
- 2026-02-20: Added full widget theming - all UI elements (header, labels, button, combobox) follow dark/light mode
- 2026-02-20: Added persistent data storage across EDMC restarts
- 2026-02-20: Added $EXT_PANEL_ prefix trimming from station display names
- 2026-02-20: Added Docked event handler to reload carrier cargo on every dock
- 2026-02-20: Added dark mode toggle button with themed colors for material display
- 2026-02-20: Initial plugin creation with full MVP feature set

## Testing
Run `python test_plugin.py` to execute all unit tests (16 tests covering core logic, event handling, cargo loading, name trimming, docked event, dark mode, persistence save/load, and restart persistence).
