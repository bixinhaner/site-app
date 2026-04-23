from datetime import datetime

from app.models.inspection import (
    CheckItemStatusEnum,
    InspectionCheckItem,
    InspectionStatusEnum,
    SiteInspection,
)
from app.services.cell_generator import CellInfo
from app.services.inspection_template_sync import (
    InspectionGenerationContext,
    _apply_spec_to_check_item,
    iter_template_check_item_specs,
)


def test_template_sync_preserves_existing_equipment_sn():
    inspection = SiteInspection(
        id="inspection-template-sn",
        site_id=1,
        template_id="template-1",
        inspector_id=1,
        status=InspectionStatusEnum.IN_PROGRESS,
    )
    check_item = InspectionCheckItem(
        id="check-item-1",
        inspection_id=inspection.id,
        item_id="item_device_cell_2_B20",
        template_item_id="item_device",
        item_name="Device - 2_B20",
        category_id="device-category",
        category_name="Device",
        sector_id="2",
        band="B20",
        cell_id="2_B20",
        equipment_sn="12020008672585D0023",
        required_type="photo",
        status=CheckItemStatusEnum.PENDING,
        fields=[],
        is_active=True,
        removed_by_template=False,
    )
    spec = {
        "item_id": "item_device_cell_2_B20",
        "template_item_id": "item_device",
        "item_name": "Device - 2_B20",
        "description": None,
        "category_id": "device-category",
        "category_name": "Device",
        "sector_id": "2",
        "band": "B20",
        "cell_id": "2_B20",
        "equipment_sn": None,
        "required_type": "photo",
        "fields": [],
    }

    changed, reopened = _apply_spec_to_check_item(
        None,
        inspection,
        check_item,
        spec,
        datetime(2026, 4, 24),
    )

    assert changed is False
    assert reopened is False
    assert check_item.equipment_sn == "12020008672585D0023"


def test_new_device_specs_can_still_carry_initial_equipment_sn():
    template_data = {
        "check_categories": [
            {
                "category_id": "device-category",
                "category_name": "Device",
                "level_type": "device",
                "items": [
                    {
                        "item_id": "item_device",
                        "item_name": "Device",
                        "required_type": "photo",
                        "fields": [],
                    }
                ],
            }
        ]
    }
    context = InspectionGenerationContext(
        devices=[CellInfo(sector_id="2", band="B20", cell_id="2_B20")],
        sectors=["2"],
        carrier_cells=[],
        equipment_sn_map={("2", "B20"): "12020008672585D0023"},
    )

    specs = iter_template_check_item_specs(template_data, context)

    assert len(specs) == 1
    assert specs[0]["equipment_sn"] == "12020008672585D0023"


if __name__ == "__main__":
    test_template_sync_preserves_existing_equipment_sn()
    test_new_device_specs_can_still_carry_initial_equipment_sn()
    print("template sync equipment SN tests passed")
