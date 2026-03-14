import json
import os
import sys
import tempfile
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "EDMCConstructionTracker"))

os.environ["DISPLAY"] = ""

try:
    import tkinter as tk
    HAS_TK = True
except (ImportError, RuntimeError):
    HAS_TK = False

import load as plugin

_test_tmpdir = tempfile.mkdtemp()


def _reset_plugin():
    plugin.construction_sites.clear()
    plugin.carrier_cargo.clear()
    plugin.ship_cargo.clear()
    plugin.pending_transfers.clear()
    plugin.station_commodities.clear()
    plugin.selected_site_id = None
    plugin.hide_completed_materials = False
    plugin.capi_received = False
    plugin.carrier_free_space = None
    plugin.plugin_dir = _test_tmpdir
    save_path = os.path.join(_test_tmpdir, plugin.SAVE_FILE)
    if os.path.exists(save_path):
        os.remove(save_path)


def test_plugin_start():
    result = plugin.plugin_start3(_test_tmpdir)
    assert result == "Construction Tracker", f"Expected 'Construction Tracker', got '{result}'"
    print("[PASS] plugin_start3 returns correct name")


def test_construction_depot_processing():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100, "ceramiccomposites": 50}

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 12345,
        "ConstructionProgress": 0.45,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 500,
                "ProvidedAmount": 200,
                "Payment": 3239,
            },
            {
                "Name": "$ceramiccomposites_name;",
                "Name_Localised": "Ceramic Composites",
                "RequiredAmount": 300,
                "ProvidedAmount": 100,
                "Payment": 724,
            },
        ],
    }

    plugin._process_construction_depot(entry, "Test Station", "Test System")

    assert 12345 in plugin.construction_sites
    site = plugin.construction_sites[12345]
    assert site["display_name"] == "Test Station"
    assert site["progress"] == 0.45
    assert len(site["materials"]) == 2

    alum = site["materials"][0]
    assert alum["name"] == "Aluminium"
    assert alum["required"] == 500
    assert alum["provided"] == 200
    assert alum["carrier"] == 100
    assert alum["completion"] == 200

    ceramic = site["materials"][1]
    assert ceramic["carrier"] == 50
    assert ceramic["completion"] == 150

    print("[PASS] Construction depot processing with carrier amounts")


def test_multiple_sites():
    _reset_plugin()

    entry1 = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 111,
        "ConstructionProgress": 0.3,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 100,
                "ProvidedAmount": 30,
                "Payment": 1000,
            }
        ],
    }

    entry2 = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 222,
        "ConstructionProgress": 0.7,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 200,
                "ProvidedAmount": 140,
                "Payment": 500,
            }
        ],
    }

    plugin._process_construction_depot(entry1, "Alpha Station", "Alpha System")
    plugin._process_construction_depot(entry2, "Beta Outpost", "Beta System")

    assert len(plugin.construction_sites) == 2
    assert 111 in plugin.construction_sites
    assert 222 in plugin.construction_sites
    assert plugin.construction_sites[111]["display_name"] == "Alpha Station"
    assert plugin.construction_sites[222]["display_name"] == "Beta Outpost"
    assert plugin.selected_site_id == 222

    print("[PASS] Multiple construction sites tracked correctly")


def test_completion_amount_calculation():
    assert plugin._calculate_completion(500, 200, 100) == 200
    assert plugin._calculate_completion(500, 400, 100) == 0
    assert plugin._calculate_completion(500, 300, 300) == 0
    assert plugin._calculate_completion(100, 0, 0) == 100
    assert plugin._calculate_completion(100, 100, 0) == 0
    assert plugin._calculate_completion(100, 50, 50) == 0
    assert plugin._calculate_completion(100, 80, 30) == 0

    print("[PASS] CompletionAmount calculation (never goes negative)")


def test_carrier_cargo_update():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 0}

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 999,
        "ConstructionProgress": 0.5,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 200,
                "ProvidedAmount": 50,
                "Payment": 1000,
            }
        ],
    }
    plugin._process_construction_depot(entry, "Test", "System")

    assert plugin.construction_sites[999]["materials"][0]["completion"] == 150

    plugin.carrier_cargo = {"aluminium": 80}
    plugin._update_carrier_amounts()

    mat = plugin.construction_sites[999]["materials"][0]
    assert mat["carrier"] == 80
    assert mat["completion"] == 70

    print("[PASS] Carrier cargo update recalculates CompletionAmount")


def test_contribution_updates():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 50}

    depot_entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 555,
        "ConstructionProgress": 0.2,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 400,
                "ProvidedAmount": 80,
                "Payment": 1000,
            }
        ],
    }
    plugin._process_construction_depot(depot_entry, "Depot", "System")

    mat = plugin.construction_sites[555]["materials"][0]
    assert mat["provided"] == 80
    assert mat["completion"] == 270

    contrib_entry = {
        "event": "ColonisationContribution",
        "MarketID": 555,
        "Contributions": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "Amount": 20,
            }
        ],
    }

    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "System", "Depot", contrib_entry, state)

    mat = plugin.construction_sites[555]["materials"][0]
    assert mat["provided"] == 100
    assert mat["completion"] == 250

    print("[PASS] ColonisationContribution updates ProvidedAmount and recalculates CompletionAmount")


def test_fc_materials_loading():
    with tempfile.TemporaryDirectory() as tmpdir:
        fc_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "FCMaterials",
            "MarketID": 3700005632,
            "CarrierName": "TEST CARRIER",
            "CarrierID": "T7T-TTT",
            "Items": [
                {"id": 1, "Name": "$aluminium_name;", "Name_Localised": "Aluminium",
                 "Stock": 120, "Demand": 0, "BuyPrice": 0, "SellPrice": 0},
                {"id": 2, "Name": "$steel_name;", "Name_Localised": "Steel",
                 "Stock": 80, "Demand": 0, "BuyPrice": 0, "SellPrice": 0},
                {"id": 3, "Name": "$polymers_name;", "Name_Localised": "Polymers",
                 "Stock": 45, "Demand": 0, "BuyPrice": 0, "SellPrice": 0},
                {"id": 4, "Name": "$gold_name;", "Name_Localised": "Gold",
                 "Stock": 0, "Demand": 100, "BuyPrice": 0, "SellPrice": 0},
            ],
        }
        with open(os.path.join(tmpdir, "FCMaterials.json"), "w") as f:
            json.dump(fc_data, f)

        plugin.journal_dir = tmpdir
        plugin.carrier_cargo.clear()
        plugin._load_carrier_cargo()

        assert plugin.carrier_cargo.get("aluminium") == 120
        assert plugin.carrier_cargo.get("steel") == 80
        assert plugin.carrier_cargo.get("polymers") == 45
        assert plugin.carrier_cargo.get("gold", 0) == 0

    print("[PASS] FCMaterials.json loading works correctly")


def test_display_name_generation():
    assert plugin._get_site_display_name("Station", "System", 1) == "Station"
    assert plugin._get_site_display_name("Station", None, 1) == "Station"
    assert plugin._get_site_display_name(None, "System", 1) == "Site #1"
    assert plugin._get_site_display_name(None, None, 42) == "Site #42"

    print("[PASS] Display name generation")


def test_normalize_name():
    assert plugin._normalize_name("$aluminium_name;") == "aluminium"
    assert plugin._normalize_name("$steel_name;") == "steel"
    assert plugin._normalize_name("Steel") == "steel"
    assert plugin._normalize_name("steel") == "steel"
    assert plugin._normalize_name("$polymers_name;") == "polymers"
    assert plugin._normalize_name("polymers") == "polymers"
    assert plugin._normalize_name("$ceramiccomposites_name;") == "ceramiccomposites"
    assert plugin._normalize_name("  $Gold_Name;  ") == "gold"
    assert plugin._normalize_name("") == ""

    print("[PASS] Name normalization handles all formats")


def test_parse_station_name():
    site_type, site_name, system_name = plugin._parse_station_name("$EXT_PANEL_ColDepot;My Station - Sol;")
    assert site_type == "ColDepot", f"Expected 'ColDepot', got '{site_type}'"
    assert site_name == "My Station", f"Expected 'My Station', got '{site_name}'"
    assert system_name == "Sol", f"Expected 'Sol', got '{system_name}'"

    site_type, site_name, system_name = plugin._parse_station_name("$EXT_PANEL_Hub;Alpha Base - Barnard's Star;")
    assert site_type == "Hub"
    assert site_name == "Alpha Base"
    assert system_name == "Barnard's Star"

    site_type, site_name, system_name = plugin._parse_station_name("Normal Station")
    assert site_type == ""
    assert site_name == "Normal Station"
    assert system_name == ""

    site_type, site_name, system_name = plugin._parse_station_name("$EXT_PANEL_ColDepot;")
    assert site_type == ""
    assert site_name == "ColDepot"
    assert system_name == ""

    site_type, site_name, system_name = plugin._parse_station_name("$EXT_PANEL_Outpost;My Outpost - Alpha Centauri;")
    assert site_type == "Outpost"
    assert site_name == "My Outpost"
    assert system_name == "Alpha Centauri"

    site_type, site_name, system_name = plugin._parse_station_name("Orbital Construction Site: Kubokawa Sanctuary")
    assert site_type == "Orbital Construction Site", f"Expected 'Orbital Construction Site', got '{site_type}'"
    assert site_name == "Kubokawa Sanctuary", f"Expected 'Kubokawa Sanctuary', got '{site_name}'"
    assert system_name == ""

    site_type, site_name, system_name = plugin._parse_station_name("Surface Port: Dawes Landing - Sol")
    assert site_type == "Surface Port", f"Expected 'Surface Port', got '{site_type}'"
    assert site_name == "Dawes Landing", f"Expected 'Dawes Landing', got '{site_name}'"
    assert system_name == "Sol", f"Expected 'Sol', got '{system_name}'"

    print("[PASS] Station name parsing into site type, site, and system")


def test_display_name_with_ext_panel():
    _reset_plugin()

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 777,
        "ConstructionProgress": 0.5,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [],
    }
    plugin._process_construction_depot(entry, "$EXT_PANEL_ColDepot;My Station - Sol;", "Sol")
    assert plugin.construction_sites[777]["display_name"] == "My Station"
    assert plugin.construction_sites[777]["site_type"] == "ColDepot"
    assert plugin.construction_sites[777]["site_name"] == "My Station"
    assert plugin.construction_sites[777]["parsed_system"] == "Sol"

    print("[PASS] Display name extracts site name from $EXT_PANEL_ format")


def test_docked_event_does_not_reload_carrier_cargo():
    with tempfile.TemporaryDirectory() as tmpdir:
        fc_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "FCMaterials",
            "Items": [
                {"id": 1, "Name": "$aluminium_name;", "Stock": 200, "Demand": 0,
                 "BuyPrice": 0, "SellPrice": 0},
            ],
        }
        with open(os.path.join(tmpdir, "FCMaterials.json"), "w") as f:
            json.dump(fc_data, f)

        plugin.journal_dir = tmpdir
        plugin.carrier_cargo = {"steel": 500}

        docked_entry = {"event": "Docked", "StationName": "Test", "MarketID": 99999}
        state = {"JournalDir": tmpdir}
        plugin.journal_entry("Cmdr", False, "Sys", "Stn", docked_entry, state)

        assert plugin.carrier_cargo.get("steel") == 500
        assert "aluminium" not in plugin.carrier_cargo

    print("[PASS] Docked event does not reload carrier cargo")


def test_capi_fleetcarrier_cargo_list_format():
    _reset_plugin()

    depot_entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 6000,
        "ConstructionProgress": 0.1,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 500,
                "ProvidedAmount": 100,
                "Payment": 1000,
            },
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 300,
                "ProvidedAmount": 50,
                "Payment": 500,
            },
        ],
    }
    plugin._process_construction_depot(depot_entry, "Test Station", "Test System")

    capi_data = {
        "name": {"callsign": "T3S-T0P", "name": "TEST CARRIER"},
        "currentStarSystem": "Sol",
        "cargo": [
            {"commodity": "Aluminium", "quantity": 200},
            {"commodity": "Steel", "quantity": 150},
        ],
        "orders": {"commodities": {"sales": {}, "purchases": {}}},
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("aluminium") == 200
    assert plugin.carrier_cargo.get("steel") == 150

    mat_alum = plugin.construction_sites[6000]["materials"][0]
    assert mat_alum["carrier"] == 200
    assert mat_alum["completion"] == 200

    mat_steel = plugin.construction_sites[6000]["materials"][1]
    assert mat_steel["carrier"] == 150
    assert mat_steel["completion"] == 100

    print("[PASS] CAPI fleetcarrier cargo list format populates carrier amounts")


def test_capi_fleetcarrier_cargo_dict_format():
    _reset_plugin()

    capi_data = {
        "cargo": {
            "capacity": 25000,
            "qty": 200,
            "commodities": [
                {"name": "Aluminium", "qty": 200},
            ],
        },
        "orders": {"commodities": {"sales": {}, "purchases": {}}},
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("aluminium") == 200

    print("[PASS] CAPI fleetcarrier cargo dict format fallback works")


def test_capi_fleetcarrier_cargo_duplicate_entries():
    _reset_plugin()

    capi_data = {
        "cargo": [
            {"commodity": "Aluminium", "quantity": 200},
            {"commodity": "Aluminium", "quantity": 100},
            {"commodity": "Steel", "quantity": 50},
        ],
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("aluminium") == 300
    assert plugin.carrier_cargo.get("steel") == 50

    print("[PASS] CAPI fleetcarrier sums duplicate cargo entries")


def test_capi_fleetcarrier_sales_orders():
    _reset_plugin()

    capi_data = {
        "cargo": [],
        "orders": {
            "commodities": {
                "sales": {
                    "100": {"id": 128049204, "name": "Gold", "outstanding": 500, "price": 9500, "total": 1000, "blackMarket": False},
                    "101": {"id": 128049168, "name": "Aluminium", "outstanding": 300, "price": 340, "total": 500, "blackMarket": False},
                },
                "purchases": {},
            }
        },
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("gold") == 500
    assert plugin.carrier_cargo.get("aluminium") == 300

    print("[PASS] CAPI fleetcarrier sales orders populate carrier amounts")


def test_capi_fleetcarrier_string_values():
    _reset_plugin()

    capi_data = {
        "cargo": [
            {"commodity": "Aluminium", "quantity": "200"},
            {"commodity": "Steel", "quantity": "150"},
        ],
        "orders": {
            "commodities": {
                "sales": {
                    "100": {"name": "Gold", "outstanding": "500"},
                },
                "purchases": {},
            }
        },
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("aluminium") == 200
    assert plugin.carrier_cargo.get("steel") == 150
    assert plugin.carrier_cargo.get("gold") == 500

    print("[PASS] CAPI fleetcarrier handles string quantity values")


def test_capi_fleetcarrier_empty_data():
    _reset_plugin()
    plugin.carrier_cargo = {"old_item": 100}

    plugin.capi_fleetcarrier(None)
    assert plugin.carrier_cargo.get("old_item") == 100
    assert plugin.capi_received is False

    capi_data = {"cargo": [], "orders": {"commodities": {"sales": {}, "purchases": {}}}}
    plugin.capi_fleetcarrier(capi_data)
    assert plugin.carrier_cargo.get("old_item") is None
    assert plugin.capi_received is True

    print("[PASS] CAPI fleetcarrier handles empty/null data")


def test_capi_fleetcarrier_first_query_replaces_cargo():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 500, "steel": 100}

    capi_data = {
        "cargo": [
            {"commodity": "Aluminium", "quantity": 200},
            {"commodity": "Gold", "quantity": 50},
        ],
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("aluminium") == 200
    assert plugin.carrier_cargo.get("gold") == 50
    assert "steel" not in plugin.carrier_cargo
    assert plugin.capi_received is True

    print("[PASS] CAPI fleetcarrier first query fully replaces carrier cargo")


def test_capi_fleetcarrier_subsequent_queries_ignored():
    _reset_plugin()

    first_data = {
        "cargo": [
            {"commodity": "Aluminium", "quantity": 200},
        ],
    }
    plugin.capi_fleetcarrier(first_data)
    assert plugin.carrier_cargo.get("aluminium") == 200

    second_data = {
        "cargo": [
            {"commodity": "Aluminium", "quantity": 999},
            {"commodity": "Steel", "quantity": 500},
        ],
    }
    plugin.capi_fleetcarrier(second_data)

    assert plugin.carrier_cargo.get("aluminium") == 200
    assert "steel" not in plugin.carrier_cargo

    print("[PASS] CAPI fleetcarrier ignores subsequent queries")


def test_capi_fleetcarrier_capacity_parsed():
    _reset_plugin()

    capi_data = {
        "cargo": [
            {"commodity": "Aluminium", "quantity": 500},
            {"commodity": "Steel", "quantity": 300},
        ],
        "capacity": {
            "capacity": 25000,
            "freeSpace": 24200,
            "usedSpace": 800,
            "reservedSpace": 0,
        },
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_free_space is None, "CAPI should not set carrier_free_space"
    assert plugin.carrier_cargo.get("aluminium") == 500
    assert plugin.carrier_cargo.get("steel") == 300

    print("[PASS] CAPI fleetcarrier capacity parsed correctly")


def test_carrier_stats_sets_free_space():
    _reset_plugin()

    entry = {
        "event": "CarrierStats",
        "SpaceUsage": {
            "TotalCapacity": 25000,
            "Crew": 930,
            "Cargo": 1050,
            "CargoReserved": 200,
            "ShipPacks": 0,
            "ModulePacks": 0,
            "FreeSpace": 22820,
            "Services": 0,
            "Reserved": 1000,
        },
    }
    plugin.journal_entry("Cmdr", False, "Sol", "", entry, {})

    assert plugin.carrier_free_space == 25000 - 200 - 1050, (
        f"Expected {25000 - 200 - 1050}, got {plugin.carrier_free_space}"
    )

    print("[PASS] CarrierStats event sets carrier free space correctly")


def test_cargo_transfer_to_carrier():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100}

    entry = {
        "event": "CargoTransfer",
        "Transfers": [
            {"Type": "$aluminium_name;", "Type_Localised": "Aluminium", "Count": 50, "Direction": "tocarrier"},
            {"Type": "$steel_name;", "Type_Localised": "Steel", "Count": 200, "Direction": "tocarrier"},
        ],
    }
    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", entry, state)

    assert plugin.carrier_cargo.get("aluminium") == 150
    assert plugin.carrier_cargo.get("steel") == 200

    print("[PASS] CargoTransfer tocarrier adds to carrier cargo")


def test_cargo_transfer_to_ship():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100, "steel": 50}

    entry = {
        "event": "CargoTransfer",
        "Transfers": [
            {"Type": "$aluminium_name;", "Type_Localised": "Aluminium", "Count": 30, "Direction": "toship"},
            {"Type": "$steel_name;", "Type_Localised": "Steel", "Count": 50, "Direction": "toship"},
        ],
    }
    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", entry, state)

    assert plugin.carrier_cargo.get("aluminium") == 70
    assert "steel" not in plugin.carrier_cargo

    print("[PASS] CargoTransfer toship removes from carrier cargo")


def test_cargo_transfer_updates_construction_site():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100}

    depot_entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 7000,
        "ConstructionProgress": 0.1,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {"Name": "$aluminium_name;", "Name_Localised": "Aluminium",
             "RequiredAmount": 500, "ProvidedAmount": 100, "Payment": 1000},
        ],
    }
    plugin._process_construction_depot(depot_entry, "Test", "System")

    mat = plugin.construction_sites[7000]["materials"][0]
    assert mat["carrier"] == 100

    transfer_entry = {
        "event": "CargoTransfer",
        "Transfers": [
            {"Type": "$aluminium_name;", "Type_Localised": "Aluminium", "Count": 50, "Direction": "tocarrier"},
        ],
    }
    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", transfer_entry, state)

    mat = plugin.construction_sites[7000]["materials"][0]
    assert plugin.carrier_cargo.get("aluminium") == 150
    assert mat["carrier"] == 150

    print("[PASS] CargoTransfer updates construction site carrier amounts")


def test_carrier_cargo_persisted():
    _reset_plugin()
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin.plugin_dir = tmpdir
        plugin.carrier_cargo = {"aluminium": 500, "steel": 300}
        plugin._save_data()

        plugin.carrier_cargo.clear()
        assert len(plugin.carrier_cargo) == 0

        plugin._load_data()
        assert plugin.carrier_cargo.get("aluminium") == 500
        assert plugin.carrier_cargo.get("steel") == 300

    print("[PASS] Carrier cargo is persisted across save/load")


def test_loadgame_reloads_carrier_cargo():
    _reset_plugin()
    with tempfile.TemporaryDirectory() as tmpdir:
        fc_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "FCMaterials",
            "Items": [
                {"id": 1, "Name": "$gold_name;", "Stock": 200, "Demand": 0,
                 "BuyPrice": 0, "SellPrice": 0},
            ],
        }
        with open(os.path.join(tmpdir, "FCMaterials.json"), "w") as f:
            json.dump(fc_data, f)

        plugin.journal_dir = tmpdir
        plugin.carrier_cargo = {"aluminium": 999}

        entry = {"event": "LoadGame", "Commander": "TestCmdr"}
        state = {"JournalDir": tmpdir}
        plugin.journal_entry("Cmdr", False, "Sys", "Stn", entry, state)

        assert plugin.carrier_cargo.get("gold") == 200
        assert "aluminium" not in plugin.carrier_cargo

    print("[PASS] LoadGame event reloads carrier cargo from FCMaterials.json")


def test_startup_always_reloads_fc_materials():
    with tempfile.TemporaryDirectory() as tmpdir:
        save_data = {
            "selected_site_id": None,
            "construction_sites": {},
            "carrier_cargo": {"aluminium": 500, "steel": 200},
        }
        with open(os.path.join(tmpdir, plugin.SAVE_FILE), "w") as f:
            json.dump(save_data, f)

        fc_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "FCMaterials",
            "Items": [
                {"id": 1, "Name": "$aluminium_name;", "Stock": 300, "Demand": 0,
                 "BuyPrice": 0, "SellPrice": 0},
            ],
        }
        with open(os.path.join(tmpdir, "FCMaterials.json"), "w") as f:
            json.dump(fc_data, f)

        plugin.journal_dir = tmpdir
        plugin.plugin_start3(tmpdir)

        assert plugin.carrier_cargo.get("aluminium") == 300
        assert "steel" not in plugin.carrier_cargo

    print("[PASS] Startup always reloads FCMaterials.json over persisted data")


def test_cargo_event_updates_ship_cargo():
    _reset_plugin()

    entry = {
        "event": "Cargo",
        "Vessel": "Ship",
        "Inventory": [
            {"Name": "gold", "Count": 50, "Stolen": 0},
            {"Name": "silver", "Count": 30, "Stolen": 0},
            {"Name": "gold", "MissionID": 12345, "Count": 10, "Stolen": 0},
        ],
    }
    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", entry, state)

    assert plugin.ship_cargo.get("gold") == 60
    assert plugin.ship_cargo.get("silver") == 30

    print("[PASS] Cargo event updates ship cargo from Inventory")


def test_cargo_event_reads_cargo_json():
    _reset_plugin()
    with tempfile.TemporaryDirectory() as tmpdir:
        cargo_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "Cargo",
            "Vessel": "Ship",
            "Inventory": [
                {"Name": "aluminium", "Count": 100, "Stolen": 0},
            ],
        }
        with open(os.path.join(tmpdir, "Cargo.json"), "w") as f:
            json.dump(cargo_data, f)

        plugin.journal_dir = tmpdir

        entry = {"event": "Cargo", "Vessel": "Ship", "Count": 100}
        state = {"JournalDir": tmpdir}
        plugin.journal_entry("Cmdr", False, "Sys", "Stn", entry, state)

        assert plugin.ship_cargo.get("aluminium") == 100

    print("[PASS] Cargo event reads Cargo.json when Inventory not in event")


def test_sanity_check_corrects_tocarrier():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100}
    plugin.ship_cargo = {"aluminium": 200}

    transfer_entry = {
        "event": "CargoTransfer",
        "Transfers": [
            {"Type": "aluminium", "Count": 50, "Direction": "tocarrier"},
        ],
    }
    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", transfer_entry, state)

    assert plugin.carrier_cargo.get("aluminium") == 150
    assert len(plugin.pending_transfers) == 1

    cargo_entry = {
        "event": "Cargo",
        "Vessel": "Ship",
        "Inventory": [
            {"Name": "aluminium", "Count": 170, "Stolen": 0},
        ],
    }
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", cargo_entry, state)

    assert plugin.carrier_cargo.get("aluminium") == 130
    assert len(plugin.pending_transfers) == 0

    print("[PASS] Sanity check corrects tocarrier when ship delta mismatches")


def test_sanity_check_corrects_toship():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100}
    plugin.ship_cargo = {"aluminium": 50}

    transfer_entry = {
        "event": "CargoTransfer",
        "Transfers": [
            {"Type": "aluminium", "Count": 30, "Direction": "toship"},
        ],
    }
    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", transfer_entry, state)

    assert plugin.carrier_cargo.get("aluminium") == 70
    assert len(plugin.pending_transfers) == 1

    cargo_entry = {
        "event": "Cargo",
        "Vessel": "Ship",
        "Inventory": [
            {"Name": "aluminium", "Count": 70, "Stolen": 0},
        ],
    }
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", cargo_entry, state)

    assert plugin.carrier_cargo.get("aluminium") == 80
    assert len(plugin.pending_transfers) == 0

    print("[PASS] Sanity check corrects toship when ship delta mismatches")


def test_sanity_check_no_correction_needed():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100}
    plugin.ship_cargo = {"aluminium": 200}

    transfer_entry = {
        "event": "CargoTransfer",
        "Transfers": [
            {"Type": "aluminium", "Count": 50, "Direction": "tocarrier"},
        ],
    }
    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", transfer_entry, state)

    assert plugin.carrier_cargo.get("aluminium") == 150

    cargo_entry = {
        "event": "Cargo",
        "Vessel": "Ship",
        "Inventory": [
            {"Name": "aluminium", "Count": 150, "Stolen": 0},
        ],
    }
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", cargo_entry, state)

    assert plugin.carrier_cargo.get("aluminium") == 150
    assert len(plugin.pending_transfers) == 0

    print("[PASS] Sanity check makes no correction when transfer is accurate")


def test_sanity_check_multiple_transfers_same_commodity():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100}
    plugin.ship_cargo = {"aluminium": 300}

    transfer1 = {
        "event": "CargoTransfer",
        "Transfers": [
            {"Type": "aluminium", "Count": 50, "Direction": "tocarrier"},
        ],
    }
    transfer2 = {
        "event": "CargoTransfer",
        "Transfers": [
            {"Type": "aluminium", "Count": 30, "Direction": "tocarrier"},
        ],
    }
    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", transfer1, state)
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", transfer2, state)

    assert plugin.carrier_cargo.get("aluminium") == 180
    assert len(plugin.pending_transfers) == 2

    cargo_entry = {
        "event": "Cargo",
        "Vessel": "Ship",
        "Inventory": [
            {"Name": "aluminium", "Count": 220, "Stolen": 0},
        ],
    }
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", cargo_entry, state)

    assert plugin.carrier_cargo.get("aluminium") == 180
    assert len(plugin.pending_transfers) == 0

    print("[PASS] Sanity check handles multiple transfers of same commodity correctly")


def test_sanity_check_mixed_directions():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 200}
    plugin.ship_cargo = {"aluminium": 100}

    transfer1 = {
        "event": "CargoTransfer",
        "Transfers": [
            {"Type": "aluminium", "Count": 50, "Direction": "tocarrier"},
        ],
    }
    transfer2 = {
        "event": "CargoTransfer",
        "Transfers": [
            {"Type": "aluminium", "Count": 20, "Direction": "toship"},
        ],
    }
    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", transfer1, state)
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", transfer2, state)

    assert plugin.carrier_cargo.get("aluminium") == 230
    assert len(plugin.pending_transfers) == 2

    cargo_entry = {
        "event": "Cargo",
        "Vessel": "Ship",
        "Inventory": [
            {"Name": "aluminium", "Count": 70, "Stolen": 0},
        ],
    }
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", cargo_entry, state)

    assert plugin.carrier_cargo.get("aluminium") == 230
    assert len(plugin.pending_transfers) == 0

    print("[PASS] Sanity check handles mixed tocarrier/toship transfers correctly")




def test_journal_entry_cargo_event():
    _reset_plugin()
    plugin.carrier_cargo = {"gold": 50}

    cargo_entry = {
        "event": "Cargo",
        "Vessel": "Ship",
        "Count": 2,
        "Inventory": [
            {"Name": "gold", "Count": 10},
            {"Name": "silver", "Count": 5},
        ],
    }
    state = {"JournalDir": _test_tmpdir}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", cargo_entry, state)

    assert plugin.ship_cargo.get("gold") == 10
    assert plugin.ship_cargo.get("silver") == 5
    assert plugin.carrier_cargo.get("gold") == 50

    print("[PASS] journal_entry handles Cargo event")


def test_save_and_load_data():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100}
    plugin.hide_completed_materials = True

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 8888,
        "ConstructionProgress": 0.6,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 500,
                "ProvidedAmount": 200,
                "Payment": 1000,
            }
        ],
    }
    plugin._process_construction_depot(entry, "Persist Station", "Persist System")

    save_path = os.path.join(_test_tmpdir, plugin.SAVE_FILE)
    assert os.path.exists(save_path), "Save file should exist after processing depot"

    with open(save_path, "r") as f:
        saved = json.load(f)
    assert saved["hide_completed_materials"] is True
    assert saved["selected_site_id"] == 8888
    assert "8888" in saved["construction_sites"]
    assert saved["construction_sites"]["8888"]["display_name"] == "Persist Station"

    plugin.construction_sites.clear()
    plugin.selected_site_id = None
    plugin.hide_completed_materials = False

    plugin._load_data()

    assert plugin.hide_completed_materials is True
    assert plugin.selected_site_id == 8888
    assert 8888 in plugin.construction_sites
    site = plugin.construction_sites[8888]
    assert site["display_name"] == "Persist Station"
    assert site["progress"] == 0.6
    assert len(site["materials"]) == 1
    assert site["materials"][0]["name"] == "Aluminium"
    assert site["materials"][0]["required"] == 500
    assert site["materials"][0]["provided"] == 200

    print("[PASS] Data persistence: save and load works correctly")


def test_persistence_across_restart():
    _reset_plugin()
    plugin.carrier_cargo = {"steel": 75}
    plugin.hide_completed_materials = True

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 4444,
        "ConstructionProgress": 0.3,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 300,
                "ProvidedAmount": 100,
                "Payment": 500,
            }
        ],
    }
    plugin._process_construction_depot(entry, "Restart Station", "Restart System")

    plugin.plugin_stop()

    plugin.construction_sites.clear()
    plugin.selected_site_id = None
    plugin.hide_completed_materials = False

    result = plugin.plugin_start3(_test_tmpdir)
    assert result == "Construction Tracker"

    assert plugin.hide_completed_materials is True
    assert plugin.selected_site_id == 4444
    assert 4444 in plugin.construction_sites
    site = plugin.construction_sites[4444]
    assert site["display_name"] == "Restart Station"

    print("[PASS] Data persists across plugin stop/start cycle")



def test_split_camel_case():
    assert plugin._split_camel_case("OrbitalStation") == "Orbital Station"
    assert plugin._split_camel_case("CivilianOutpost") == "Civilian Outpost"
    assert plugin._split_camel_case("Station") == "Station"
    assert plugin._split_camel_case("") == ""
    assert plugin._split_camel_case("ABC") == "A B C"
    assert plugin._split_camel_case("MiningAndRefinery") == "Mining And Refinery"

    print("[PASS] _split_camel_case splits on capital letters correctly")


def test_carrier_edit_updates_cargo():
    _reset_plugin()

    plugin.carrier_cargo = {"steel": 50}
    plugin.construction_sites[5555] = {
        "display_name": "Test Site",
        "market_id": 5555,
        "progress": 0.5,
        "complete": False,
        "failed": False,
        "materials": [
            {
                "name": "Steel",
                "name_key": "steel",
                "required": 300,
                "provided": 100,
                "carrier": 50,
                "completion": 150,
            }
        ],
        "station": "Test",
        "system": "TestSys",
        "site_type": "OrbitalStation",
        "site_name": "Test Site",
        "parsed_system": "TestSys",
    }
    plugin.selected_site_id = 5555

    mat = plugin.construction_sites[5555]["materials"][0]
    var = type('MockVar', (), {'get': lambda self: '200'})()
    plugin._on_carrier_edit("steel", var, 2, mat)

    assert plugin.carrier_cargo.get("steel") == 200
    assert mat["carrier"] == 200
    assert mat["completion"] == 0

    print("[PASS] Manual carrier edit updates cargo and recalculates remaining")


def test_carrier_edit_zero_removes_from_cargo():
    _reset_plugin()

    plugin.carrier_cargo = {"steel": 50}
    mat = {
        "name": "Steel",
        "name_key": "steel",
        "required": 300,
        "provided": 100,
        "carrier": 50,
        "completion": 150,
    }

    var = type('MockVar', (), {'get': lambda self: '0'})()
    plugin._on_carrier_edit("steel", var, 2, mat)

    assert "steel" not in plugin.carrier_cargo
    assert mat["carrier"] == 0
    assert mat["completion"] == 200

    print("[PASS] Carrier edit to zero removes commodity from carrier cargo")


def test_carrier_edit_invalid_input_ignored():
    _reset_plugin()

    plugin.carrier_cargo = {"steel": 50}
    mat = {
        "name": "Steel",
        "name_key": "steel",
        "required": 300,
        "provided": 100,
        "carrier": 50,
        "completion": 150,
    }

    var = type('MockVar', (), {'get': lambda self: 'abc'})()
    plugin._on_carrier_edit("steel", var, 2, mat)

    assert plugin.carrier_cargo.get("steel") == 50
    assert mat["carrier"] == 50
    assert mat["completion"] == 150

    print("[PASS] Invalid carrier edit input is ignored")


def test_hide_completed_materials():
    _reset_plugin()
    plugin.hide_completed_materials = False

    plugin.construction_sites[7777] = {
        "display_name": "Test Site",
        "market_id": 7777,
        "progress": 0.5,
        "complete": False,
        "failed": False,
        "materials": [
            {"name": "Steel", "name_key": "steel", "required": 100, "provided": 100, "carrier": 0, "completion": 0},
            {"name": "Aluminium", "name_key": "aluminium", "required": 200, "provided": 50, "carrier": 0, "completion": 150},
        ],
        "system": "Sol",
        "station": "Test",
        "site_type": "Starport",
        "site_name": "Test",
        "parsed_system": "Sol",
    }
    plugin.selected_site_id = 7777

    materials = plugin.construction_sites[7777]["materials"]
    completed = [m for m in materials if m["completion"] == 0 and m["provided"] >= m["required"]]
    incomplete = [m for m in materials if not (m["completion"] == 0 and m["provided"] >= m["required"])]
    assert len(completed) == 1
    assert len(incomplete) == 1
    assert completed[0]["name"] == "Steel"
    assert incomplete[0]["name"] == "Aluminium"

    plugin._set_hide_completed(True)
    assert plugin.hide_completed_materials is True

    plugin._set_hide_completed(False)
    assert plugin.hide_completed_materials is False

    print("[PASS] Hide completed materials setting toggles correctly")


def test_ship_cargo_affects_completion():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100}
    plugin.ship_cargo = {"aluminium": 50}

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 9999,
        "ConstructionProgress": 0.2,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 500,
                "ProvidedAmount": 200,
                "Payment": 1000,
            },
        ],
    }
    plugin._process_construction_depot(entry, "Ship Test", "Sol")

    mat = plugin.construction_sites[9999]["materials"][0]
    assert mat["ship"] == 50
    assert mat["carrier"] == 100
    assert mat["completion"] == 150

    plugin.ship_cargo = {"aluminium": 100}
    plugin._update_ship_amounts()
    mat = plugin.construction_sites[9999]["materials"][0]
    assert mat["ship"] == 100
    assert mat["completion"] == 100

    print("[PASS] Ship cargo affects completion calculation")


def test_cargo_event_updates_ship_amounts_in_sites():
    _reset_plugin()
    plugin.carrier_cargo = {"steel": 50}

    depot_entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 8888,
        "ConstructionProgress": 0.1,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 300,
                "ProvidedAmount": 100,
                "Payment": 500,
            },
        ],
    }
    plugin._process_construction_depot(depot_entry, "Cargo Test", "Sol")

    mat = plugin.construction_sites[8888]["materials"][0]
    assert mat["ship"] == 0
    assert mat["completion"] == 150

    cargo_entry = {
        "event": "Cargo",
        "Vessel": "Ship",
        "Count": 1,
        "Inventory": [
            {"Name": "steel", "Count": 75},
        ],
    }
    state = {"JournalDir": _test_tmpdir}
    plugin.journal_entry("Cmdr", False, "Sys", "Stn", cargo_entry, state)

    mat = plugin.construction_sites[8888]["materials"][0]
    assert mat["ship"] == 75
    assert mat["completion"] == 75

    print("[PASS] Cargo event updates ship amounts in construction sites")


def test_hide_completed_persisted():
    _reset_plugin()
    plugin.hide_completed_materials = False
    plugin._set_hide_completed(True)

    save_path = os.path.join(_test_tmpdir, plugin.SAVE_FILE)
    with open(save_path, "r") as f:
        saved = json.load(f)
    assert saved["hide_completed_materials"] is True

    plugin._set_hide_completed(False)
    with open(save_path, "r") as f:
        saved = json.load(f)
    assert saved["hide_completed_materials"] is False

    print("[PASS] Hide completed materials setting persists correctly")



def test_complete_site_removed_on_contribution():
    _reset_plugin()
    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 5555,
        "ConstructionProgress": 0.9,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 100,
                "ProvidedAmount": 90,
                "Payment": 500,
            },
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 50,
                "ProvidedAmount": 50,
                "Payment": 300,
            },
        ],
    }
    plugin._process_construction_depot(entry, "Test Site", "Sol")
    assert 5555 in plugin.construction_sites

    contrib_entry = {
        "event": "ColonisationContribution",
        "MarketID": 5555,
        "Contributions": [
            {"Name": "$steel_name;", "Amount": 10},
        ],
    }
    state = {"JournalDir": _test_tmpdir}
    plugin.journal_entry("Cmdr", False, "Sol", "Test Site", contrib_entry, state)

    assert 5555 not in plugin.construction_sites
    print("[PASS] Complete construction site removed after contribution")


def test_complete_site_removed_on_depot_event():
    _reset_plugin()
    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 6666,
        "ConstructionProgress": 1.0,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 100,
                "ProvidedAmount": 100,
                "Payment": 500,
            },
        ],
    }
    state = {"JournalDir": _test_tmpdir}
    plugin.journal_entry("Cmdr", False, "Sol", "Test Site", entry, state)

    assert 6666 not in plugin.construction_sites
    print("[PASS] Complete construction site removed on depot event")


def test_incomplete_site_not_removed():
    _reset_plugin()
    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 7777,
        "ConstructionProgress": 0.5,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 100,
                "ProvidedAmount": 50,
                "Payment": 500,
            },
        ],
    }
    plugin._process_construction_depot(entry, "Test Site", "Sol")
    assert 7777 in plugin.construction_sites
    print("[PASS] Incomplete construction site not removed")


def test_selected_site_switches_on_removal():
    _reset_plugin()
    entry1 = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 1111,
        "ConstructionProgress": 0.5,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 100,
                "ProvidedAmount": 50,
                "Payment": 500,
            },
        ],
    }
    plugin._process_construction_depot(entry1, "Site A", "Sol")

    entry2 = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 2222,
        "ConstructionProgress": 0.9,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 50,
                "ProvidedAmount": 40,
                "Payment": 300,
            },
        ],
    }
    plugin._process_construction_depot(entry2, "Site B", "Alpha Centauri")
    assert plugin.selected_site_id == 2222

    contrib_entry = {
        "event": "ColonisationContribution",
        "MarketID": 2222,
        "Contributions": [
            {"Name": "$aluminium_name;", "Amount": 10},
        ],
    }
    state = {"JournalDir": _test_tmpdir}
    plugin.journal_entry("Cmdr", False, "Alpha Centauri", "Site B", contrib_entry, state)

    assert 2222 not in plugin.construction_sites
    assert 1111 in plugin.construction_sites
    assert plugin.selected_site_id == 1111
    print("[PASS] Selected site switches to remaining site on removal")


def test_startup_removes_complete_sites():
    _reset_plugin()
    plugin.construction_sites = {
        1111: {
            "display_name": "Complete Site",
            "market_id": 1111,
            "progress": 1.0,
            "complete": False,
            "failed": False,
            "materials": [
                {"name": "Steel", "name_key": "steel", "required": 100, "provided": 100, "carrier": 0, "ship": 0, "completion": 0},
            ],
            "station": "Test", "system": "Sol",
            "site_type": "", "site_name": "", "parsed_system": "",
        },
        2222: {
            "display_name": "Incomplete Site",
            "market_id": 2222,
            "progress": 0.5,
            "complete": False,
            "failed": False,
            "materials": [
                {"name": "Aluminium", "name_key": "aluminium", "required": 200, "provided": 50, "carrier": 0, "ship": 0, "completion": 150},
            ],
            "station": "Test2", "system": "Alpha Centauri",
            "site_type": "", "site_name": "", "parsed_system": "",
        },
    }
    plugin.selected_site_id = 1111
    plugin._cleanup_complete_sites()

    assert 1111 not in plugin.construction_sites
    assert 2222 in plugin.construction_sites
    assert plugin.selected_site_id == 2222
    print("[PASS] Startup cleanup removes fully delivered sites")


def test_market_event_loads_commodities():
    _reset_plugin()
    market_data = {
        "Items": [
            {"Name": "$steel_name;", "Name_Localised": "Steel", "Stock": 1000},
            {"Name": "$aluminium_name;", "Name_Localised": "Aluminium", "Stock": 500},
            {"Name": "$copper_name;", "Name_Localised": "Copper", "Stock": 0},
            {"Name": "$gold_name;", "Name_Localised": "Gold", "Stock": 200},
        ]
    }
    market_path = os.path.join(_test_tmpdir, "Market.json")
    with open(market_path, "w") as f:
        json.dump(market_data, f)

    plugin.journal_dir = _test_tmpdir
    entry = {"event": "Market", "MarketID": 12345, "StationName": "Test Station"}
    state = {"JournalDir": _test_tmpdir}
    plugin.journal_entry("Cmdr", False, "Sol", "Test Station", entry, state)

    assert "steel" in plugin.station_commodities
    assert "aluminium" in plugin.station_commodities
    assert "copper" not in plugin.station_commodities
    assert "gold" in plugin.station_commodities
    assert len(plugin.station_commodities) == 3
    print("[PASS] Market event loads station commodities with stock > 0 only")


def test_undocked_event_clears_commodities():
    _reset_plugin()
    plugin.station_commodities = {"steel", "aluminium", "copper"}

    entry = {"event": "Undocked", "StationName": "Test Station"}
    state = {"JournalDir": _test_tmpdir}
    plugin.journal_entry("Cmdr", False, "Sol", "Test Station", entry, state)

    assert len(plugin.station_commodities) == 0
    print("[PASS] Undocked event clears station commodities")


def test_market_commodities_affect_material_color():
    _reset_plugin()
    plugin.station_commodities = {"steel"}

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 9876,
        "ConstructionProgress": 0.3,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 500,
                "ProvidedAmount": 100,
                "Payment": 1000,
            },
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 300,
                "ProvidedAmount": 50,
                "Payment": 500,
            },
        ],
    }
    plugin._process_construction_depot(entry, "Test Site", "Sol")

    materials = plugin.construction_sites[9876]["materials"]
    steel = [m for m in materials if m["name_key"] == "steel"][0]
    aluminium = [m for m in materials if m["name_key"] == "aluminium"][0]

    assert steel["name_key"] in plugin.station_commodities
    assert aluminium["name_key"] not in plugin.station_commodities
    print("[PASS] Market commodities correctly flag matching materials for highlight")


if __name__ == "__main__":
    print("Running Construction Tracker Plugin Tests\n")

    test_plugin_start()
    test_completion_amount_calculation()
    test_display_name_generation()
    test_normalize_name()
    test_parse_station_name()
    test_display_name_with_ext_panel()
    test_construction_depot_processing()
    test_multiple_sites()
    test_carrier_cargo_update()
    test_contribution_updates()
    test_fc_materials_loading()
    test_journal_entry_cargo_event()
    test_docked_event_does_not_reload_carrier_cargo()
    test_capi_fleetcarrier_cargo_list_format()
    test_capi_fleetcarrier_cargo_dict_format()
    test_capi_fleetcarrier_cargo_duplicate_entries()
    test_capi_fleetcarrier_sales_orders()
    test_capi_fleetcarrier_string_values()
    test_capi_fleetcarrier_empty_data()
    test_capi_fleetcarrier_first_query_replaces_cargo()
    test_capi_fleetcarrier_subsequent_queries_ignored()
    test_capi_fleetcarrier_capacity_parsed()
    test_carrier_stats_sets_free_space()
    test_cargo_transfer_to_carrier()
    test_cargo_transfer_to_ship()
    test_cargo_transfer_updates_construction_site()
    test_carrier_cargo_persisted()
    test_loadgame_reloads_carrier_cargo()
    test_startup_always_reloads_fc_materials()
    test_cargo_event_updates_ship_cargo()
    test_cargo_event_reads_cargo_json()
    test_sanity_check_corrects_tocarrier()
    test_sanity_check_corrects_toship()
    test_sanity_check_no_correction_needed()
    test_sanity_check_multiple_transfers_same_commodity()
    test_sanity_check_mixed_directions()
    test_save_and_load_data()
    test_persistence_across_restart()
    test_split_camel_case()
    test_ship_cargo_affects_completion()
    test_cargo_event_updates_ship_amounts_in_sites()
    test_carrier_edit_updates_cargo()
    test_carrier_edit_zero_removes_from_cargo()
    test_carrier_edit_invalid_input_ignored()

    test_hide_completed_materials()
    test_hide_completed_persisted()

    test_complete_site_removed_on_contribution()
    test_complete_site_removed_on_depot_event()
    test_incomplete_site_not_removed()
    test_selected_site_switches_on_removal()
    test_startup_removes_complete_sites()

    test_market_event_loads_commodities()
    test_undocked_event_clears_commodities()
    test_market_commodities_affect_material_color()

    print(f"\nAll tests passed!")
