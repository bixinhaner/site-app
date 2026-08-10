# Inventory List Design QA

## Reference

- `outputs/inventory-list-design-20260810/final-flow/01-main-equipment-by-equipment.png`
- `outputs/inventory-list-design-20260810/final-flow/02-main-equipment-by-warehouse.png`
- `outputs/inventory-list-design-20260810/final-flow/03-main-equipment-sn-drawer.png`
- `outputs/inventory-list-design-20260810/final-flow/04-auxiliary-by-equipment.png`
- `outputs/inventory-list-design-20260810/final-flow/05-auxiliary-by-warehouse.png`
- `outputs/inventory-list-design-20260810/final-flow/06-auxiliary-stock-distribution-drawer.png`
- `outputs/inventory-list-design-20260810/final-flow/07-auxiliary-outbound-drawer.png`
- `outputs/inventory-list-design-20260810/final-flow/08-filter-empty-state.png`

## Validation

- Viewports: 1024 x 900, 1440 x 900 and 1920 x 883.
- Main equipment: KPI filters, equipment/warehouse grouping, zero-stock toggle, URL state, SN drawer and empty results checked with local database data.
- Auxiliary material: equipment/warehouse grouping, zero-stock and restock filters, stock distribution, outstanding outbound and full transaction drawers checked with local database data.
- Count consistency: main status sum equals device total; auxiliary outstanding quantity is derived from stock-out minus received returns and matches its drawer total.
- Responsive layout: page width, result area and drawer shells have no horizontal overflow at both validation widths; table columns share remaining width and stay readable.
- Internationalization: Chinese, English and Indonesian labels and common inventory units render without clipped controls or table headers at 1440 px.
- Empty, loading and error states remain inside the table region and preserve toolbar position.

## Fixes During QA

- Aligned auxiliary overview and detail calculations to transaction-ledger outstanding quantities.
- Made zero-stock and restock KPI drilldowns bypass the default zero-record hiding rule.
- Removed the secondary reorder-point warning and its dedicated filter from the overview; row-level reorder-point values still show whether configuration is missing.
- Rebalanced table columns for 1440 px and wide desktops.
- Aligned tree expand icons with parent names, enlarged their pointer target, and verified mouse, Enter and Space toggling.
- Removed the ambiguous auxiliary zero-stock warehouse/material columns; zero stock remains discoverable through the KPI, switch, current quantity and row status.
- Moved category tabs before the selected category summary, reduced the summary to 72 px, kept desktop filters on one line, and merged result actions into the 42 px result-meta row. At 1440 px the table now starts at 338 px without page-level horizontal overflow.
- Increased desktop drawer width to 1080 px and constrained grid children to the drawer boundary.
- Added localized display mapping for common inventory units without changing stored values.

final result: passed
