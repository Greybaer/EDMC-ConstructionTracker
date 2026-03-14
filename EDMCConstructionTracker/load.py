
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False
    tk = None
    ttk = None

try:
    import myNotebook as nb
    HAS_NB = True
except ImportError:
    HAS_NB = False
    nb = None

try:
    import theme as edmc_theme
    HAS_THEME = True
except ImportError:
    HAS_THEME = False
    edmc_theme = None

plugin_name = "Construction Tracker"
plugin_version = "1.3.0"

logger = logging.getLogger(f"{plugin_name}")
logger.setLevel(logging.DEBUG)


def _setup_logging(log_dir: str) -> None:
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)

    log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    info_path = os.path.join(log_dir, "Tracker.log")
    info_handler = logging.FileHandler(info_path, mode="a", encoding="utf-8")
    info_handler.setLevel(logging.INFO)
    info_handler.addFilter(lambda record: record.levelno == logging.INFO)
    info_handler.setFormatter(log_format)

    debug_path = os.path.join(log_dir, "Tracker.debug")
    debug_handler = logging.FileHandler(debug_path, mode="a", encoding="utf-8")
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.addFilter(lambda record: record.levelno != logging.INFO)
    debug_handler.setFormatter(log_format)

    logger.addHandler(info_handler)
    logger.addHandler(debug_handler)

carrier_cargo: Dict[str, int] = {}
ship_cargo: Dict[str, int] = {}
pending_transfers: List[Dict[str, Any]] = []
construction_sites: Dict[int, Dict[str, Any]] = {}
selected_site_id: Optional[int] = None
journal_dir: Optional[str] = None
plugin_dir: Optional[str] = None
hide_completed_materials: bool = False
station_commodities: set = set()
capi_received: bool = False
carrier_total_capacity: Optional[int] = None
carrier_cargo_reserved: int = 0

frame = None
site_selector = None
site_var = None
progress_var = None
material_frame = None
status_var = None
header_label = None
site_label = None
type_label = None
type_value_label = None
system_label = None
system_value_label = None
progress_label_widget = None
progress_value_widget = None
status_label_widget = None
fc_capacity_label = None
fc_capacity_value_label = None

LABEL_FG_DEFAULT = "#000000"
LABEL_FG_DARK = "#ff8c00"
VALUE_FG_DEFAULT = "#000000"
VALUE_FG_DARK = "#ffffff"
COMPLETE_GREEN = "#4ec94e"
PENDING_YELLOW = "#daa520"
INCOMPLETE_ORANGE = "#ff8c00"
MARKET_BLUE = "#4dc8ff"

SAVE_FILE = "construction_tracker_data.json"


def _get_save_path() -> Optional[str]:
    if plugin_dir:
        return os.path.join(plugin_dir, SAVE_FILE)
    return None


def _save_data() -> None:
    path = _get_save_path()
    if not path:
        return
    try:
        save_obj = {
            "hide_completed_materials": hide_completed_materials,
            "selected_site_id": selected_site_id,
            "construction_sites": {str(k): v for k, v in construction_sites.items()},
            "carrier_cargo": carrier_cargo,
            "carrier_total_capacity": carrier_total_capacity,
            "carrier_cargo_reserved": carrier_cargo_reserved,
        }
        with open(path, "w") as f:
            json.dump(save_obj, f, indent=2)
        logger.debug(f"Saved data to {path}")
    except Exception as e:
        logger.error(f"Error saving data: {e}")


def _load_data() -> None:
    global hide_completed_materials, selected_site_id, construction_sites, carrier_cargo, carrier_total_capacity, carrier_cargo_reserved
    path = _get_save_path()
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, "r") as f:
            save_obj = json.load(f)
        hide_completed_materials = save_obj.get("hide_completed_materials", False)
        selected_site_id = save_obj.get("selected_site_id")
        raw_sites = save_obj.get("construction_sites", {})
        construction_sites.clear()
        for k, v in raw_sites.items():
            construction_sites[int(k)] = v
        saved_cargo = save_obj.get("carrier_cargo", {})
        carrier_cargo.clear()
        carrier_cargo.update(saved_cargo)
        saved_cap = save_obj.get("carrier_total_capacity")
        if saved_cap is not None:
            carrier_total_capacity = int(saved_cap)
        carrier_cargo_reserved = int(save_obj.get("carrier_cargo_reserved", 0))
        logger.info(f"Loaded {len(construction_sites)} construction sites, {len(carrier_cargo)} carrier cargo items from save")
    except Exception as e:
        logger.error(f"Error loading data: {e}")


def _init_journal_dir() -> None:
    global journal_dir
    if journal_dir:
        return
    try:
        from config import config as edmc_cfg
        journal_dir = edmc_cfg.get_str('journaldir') or str(edmc_cfg.default_journal_dir_path)
        if journal_dir:
            logger.info(f"Journal directory from EDMC config: {journal_dir}")
    except Exception:
        pass


def plugin_start3(plugin_dir_path: str) -> str:
    global plugin_dir
    plugin_dir = plugin_dir_path
    _setup_logging(plugin_dir)
    _load_data()
    _init_journal_dir()
    if journal_dir:
        _load_carrier_cargo()
        _update_carrier_amounts()
        _save_data()
    _cleanup_complete_sites()
    logger.info(f"{plugin_name} v{plugin_version} started")
    return plugin_name


def plugin_stop() -> None:
    _save_data()
    logger.info(f"{plugin_name} stopped")


def plugin_app(parent: tk.Frame) -> tk.Frame:
    global frame, site_selector, site_var, progress_var, material_frame, status_var
    global header_label, site_label, progress_label_widget, progress_value_widget, status_label_widget
    global type_label, type_value_label, system_label, system_value_label
    global fc_capacity_label, fc_capacity_value_label

    frame = tk.Frame(parent)

    header_label = tk.Label(frame, text="Construction Tracker", font=("Helvetica", 10, "bold"), fg=_label_fg())
    header_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 4))

    site_label = tk.Label(frame, text="Site:", fg=_label_fg())
    site_label.grid(row=1, column=0, sticky=tk.W)
    site_var = tk.StringVar(value="No sites tracked")
    site_selector = tk.OptionMenu(frame, site_var, "No sites tracked")
    site_selector.config(width=30, anchor=tk.W)
    site_selector.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=(4, 0))
    site_var.trace_add("write", _on_site_var_changed)

    type_label = tk.Label(frame, text="Type:", fg=_label_fg())
    type_label.grid(row=2, column=0, sticky=tk.W)
    type_value_label = tk.Label(frame, text="--", fg=_value_fg())
    type_value_label.grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=(4, 0))

    system_label = tk.Label(frame, text="System:", fg=_label_fg())
    system_label.grid(row=3, column=0, sticky=tk.W)
    system_value_label = tk.Label(frame, text="--", fg=_value_fg())
    system_value_label.grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=(4, 0))

    progress_label_widget = tk.Label(frame, text="Progress:", font=("Helvetica", 9), fg=_label_fg())
    progress_label_widget.grid(row=4, column=0, sticky=tk.W, pady=(4, 2))
    progress_var = tk.StringVar(value="--")
    progress_value_widget = tk.Label(frame, textvariable=progress_var, font=("Helvetica", 9), fg=_value_fg())
    progress_value_widget.grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=(4, 0), pady=(4, 2))

    status_var = tk.StringVar(value="Waiting for construction site data...")
    status_label_widget = tk.Label(frame, textvariable=status_var, font=("Helvetica", 8))
    status_label_widget.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(0, 2))

    fc_capacity_label = tk.Label(frame, text="Remaining Cargo Space:", font=("Helvetica", 8), fg=_label_fg())
    fc_capacity_label.grid(row=6, column=0, sticky=tk.W)
    fc_capacity_value_label = tk.Label(frame, text="", font=("Helvetica", 8), fg=_value_fg())
    fc_capacity_value_label.grid(row=6, column=1, columnspan=2, sticky=tk.W, padx=(4, 0), pady=(0, 4))
    fc_capacity_label.grid_remove()
    fc_capacity_value_label.grid_remove()

    material_frame = tk.Frame(frame)
    material_frame.grid(row=7, column=0, columnspan=3, sticky=tk.W)

    if construction_sites:
        _update_site_selector()
        _update_display()

    return frame


def plugin_prefs(parent, cmdr: str, is_beta: bool):
    if HAS_NB and nb:
        prefs_frame = nb.Frame(parent)
    else:
        prefs_frame = tk.Frame(parent)

    global _prefs_hide_completed_var
    _prefs_hide_completed_var = tk.IntVar(value=1 if hide_completed_materials else 0)
    nb_cb = nb.Checkbutton if (HAS_NB and nb and hasattr(nb, 'Checkbutton')) else tk.Checkbutton
    nb_cb(prefs_frame, text="Hide completed materials", variable=_prefs_hide_completed_var).grid(
        row=0, column=0, columnspan=2, sticky=tk.W, padx=(20, 0))

    return prefs_frame


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    global _prefs_hide_completed_var
    if _prefs_hide_completed_var:
        _set_hide_completed(_prefs_hide_completed_var.get() == 1)


_prefs_hide_completed_var = None



def _on_site_var_changed(*args) -> None:
    global selected_site_id
    if not site_var or not construction_sites:
        return

    selected_name = site_var.get()
    for mid, site_data in construction_sites.items():
        if site_data["display_name"] == selected_name:
            if selected_site_id != mid:
                selected_site_id = mid
                _update_display()
                _save_data()
            return


def _parse_station_name(name: str) -> Tuple[str, str, str]:
    site_type = ""
    site_name = ""
    system_name = ""

    if name.startswith("$EXT_PANEL_"):
        name = name[len("$EXT_PANEL_"):]

    segments = [s.strip() for s in name.split(";") if s.strip()]

    if len(segments) >= 2:
        site_type = segments[0]
        remainder = segments[1]
    elif len(segments) == 1:
        remainder = segments[0]
    else:
        return site_type, site_name, system_name

    if not site_type and ": " in remainder:
        colon_parts = remainder.split(": ", 1)
        site_type = colon_parts[0].strip()
        remainder = colon_parts[1].strip()

    if " - " in remainder:
        site_parts = remainder.rsplit(" - ", 1)
        site_name = site_parts[0].strip()
        system_name = site_parts[1].strip()
    else:
        site_name = remainder

    return site_type, site_name, system_name


def _get_site_display_name(station: Optional[str], system: Optional[str], market_id: int) -> str:
    if station:
        site_type, site_name, parsed_system = _parse_station_name(station)
        if site_name:
            return site_name
        if site_type:
            return site_type
    return f"Site #{market_id}"


def _safe_int(value) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _normalize_name(raw_name: str) -> str:
    name = raw_name.strip().lower()
    if name.startswith("$"):
        name = name[1:]
    if name.endswith(";"):
        name = name[:-1]
    if name.endswith("_name"):
        name = name[:-5]
    return name


def _split_camel_case(text: str) -> str:
    if not text:
        return text
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', text)


def _load_carrier_cargo() -> bool:
    global carrier_cargo
    if not journal_dir:
        logger.debug("Cannot load carrier cargo: journal_dir not set")
        return False

    fc_path = os.path.join(journal_dir, "FCMaterials.json")
    if not os.path.exists(fc_path):
        logger.debug(f"FCMaterials.json not found at {fc_path}")
        return False

    try:
        with open(fc_path, "r") as f:
            data = json.load(f)

        items = data.get("Items", [])
        carrier_cargo.clear()
        for item in items:
            raw_name = item.get("Name", "")
            name_key = _normalize_name(raw_name)
            stock = item.get("Stock", 0)
            if name_key and stock > 0:
                carrier_cargo[name_key] = stock
        logger.info(f"Loaded FC cargo: {len(carrier_cargo)} items from FCMaterials.json")
        return True
    except Exception as e:
        logger.error(f"Error loading FCMaterials.json: {e}")
        return False


def _load_market_commodities() -> bool:
    global station_commodities
    if not journal_dir:
        return False

    market_path = os.path.join(journal_dir, "Market.json")
    if not os.path.exists(market_path):
        logger.debug(f"Market.json not found at {market_path}")
        return False

    try:
        with open(market_path, "r") as f:
            data = json.load(f)

        items = data.get("Items", [])
        station_commodities = set()
        for item in items:
            stock = item.get("Stock", 0)
            if stock > 0:
                raw_name = item.get("Name", "")
                name_key = _normalize_name(raw_name)
                if name_key:
                    station_commodities.add(name_key)
        logger.info(f"Loaded market commodities: {len(station_commodities)} items")
        return True
    except Exception as e:
        logger.error(f"Error loading Market.json: {e}")
        return False


def _calculate_completion(required: int, provided: int, carrier: int, ship: int = 0) -> int:
    remaining = required - (provided + carrier + ship)
    return max(0, remaining)


def _update_ship_cargo(entry: Dict[str, Any]) -> None:
    global ship_cargo
    inventory = entry.get("Inventory")
    if inventory is None and journal_dir:
        cargo_path = os.path.join(journal_dir, "Cargo.json")
        if os.path.exists(cargo_path):
            try:
                with open(cargo_path, "r") as f:
                    cargo_data = json.load(f)
                inventory = cargo_data.get("Inventory")
            except Exception as e:
                logger.error(f"Error reading Cargo.json: {e}")

    if inventory is None:
        return

    ship_cargo.clear()
    for item in inventory:
        raw_name = item.get("Name", "")
        name_key = _normalize_name(raw_name)
        count = _safe_int(item.get("Count", 0))
        if name_key and count > 0:
            ship_cargo[name_key] = ship_cargo.get(name_key, 0) + count
    logger.debug(f"Ship cargo updated: {len(ship_cargo)} items")


def _validate_pending_transfers() -> None:
    global carrier_cargo, pending_transfers
    if not pending_transfers:
        return

    aggregated: Dict[str, Dict[str, Any]] = {}
    for transfer in pending_transfers:
        name_key = transfer["name_key"]
        count = transfer["count"]
        direction = transfer["direction"]
        ship_before = transfer["ship_before"]

        if name_key not in aggregated:
            aggregated[name_key] = {
                "ship_before": ship_before,
                "net_to_carrier": 0,
            }

        if direction == "tocarrier":
            aggregated[name_key]["net_to_carrier"] += count
        elif direction == "toship":
            aggregated[name_key]["net_to_carrier"] -= count

    pending_transfers.clear()

    corrections_made = False
    for name_key, agg in aggregated.items():
        ship_before = agg["ship_before"]
        net_to_carrier = agg["net_to_carrier"]
        ship_after = ship_cargo.get(name_key, 0)

        expected_ship_change = -net_to_carrier
        actual_ship_change = ship_after - ship_before

        if actual_ship_change == expected_ship_change:
            continue

        if net_to_carrier > 0 and actual_ship_change > 0:
            logger.debug(
                f"CargoTransfer sanity check: {name_key} skipping correction - "
                f"ship gained cargo during tocarrier transfer (likely unrelated change)"
            )
            continue
        if net_to_carrier < 0 and actual_ship_change < 0:
            logger.debug(
                f"CargoTransfer sanity check: {name_key} skipping correction - "
                f"ship lost cargo during toship transfer (likely unrelated change)"
            )
            continue

        actual_to_carrier = ship_before - ship_after
        correction = actual_to_carrier - net_to_carrier

        if correction == 0:
            continue

        logger.warning(
            f"CargoTransfer sanity check: {name_key} expected ship change "
            f"{expected_ship_change:+d}, actual {actual_ship_change:+d} "
            f"(before={ship_before}, after={ship_after}). "
            f"Adjusting carrier by {correction:+d}"
        )
        carrier_cargo[name_key] = carrier_cargo.get(name_key, 0) + correction
        if carrier_cargo.get(name_key, 0) <= 0:
            carrier_cargo.pop(name_key, None)
        corrections_made = True

    if corrections_made:
        _update_carrier_amounts()
        _save_data()
        if selected_site_id:
            _update_display()
        logger.info(f"Carrier cargo corrected via sanity check: {dict(carrier_cargo)}")


def _process_cargo_transfer(entry: Dict[str, Any]) -> None:
    global carrier_cargo, pending_transfers
    transfers = entry.get("Transfers", [])
    for transfer in transfers:
        raw_name = transfer.get("Type", "")
        name_key = _normalize_name(raw_name)
        count = _safe_int(transfer.get("Count", 0))
        direction = transfer.get("Direction", "")

        if not name_key or count <= 0:
            continue

        ship_before = ship_cargo.get(name_key, 0)

        pending_transfers.append({
            "name_key": name_key,
            "count": count,
            "direction": direction,
            "ship_before": ship_before,
        })

        if direction == "tocarrier":
            carrier_cargo[name_key] = carrier_cargo.get(name_key, 0) + count
            logger.info(f"CargoTransfer: +{count} {name_key} to carrier (now {carrier_cargo[name_key]})")
        elif direction == "toship":
            current = carrier_cargo.get(name_key, 0)
            carrier_cargo[name_key] = max(0, current - count)
            if carrier_cargo[name_key] == 0:
                del carrier_cargo[name_key]
            logger.info(f"CargoTransfer: -{count} {name_key} from carrier (now {carrier_cargo.get(name_key, 0)})")


def _process_construction_depot(entry: Dict[str, Any], station: Optional[str], system: Optional[str]) -> None:
    global selected_site_id

    market_id = entry.get("MarketID")
    if market_id is None:
        return

    progress = entry.get("ConstructionProgress", 0.0)
    complete = entry.get("ConstructionComplete", False)
    failed = entry.get("ConstructionFailed", False)
    resources = entry.get("ResourcesRequired", [])

    display_name = _get_site_display_name(station, system, market_id)

    site_type, site_name, parsed_system = _parse_station_name(station or "")

    materials: List[Dict[str, Any]] = []
    for res in resources:
        raw_name = res.get("Name", "")
        name_localised = res.get("Name_Localised", raw_name)
        name_key = _normalize_name(raw_name)
        required_amount = res.get("RequiredAmount", 0)
        provided_amount = res.get("ProvidedAmount", 0)
        carrier_amount = carrier_cargo.get(name_key, 0)
        ship_amount = ship_cargo.get(name_key, 0)
        completion_amount = _calculate_completion(required_amount, provided_amount, carrier_amount, ship_amount)

        materials.append({
            "name": name_localised,
            "name_key": name_key,
            "required": required_amount,
            "provided": provided_amount,
            "carrier": carrier_amount,
            "ship": ship_amount,
            "completion": completion_amount,
        })

    construction_sites[market_id] = {
        "display_name": display_name,
        "market_id": market_id,
        "progress": progress,
        "complete": complete,
        "failed": failed,
        "materials": materials,
        "station": station,
        "system": system,
        "site_type": site_type,
        "site_name": site_name,
        "parsed_system": parsed_system,
    }

    selected_site_id = market_id

    _update_site_selector()
    _update_display()
    _save_data()
    logger.info(f"Processed construction depot: {display_name} ({progress:.1%})")


def _check_site_complete(market_id: int) -> bool:
    global selected_site_id
    if market_id not in construction_sites:
        return False
    site = construction_sites[market_id]
    materials = site.get("materials", [])
    if not materials:
        return False
    all_delivered = all(m["provided"] >= m["required"] for m in materials)
    if all_delivered:
        display_name = site.get("display_name", str(market_id))
        logger.info(f"Construction site fully delivered, removing: {display_name}")
        del construction_sites[market_id]
        if selected_site_id == market_id:
            if construction_sites:
                selected_site_id = next(iter(construction_sites))
            else:
                selected_site_id = None
        _update_site_selector()
        _update_display()
        _save_data()
        return True
    return False


def _cleanup_complete_sites() -> None:
    global selected_site_id
    complete_ids = [
        mid for mid, site in construction_sites.items()
        if site.get("materials") and all(m["provided"] >= m["required"] for m in site["materials"])
    ]
    if not complete_ids:
        return
    for mid in complete_ids:
        display_name = construction_sites[mid].get("display_name", str(mid))
        logger.info(f"Startup cleanup: removing fully delivered site: {display_name}")
        del construction_sites[mid]
    if selected_site_id not in construction_sites:
        if construction_sites:
            selected_site_id = next(iter(construction_sites))
        else:
            selected_site_id = None
    _save_data()


def _update_carrier_amounts() -> None:
    for mid, site_data in construction_sites.items():
        for mat in site_data["materials"]:
            carrier_amount = carrier_cargo.get(mat["name_key"], 0)
            ship_amount = ship_cargo.get(mat["name_key"], 0)
            mat["carrier"] = carrier_amount
            mat["ship"] = ship_amount
            mat["completion"] = _calculate_completion(mat["required"], mat["provided"], carrier_amount, ship_amount)


def _update_ship_amounts() -> None:
    for mid, site_data in construction_sites.items():
        for mat in site_data["materials"]:
            ship_amount = ship_cargo.get(mat["name_key"], 0)
            mat["ship"] = ship_amount
            mat["completion"] = _calculate_completion(mat["required"], mat["provided"], mat["carrier"], ship_amount)


def _update_site_selector() -> None:
    if not site_selector or not site_var:
        return

    names = [site["display_name"] for site in construction_sites.values()]

    menu = site_selector["menu"]
    menu.delete(0, "end")
    for name in names:
        menu.add_command(label=name, command=lambda n=name: site_var.set(n))

    if selected_site_id and selected_site_id in construction_sites:
        site_var.set(construction_sites[selected_site_id]["display_name"])
    elif names:
        site_var.set(names[0])

    _register_with_theme(site_selector)


def _refresh_label_colors() -> None:
    label_color = _label_fg()
    value_color = _value_fg()
    if header_label:
        header_label.config(fg=label_color)
    if site_label:
        site_label.config(fg=label_color)
    if site_selector:
        try:
            site_selector.config(fg=label_color)
        except Exception:
            pass
    if type_label:
        type_label.config(fg=label_color)
    if type_value_label:
        type_value_label.config(fg=value_color)
    if system_label:
        system_label.config(fg=label_color)
    if system_value_label:
        system_value_label.config(fg=value_color)
    if progress_label_widget:
        progress_label_widget.config(fg=label_color)
    if progress_value_widget:
        progress_value_widget.config(fg=value_color)
    if fc_capacity_label:
        fc_capacity_label.config(fg=label_color)
    if fc_capacity_value_label:
        fc_capacity_value_label.config(fg=value_color)


def _update_display() -> None:
    if not progress_var or not material_frame or not status_var:
        return

    _refresh_label_colors()

    if fc_capacity_value_label and fc_capacity_label:
        if carrier_total_capacity is not None:
            remaining = carrier_total_capacity - carrier_cargo_reserved - sum(carrier_cargo.values())
            fc_capacity_value_label.config(text=f"{remaining:,}")
            fc_capacity_label.grid()
            fc_capacity_value_label.grid()
        else:
            fc_capacity_label.grid_remove()
            fc_capacity_value_label.grid_remove()

    if not selected_site_id or selected_site_id not in construction_sites:
        progress_var.set("--")
        status_var.set("Waiting for construction site data...")
        _clear_material_display()
        return

    site_data = construction_sites[selected_site_id]
    progress = site_data["progress"]

    if type_value_label:
        raw_type = site_data.get("site_type") or ""
        type_value_label.config(text=_split_camel_case(raw_type) if raw_type else "--")
    if system_value_label:
        system_value_label.config(text=site_data.get("parsed_system") or site_data.get("system") or "--")

    if site_data["complete"]:
        progress_var.set("COMPLETE")
        status_var.set("Construction finished!")
    elif site_data["failed"]:
        progress_var.set("FAILED")
        status_var.set("Construction failed.")
    else:
        progress_var.set(f"{progress:.1%}")
        total_materials = len(site_data["materials"])
        completed_materials = sum(1 for m in site_data["materials"] if m["completion"] == 0 and m["provided"] >= m["required"])
        status_var.set(f"{completed_materials}/{total_materials} materials fulfilled")

    _render_materials(site_data["materials"])


def _clear_material_display() -> None:
    if not material_frame:
        return
    for widget in material_frame.winfo_children():
        widget.destroy()


def _is_dark_theme() -> bool:
    if HAS_THEME and edmc_theme:
        try:
            active = edmc_theme.theme.active
            if active is not None:
                return active in (1, 2)
        except Exception:
            pass
    try:
        from config import config as edmc_cfg
        theme_val = edmc_cfg.get_int('theme')
        return theme_val in (1, 2)
    except Exception:
        return False


def _label_fg() -> str:
    return LABEL_FG_DARK if _is_dark_theme() else LABEL_FG_DEFAULT


def _value_fg() -> str:
    return VALUE_FG_DARK if _is_dark_theme() else VALUE_FG_DEFAULT


def _register_with_theme(widget) -> None:
    if HAS_THEME and edmc_theme:
        try:
            edmc_theme.theme.register(widget)
            edmc_theme.theme.apply(widget.winfo_toplevel())
        except Exception:
            pass


def _set_hide_completed(enabled: bool) -> None:
    global hide_completed_materials
    hide_completed_materials = enabled
    _update_display()
    _save_data()



def _on_carrier_edit(name_key: str, var: 'tk.StringVar', row_idx: int,
                     mat: Dict[str, Any]) -> None:
    raw = var.get().strip()
    try:
        new_val = max(0, int(raw))
    except (ValueError, TypeError):
        return

    if new_val == 0:
        carrier_cargo.pop(name_key, None)
    else:
        carrier_cargo[name_key] = new_val

    mat["carrier"] = new_val
    mat["completion"] = _calculate_completion(mat["required"], mat["provided"], new_val, mat.get("ship", 0))

    _update_carrier_amounts()
    _save_data()
    _update_display()


def _render_materials(materials: List[Dict[str, Any]]) -> None:
    if not material_frame:
        return

    _clear_material_display()

    headers = ["Material", "Required", "Provided", "Carrier", "Ship", "Remaining"]
    for col, header_text in enumerate(headers):
        lbl = tk.Label(material_frame, text=header_text, font=("Helvetica", 8, "bold"),
                       anchor=tk.W, fg=_label_fg())
        lbl.grid(row=0, column=col, sticky=tk.W, padx=(0, 8))

    sep = ttk.Separator(material_frame, orient=tk.HORIZONTAL)
    sep.grid(row=1, column=0, columnspan=len(headers), sticky=tk.EW, pady=2)

    display_materials = materials
    if hide_completed_materials:
        display_materials = [m for m in materials if not (m["completion"] == 0 and m["provided"] >= m["required"])]

    for row_idx, mat in enumerate(display_materials, start=2):
        if mat["completion"] == 0 and mat["provided"] >= mat["required"]:
            fg_color = COMPLETE_GREEN
        elif mat["completion"] == 0 and mat.get("carrier", 0) > 0:
            fg_color = PENDING_YELLOW
        elif station_commodities and mat.get("name_key", "") in station_commodities:
            fg_color = MARKET_BLUE
        else:
            fg_color = INCOMPLETE_ORANGE

        name_lbl = tk.Label(material_frame, text=mat["name"], font=("Helvetica", 8),
                            fg=fg_color, anchor=tk.W)
        name_lbl.grid(row=row_idx, column=0, sticky=tk.W, padx=(0, 8))

        req_lbl = tk.Label(material_frame, text=str(mat["required"]), font=("Helvetica", 8),
                           fg=fg_color, anchor=tk.E)
        req_lbl.grid(row=row_idx, column=1, sticky=tk.E, padx=(0, 8))

        prov_lbl = tk.Label(material_frame, text=str(mat["provided"]), font=("Helvetica", 8),
                            fg=fg_color, anchor=tk.E)
        prov_lbl.grid(row=row_idx, column=2, sticky=tk.E, padx=(0, 8))

        is_incomplete = mat["provided"] < mat["required"]
        if is_incomplete:
            carr_var = tk.StringVar(value=str(mat["carrier"]))
            carr_entry = tk.Entry(material_frame, textvariable=carr_var,
                                  font=("Helvetica", 8), width=6,
                                  fg=fg_color,
                                  insertbackground=fg_color, justify=tk.RIGHT,
                                  relief=tk.FLAT, highlightthickness=1,
                                  highlightcolor=fg_color, highlightbackground=fg_color)
            carr_entry.grid(row=row_idx, column=3, sticky=tk.E, padx=(0, 8))
            name_key = mat.get("name_key", "")
            carr_entry.bind("<Return>", lambda e, nk=name_key, v=carr_var, r=row_idx, m=mat: _on_carrier_edit(nk, v, r, m))
            carr_entry.bind("<FocusOut>", lambda e, nk=name_key, v=carr_var, r=row_idx, m=mat: _on_carrier_edit(nk, v, r, m))
        else:
            carr_lbl = tk.Label(material_frame, text=str(mat["carrier"]), font=("Helvetica", 8),
                                fg=fg_color, anchor=tk.E)
            carr_lbl.grid(row=row_idx, column=3, sticky=tk.E, padx=(0, 8))

        ship_lbl = tk.Label(material_frame, text=str(mat.get("ship", 0)), font=("Helvetica", 8),
                            fg=fg_color, anchor=tk.E)
        ship_lbl.grid(row=row_idx, column=4, sticky=tk.E, padx=(0, 8))

        comp_lbl = tk.Label(material_frame, text=str(mat["completion"]), font=("Helvetica", 8),
                            fg=fg_color, anchor=tk.E)
        comp_lbl.grid(row=row_idx, column=5, sticky=tk.E, padx=(0, 8))

    _register_with_theme(material_frame)


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: str,
    station: str,
    entry: Dict[str, Any],
    state: Dict[str, Any],
) -> None:
    global journal_dir, capi_received, carrier_total_capacity, carrier_cargo_reserved

    if journal_dir is None:
        jdir = state.get("JournalDir")
        if jdir:
            journal_dir = jdir
        else:
            _init_journal_dir()

    event_name = entry.get("event", "")

    if event_name == "LoadGame":
        capi_received = False
        if journal_dir:
            _load_carrier_cargo()
            _update_carrier_amounts()
            _save_data()
            if selected_site_id:
                _update_display()

    elif event_name == "CargoTransfer":
        _process_cargo_transfer(entry)
        _update_carrier_amounts()
        _save_data()
        if selected_site_id:
            _update_display()

    elif event_name == "Cargo":
        _update_ship_cargo(entry)
        if pending_transfers:
            _validate_pending_transfers()
        _update_ship_amounts()
        _save_data()
        if selected_site_id:
            _update_display()

    elif event_name == "Market":
        _load_market_commodities()
        if selected_site_id:
            _update_display()

    elif event_name == "Undocked":
        station_commodities.clear()
        if selected_site_id:
            _update_display()

    elif event_name == "CarrierStats":
        space = entry.get("SpaceUsage", {})
        total = space.get("TotalCapacity")
        if total is not None:
            carrier_total_capacity = int(total)
            carrier_cargo_reserved = int(space.get("CargoReserved", 0))
            logger.info(f"CarrierStats: total={carrier_total_capacity}, reserved={carrier_cargo_reserved}")
            _save_data()
            _update_display()

    elif event_name == "ColonisationConstructionDepot":
        _process_construction_depot(entry, station, system)
        market_id = entry.get("MarketID")
        if market_id:
            _check_site_complete(market_id)

    elif event_name == "ColonisationContribution":
        market_id = entry.get("MarketID")
        if market_id and market_id in construction_sites:
            contributions = entry.get("Contributions", [])
            for contrib in contributions:
                raw_name = contrib.get("Name", "")
                name_key = _normalize_name(raw_name)
                amount = contrib.get("Amount", 0)
                for mat in construction_sites[market_id]["materials"]:
                    if mat["name_key"] == name_key:
                        mat["provided"] += amount
                        mat["completion"] = _calculate_completion(
                            mat["required"], mat["provided"], mat["carrier"], mat.get("ship", 0)
                        )
                        break
            if not _check_site_complete(market_id):
                _save_data()
                if market_id == selected_site_id:
                    _update_display()


def capi_fleetcarrier(data) -> None:
    global capi_received
    if not data:
        return

    if capi_received:
        logger.info("CAPI fleetcarrier query ignored (already received initial data)")
        return

    logger.info(f"CAPI fleetcarrier called (first query), top-level keys: {list(data.keys()) if hasattr(data, 'keys') else type(data)}")
    _process_capi_carrier_cargo(data)
    capi_received = True
    _update_carrier_amounts()
    _save_data()
    if selected_site_id:
        _update_display()
    logger.info(f"Set carrier cargo from CAPI: {len(carrier_cargo)} items: {dict(carrier_cargo)}")


def _process_capi_carrier_cargo(data) -> None:
    global carrier_cargo

    new_cargo: Dict[str, int] = {}

    cargo_section = data.get("cargo", [])
    logger.info(f"CAPI cargo type: {type(cargo_section).__name__}, value preview: {str(cargo_section)[:500]}")

    cargo_list = []
    if isinstance(cargo_section, list):
        cargo_list = cargo_section
    elif isinstance(cargo_section, dict):
        cargo_list = cargo_section.get("commodities", []) or cargo_section.get("items", [])

    for item in cargo_list:
        name_raw = item.get("commodity", "") or item.get("name", "")
        name_key = _normalize_name(name_raw)
        qty = _safe_int(item.get("quantity", 0) or item.get("qty", 0))
        if name_key and qty > 0:
            new_cargo[name_key] = new_cargo.get(name_key, 0) + qty

    orders = data.get("orders", {})
    if isinstance(orders, dict):
        commodity_orders = orders.get("commodities", {})
        if isinstance(commodity_orders, dict):
            sales = commodity_orders.get("sales", {})
            if isinstance(sales, dict):
                sales = sales.values()
            for item in sales:
                name_raw = item.get("commodity", "") or item.get("name", "")
                name_key = _normalize_name(name_raw)
                outstanding = _safe_int(item.get("stock", 0) or item.get("outstanding", 0) or item.get("quantity", 0))
                if name_key and outstanding > 0 and name_key not in new_cargo:
                    new_cargo[name_key] = outstanding

    market = data.get("market", {})
    if isinstance(market, dict) and not orders:
        sell_orders = market.get("sell_orders", [])
        if isinstance(sell_orders, dict):
            sell_orders = sell_orders.values()
        for item in sell_orders:
            name_raw = item.get("commodity", "") or item.get("name", "")
            name_key = _normalize_name(name_raw)
            qty = _safe_int(item.get("stock", 0) or item.get("quantity", 0) or item.get("outstanding", 0))
            if name_key and qty > 0 and name_key not in new_cargo:
                new_cargo[name_key] = qty

    carrier_cargo = new_cargo
    logger.info(f"CAPI carrier cargo set: {dict(carrier_cargo)}")
