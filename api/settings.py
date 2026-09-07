"""API Blueprint for Settings, Health, App Info, and Backups."""

import os
from pathlib import Path
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from paths import DB_FILE, get_version
from db import backup_db
from repositories.settings_repo import SettingsRepository

settings_bp = Blueprint("settings", __name__)
STATE_FILE = "state.json"
AUTH_STATUS_FILE = "auth_status.json"


def load_config():
    import server
    return server.load_config()


def save_config(data):
    import server
    return server.save_config(data)


def app_build_info():
    source_mtime = datetime.fromtimestamp(Path(__file__).stat().st_mtime, timezone.utc)
    return {
        "version": get_version(),
        "built_at": "2026-09-07",
        "source_updated_at": source_mtime.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "group_manager_available": True,
    }


@settings_bp.route("/api/status", methods=["GET"])
def get_status():
    is_authenticated = os.path.exists(STATE_FILE) or os.path.exists(AUTH_STATUS_FILE)
    return jsonify({"authenticated": is_authenticated})


@settings_bp.route("/api/app-info", methods=["GET"])
def get_app_info():
    return jsonify(app_build_info())


@settings_bp.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    config = load_config()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        if "gpm_api_url" in data:
            config["gpm_api_url"] = str(data["gpm_api_url"]).strip()
        if "gemini_api_key" in data:
            new_key = str(data["gemini_api_key"]).strip()
            if new_key:
                config["gemini_api_key"] = new_key
        if "delay_preset" in data:
            config["delay_preset"] = str(data["delay_preset"]).strip()
        if "delay_min" in data:
            config["delay_min"] = max(5, int(data["delay_min"]))
        if "delay_max" in data:
            config["delay_max"] = max(int(data.get("delay_min", 5)), int(data["delay_max"]))
        if "auto_join_groups" in data:
            config["auto_join_groups"] = bool(data["auto_join_groups"])
        if "group_keywords" in data:
            config["group_keywords"] = str(data["group_keywords"]).strip()
        save_config(config)
        return jsonify({
            "success": True,
            "message": "Đã lưu cấu hình thành công!",
            "settings": {
                "gpm_api_url": config.get("gpm_api_url", "http://127.0.0.1:19995"),
                "delay_preset": config.get("delay_preset", "safe"),
                "delay_min": config.get("delay_min", 300),
                "delay_max": config.get("delay_max", 600),
                "auto_join_groups": config.get("auto_join_groups", False),
                "group_keywords": config.get("group_keywords", "Homestay Huế, Du lịch Huế"),
            },
        })

    key = config.get("gemini_api_key", "")
    masked_key = f"...{key[-6:]}" if len(key) > 6 else ("" if not key else key)
    return jsonify({
        "gpm_api_url": config.get("gpm_api_url", "http://127.0.0.1:19995"),
        "gemini_api_key_masked": masked_key,
        "has_gemini_key": bool(key),
        "gemini_api_key_configured": bool(key),
        "delay_preset": config.get("delay_preset", "safe"),
        "delay_min": config.get("delay_min", 300),
        "delay_max": config.get("delay_max", 600),
        "auto_join_groups": config.get("auto_join_groups", False),
        "group_keywords": config.get("group_keywords", "Homestay Huế, Du lịch Huế"),
    })


@settings_bp.route("/api/security/overview", methods=["GET"])
def security_overview():
    config = load_config()
    import server
    return jsonify({
        "local_only": True,
        "debug_enabled": False,
        "rate_limiting_mode": "in_process_sliding_window",
        "gemini_key_configured": bool(config.get("gemini_api_key")),
        "page_token_configured": bool(config.get("page_access_token")),
        "accounts_count": server.json_list_count(server.ACCOUNTS_FILE),
        "vault_entries_count": server.json_list_count(server.VAULT_FILE),
        "campaigns_count": len(server.load_campaigns()),
        "queue_jobs_count": len(server.load_queue()),
        "groups_registered_count": server.json_list_count(server.GROUPS_FILE),
        "scheduler_posted_count": server.scheduler_posted_count(),
        "database_mode": "SQLite WAL",
    })


@settings_bp.route("/api/backup", methods=["POST"])
def api_backup():
    try:
        backup_path = backup_db()
        return jsonify({
            "success": True,
            "message": "Sao lưu cơ sở dữ liệu thành công!",
            "backup_path": backup_path,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Lỗi sao lưu cơ sở dữ liệu: {e}",
        }), 500
