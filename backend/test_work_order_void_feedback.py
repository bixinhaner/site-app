from app.api.work_orders import _format_bound_device_void_block_reason


def test_format_bound_device_void_block_reason_lists_devices_and_next_step():
    message = _format_bound_device_void_block_reason(
        [
            {"sn": "12020008972619B0003", "sector_id": "1", "band": "N50"},
            {"sn": "12020008972619B0047", "sector_id": "2", "band": "N50"},
        ]
    )

    assert "仍绑定 2 台设备" in message
    assert "12020008972619B0003（扇区 1 / N50）" in message
    assert "12020008972619B0047（扇区 2 / N50）" in message
    assert "工单执行人在 App 对应工单中解绑设备" in message


def test_format_bound_device_void_block_reason_limits_long_lists():
    bindings = [
        {"sn": f"SN{index:02d}", "sector_id": str(index), "band": "N50"}
        for index in range(1, 9)
    ]

    message = _format_bound_device_void_block_reason(bindings, preview_limit=3)

    assert "仍绑定 8 台设备" in message
    assert "SN03" in message
    assert "SN04" not in message
    assert "另有 5 台" in message


if __name__ == "__main__":
    test_format_bound_device_void_block_reason_lists_devices_and_next_step()
    test_format_bound_device_void_block_reason_limits_long_lists()
    print("work order void feedback tests passed")
