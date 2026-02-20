# EDMC Construction Tracker Plugin

## Overview
An Elite Dangerous Market Connector (EDMC) plugin that tracks construction site material requirements for the System Colonisation feature. It monitors journal events when docking at construction depots, tracks Fleet Carrier cargo, and displays material progress in a tkinter UI within EDMC.

## Project Structure
```
EDMCConstructionTracker/
  load.py          - Main plugin file (EDMC entry point)
test_plugin.py     - Unit tests for plugin logic
```

## Key Features
- Tracks multiple construction sites via dropdown selector
- Monitors ColonisationConstructionDepot and ColonisationContribution journal events
- Reads Fleet Carrier cargo from Cargo.json for CarrierAmount
- Calculates CompletionAmount = RequiredAmount - (ProvidedAmount + CarrierAmount)
- Displays material table with Required, Provided, Carrier, Remaining columns
- Updates in real-time as materials are delivered

## Architecture
- **Plugin API**: Uses EDMC plugin_start3, plugin_stop, plugin_app, journal_entry hooks
- **Data Storage**: In-memory dictionary keyed by MarketID for each construction site
- **UI**: tkinter with ttk.Combobox for site selection, grid-based material table
- **Carrier Tracking**: Reads Cargo.json from Elite Dangerous journal directory

## Recent Changes
- 2026-02-20: Initial plugin creation with full MVP feature set

## Testing
Run `python test_plugin.py` to execute all unit tests (9 tests covering core logic, event handling, cargo loading, and display name generation).
