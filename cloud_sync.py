"""
cloud_sync.py — cross-computer persistence via Google Apps Script (Hardcore).
Hardened error messages + logging.
"""

from __future__ import annotations
import json
import requests

from logging_config import log

KEY = "rugpull"
TIMEOUT = 20


class CloudError(RuntimeError):
    pass


def _valid(url: str) -> bool:
    return bool(url) and "/exec" in url


def test_connection(url: str) -> dict:
    if not _valid(url):
        return {"ok": False, "status": "bad url", "detail": "URL must end in /exec"}
    try:
        r = requests.get(url, params={"key": KEY}, timeout=TIMEOUT)
    except Exception as e:
        log.warning("Cloud test unreachable: %s", e)
        return {"ok": False, "status": "unreachable", "detail": str(e)[:120]}
    if r.status_code != 200:
        return {"ok": False, "status": f"HTTP {r.status_code}",
                "detail": "deployment may not be public (access: Anyone)"}
    try:
        data = r.json()
    except Exception:
        return {"ok": False, "status": "not JSON",
                "detail": "got HTML — usually a login/permission page; redeploy with access = Anyone"}
    if isinstance(data, dict) and "app" in data:
        return {"ok": True, "status": "connected",
                "detail": "namespace OK · " + ("data present" if data.get("app") else "empty (save once)")}
    if isinstance(data, dict) and "tickers" in data:
        return {"ok": False, "status": "old script",
                "detail": "reached the script but the rugpull namespace addon isn't installed — paste the latest Code.gs"}
    return {"ok": False, "status": "unexpected", "detail": str(data)[:120]}


def load_blob(url: str, key: str) -> dict | None:
    if not _valid(url):
        raise CloudError("URL must end in /exec")
    try:
        r = requests.get(url, params={"key": key}, timeout=TIMEOUT)
        data = r.json()
    except Exception as e:
        log.warning("Cloud load_blob failed: %s", e)
        raise CloudError(f"load failed: {e}")
    if isinstance(data, dict) and data.get("error"):
        raise CloudError(data["error"])
    return data.get("app") if isinstance(data, dict) else None


def save_blob(url: str, key: str, dataset: dict) -> dict:
    if not _valid(url):
        raise CloudError("URL must end in /exec")
    payload = {"action": "saveApp", "key": key, "dataset": dataset}
    try:
        r = requests.post(url, data=json.dumps(payload),
                          headers={"Content-Type": "text/plain;charset=utf-8"},
                          timeout=TIMEOUT)
        data = r.json()
    except Exception as e:
        log.warning("Cloud save_blob failed: %s", e)
        raise CloudError(f"save failed: {e}")
    if isinstance(data, dict) and data.get("error"):
        raise CloudError(data["error"])
    return data if isinstance(data, dict) else {"ok": True}


def load_app_state(url: str) -> dict | None:
    if not _valid(url):
        raise CloudError("URL must be the Apps Script web-app deployment ending in /exec")
    try:
        r = requests.get(url, params={"key": KEY}, timeout=TIMEOUT)
        data = r.json()
    except Exception as e:
        log.warning("Cloud load_app_state failed: %s", e)
        raise CloudError(f"load failed: {e}")
    if isinstance(data, dict) and data.get("error"):
        raise CloudError(data["error"])
    blob = data.get("app") if isinstance(data, dict) else None
    if blob is None and isinstance(data, dict) and "watchlist" in data:
        blob = data
    return blob or None


def save_app_state(url: str, watchlist: list, starred: list) -> dict:
    if not _valid(url):
        raise CloudError("URL must end in /exec (the Web App deployment URL)")
    payload = {
        "action": "saveApp",
        "key": KEY,
        "dataset": {"watchlist": watchlist, "starred": starred, "version": 1},
    }
    try:
        r = requests.post(url, data=json.dumps(payload),
                          headers={"Content-Type": "text/plain;charset=utf-8"},
                          timeout=TIMEOUT)
        data = r.json()
    except Exception as e:
        log.warning("Cloud save_app_state failed: %s", e)
        raise CloudError(f"save failed: {e}")
    if isinstance(data, dict) and data.get("error"):
        raise CloudError(data["error"])
    return data if isinstance(data, dict) else {"ok": True}


APPS_SCRIPT_ADDON = r'''
// ---- Rugpull AI Hardcore app-state add-on (namespaced; does NOT touch tickers) ----
function _rugpullGet(key) {
  var raw = PropertiesService.getScriptProperties().getProperty('app__' + key);
  return { app: raw ? JSON.parse(raw) : null };
}

function _rugpullSave(key, dataset) {
  PropertiesService.getScriptProperties()
    .setProperty('app__' + key, JSON.stringify(dataset));
  return { ok: true, key: key };
}

// In doGet(e): if (e && e.parameter && e.parameter.key) {
//   return ContentService.createTextOutput(JSON.stringify(_rugpullGet(e.parameter.key)))
//     .setMimeType(ContentService.MimeType.JSON);
// }
// In doPost(e) after parsing req: if (req && req.action === 'saveApp') {
//   return ContentService.createTextOutput(JSON.stringify(_rugpullSave(req.key, req.dataset)))
//     .setMimeType(ContentService.MimeType.JSON);
// }
'''
