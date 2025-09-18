#!/usr/bin/env python3
"""
Quick script to smoke test Site Planning APIs against a running server (http://localhost:8000)
Make sure to run: python3 start_backend.py (seeds admin/admin123)
"""

import requests
import json

BASE_URL = "http://localhost:8000"


def login_admin():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
    r.raise_for_status()
    data = r.json()
    return data["access_token"], data["user"]


def ensure_site(token):
    headers = {"Authorization": f"Bearer {token}"}
    # try to list sites
    r = requests.get(f"{BASE_URL}/api/sites/?limit=1", headers=headers)
    r.raise_for_status()
    sites = r.json()
    if sites:
        return sites[0]["id"]
    # create one
    payload = {
        "site_code": "TEST-PLANNING-001",
        "site_name": "规划测试站点",
        "site_type": "macro",
        "address": "测试地址",
    }
    r = requests.post(f"{BASE_URL}/api/sites/", headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["id"]


def put_planning(token, site_id):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "bands": ["n41"],
        "sector_count": 3,
        "notes": "initial planning via test",
        "sectors": [
            {"sector_index": 1, "azimuth_deg": 0, "downtilt_deg": 5, "bands": ["n41"]},
            {"sector_index": 2, "azimuth_deg": 120, "downtilt_deg": 5, "bands": ["n41"]},
            {"sector_index": 3, "azimuth_deg": 240, "downtilt_deg": 5, "bands": ["n41"]},
        ],
        "antenna_ports": [
            {"port_label": "ANT1", "sector_index": 1, "band": "n41", "mimo_chain": "4x4"}
        ],
        "switch_ports": [
            {"port_no": "GE1", "vlan_ids": [201, 202], "is_uplink": True, "poe": False, "description": "Uplink"}
        ],
        "base_version": 0,
    }
    r = requests.put(f"{BASE_URL}/api/sites/{site_id}/planning", headers=headers, data=json.dumps(payload))
    print("PUT planning:", r.status_code, r.text)
    r.raise_for_status()


def get_current_and_versions(token, site_id):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/api/sites/{site_id}/planning", headers=headers)
    print("GET current planning:", r.status_code, r.text)
    r.raise_for_status()
    r2 = requests.get(f"{BASE_URL}/api/sites/{site_id}/planning/versions", headers=headers)
    print("GET versions:", r2.status_code, r2.text)
    r2.raise_for_status()


def get_logs(token, site_id):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/api/sites/{site_id}/planning/logs", headers=headers)
    print("GET logs:", r.status_code, r.text)
    r.raise_for_status()


def main():
    token, user = login_admin()
    print("Logged in as:", user.get("username"))
    site_id = ensure_site(token)
    print("Using site:", site_id)
    try:
        put_planning(token, site_id)
        get_current_and_versions(token, site_id)
        get_logs(token, site_id)
        print("✅ Site planning API smoke test completed")
    except Exception as e:
        print("❌ Test failed:", e)


if __name__ == "__main__":
    main()

