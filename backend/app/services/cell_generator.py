"""
小区生成服务
根据站点规划数据生成小区配置，用于检查项生成
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from sqlalchemy.orm import Session
from app.models.planning import SitePlanning, SitePlanningCell, SitePlanningSector


class CellInfo:
    """小区信息"""
    def __init__(
        self,
        sector_id: str,
        band: str,
        cell_id: str,
        azimuth: float = None,
        downtilt: float = None,
        earfcn: Optional[int] = None,
    ):
        self.sector_id = sector_id
        self.band = band
        self.cell_id = cell_id
        self.azimuth = azimuth
        self.downtilt = downtilt
        self.earfcn = earfcn

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sector_id": self.sector_id,
            "band": self.band,
            "cell_id": self.cell_id,
            "azimuth": self.azimuth,
            "downtilt": self.downtilt,
            "earfcn": self.earfcn,
        }


class CellGenerator:
    """小区生成器"""
    
    @staticmethod
    def get_site_planning(db: Session, site_id: int) -> Optional[SitePlanning]:
        """获取站点当前规划数据"""
        return (
            db.query(SitePlanning)
            .filter(SitePlanning.site_id == site_id)
            .filter(SitePlanning.is_current == True)
            .first()
        )
    
    @staticmethod
    def generate_cells_from_planning(db: Session, site_id: int) -> List[CellInfo]:
        """
        基于站点规划数据生成小区列表（历史行为：扇区 × Band）

        注意：该方法生成的是“设备维度”（扇区×Band）的列表，用于旧版所谓“cell_specific”检查项。
        真正的小区维度（扇区×Band×EARFCN）请使用 generate_cells_from_lld。
        
        Args:
            db: 数据库会话
            site_id: 站点ID
            
        Returns:
            小区信息列表
        """
        return CellGenerator.generate_devices_from_planning(db, site_id)

    @staticmethod
    def _calc_total_downtilt(mechanical: Optional[float], electrical: Optional[float]) -> Optional[float]:
        mech = float(mechanical) if mechanical is not None else None
        elec = float(electrical) if electrical is not None else None
        if mech is None and elec is None:
            return None
        return float(mech or 0.0) + float(elec or 0.0)

    @staticmethod
    def generate_devices_from_planning(db: Session, site_id: int) -> List[CellInfo]:
        """
        生成“设备维度”（扇区 × Band）的列表。

        优先使用 LLD 明细（site_planning_cells）聚合生成，
        若无 LLD 明细则回退到 site_planning.sectors/bands 的汇总信息。
        """
        planning = CellGenerator.get_site_planning(db, site_id)

        # 优先：LLD 明细（更准确，且可覆盖双载波/多行同设备的情况）
        if planning:
            rows = (
                db.query(SitePlanningCell)
                .filter(SitePlanningCell.planning_id == planning.id)
                .filter(SitePlanningCell.site_id == site_id)
                .all()
            )
            if rows:
                devices: List[CellInfo] = []
                seen: Set[Tuple[int, str]] = set()

                # 排序保证稳定输出：按扇区、Band
                rows_sorted = sorted(
                    rows,
                    key=lambda r: (
                        int(r.local_cell_id or 0),
                        str(r.band_code or ""),
                        int(r.frequency or 0),
                    ),
                )

                for r in rows_sorted:
                    if r.local_cell_id is None or not r.band_code:
                        continue
                    key = (int(r.local_cell_id), str(r.band_code))
                    if key in seen:
                        continue
                    seen.add(key)

                    sector_id = str(int(r.local_cell_id))
                    band = str(r.band_code)
                    cell_id = f"{sector_id}_{band}"
                    devices.append(
                        CellInfo(
                            sector_id=sector_id,
                            band=band,
                            cell_id=cell_id,
                            azimuth=float(r.azimuth_deg) if r.azimuth_deg is not None else None,
                            downtilt=CellGenerator._calc_total_downtilt(
                                r.mechanical_downtilt_deg, r.electrical_downtilt_deg
                            ),
                        )
                    )

                return devices

        # 回退：仅有汇总规划（无 LLD 明细）
        cells: List[CellInfo] = []
        if not planning:
            # 如果没有规划数据，使用默认配置（3扇区，1个频段）
            for sector_num in range(1, 4):
                cell_id = f"{sector_num}_default"
                cells.append(CellInfo(sector_id=str(sector_num), band="default", cell_id=cell_id))
            return cells

        for sector in planning.sectors:
            sector_id = str(sector.sector_index)
            sector_bands = sector.bands or []

            if not sector_bands:
                sector_bands = planning.bands or ["default"]

            for band in sector_bands:
                cell_id = f"{sector_id}_{band}"
                cells.append(
                    CellInfo(
                        sector_id=sector_id,
                        band=band,
                        cell_id=cell_id,
                        azimuth=sector.azimuth_deg,
                        downtilt=sector.downtilt_deg,
                    )
                )

        return cells

    @staticmethod
    def generate_cells_from_lld(db: Session, site_id: int) -> List[CellInfo]:
        """
        生成“真正小区维度”（扇区 × Band × EARFCN）的列表。

        说明：
        - 这里的 EARFCN 来自 SitePlanningCell.frequency（LLD 模板中 4G/5G 都叫 EARFCN）。
        - 仅依赖 LLD 明细表（site_planning_cells），无明细时返回空列表（由上层决定是否报错）。
        """
        planning = CellGenerator.get_site_planning(db, site_id)
        if not planning:
            return []

        rows = (
            db.query(SitePlanningCell)
            .filter(SitePlanningCell.planning_id == planning.id)
            .filter(SitePlanningCell.site_id == site_id)
            .all()
        )
        if not rows:
            return []

        cells: List[CellInfo] = []
        seen: Set[Tuple[int, str, str]] = set()

        rows_sorted = sorted(
            rows,
            key=lambda r: (
                int(r.local_cell_id or 0),
                str(r.band_code or ""),
                int(r.frequency or 0),
            ),
        )

        for r in rows_sorted:
            if r.local_cell_id is None or not r.band_code:
                continue

            earfcn = r.frequency
            earfcn_str = str(int(earfcn)) if earfcn is not None else "NA"
            key = (int(r.local_cell_id), str(r.band_code), earfcn_str)
            if key in seen:
                continue
            seen.add(key)

            sector_id = str(int(r.local_cell_id))
            band = str(r.band_code)
            cell_id = f"{sector_id}_{band}_{earfcn_str}"
            cells.append(
                CellInfo(
                    sector_id=sector_id,
                    band=band,
                    cell_id=cell_id,
                    azimuth=float(r.azimuth_deg) if r.azimuth_deg is not None else None,
                    downtilt=CellGenerator._calc_total_downtilt(
                        r.mechanical_downtilt_deg, r.electrical_downtilt_deg
                    ),
                    earfcn=int(earfcn) if earfcn is not None else None,
                )
            )

        return cells
    
    @staticmethod
    def generate_cells_legacy(sector_count: int = 3, bands: List[str] = None) -> List[CellInfo]:
        """
        传统方式生成小区（向后兼容）
        
        Args:
            sector_count: 扇区数量
            bands: 频段列表
            
        Returns:
            小区信息列表
        """
        if bands is None:
            bands = ["n41"]  # 默认频段
            
        cells = []
        for sector_num in range(1, sector_count + 1):
            for band in bands:
                cell_id = f"{sector_num}_{band}"
                cells.append(CellInfo(
                    sector_id=str(sector_num),
                    band=band,
                    cell_id=cell_id
                ))
        
        return cells
    
    @staticmethod
    def get_cells_summary(cells: List[CellInfo]) -> Dict[str, Any]:
        """
        获取小区配置摘要
        
        Args:
            cells: 小区列表
            
        Returns:
            摘要信息
        """
        sector_count = len(set(cell.sector_id for cell in cells))
        bands = list(set(cell.band for cell in cells))
        total_cells = len(cells)
        
        return {
            "total_cells": total_cells,
            "sector_count": sector_count,
            "bands": bands,
            "cells_per_sector": total_cells / sector_count if sector_count > 0 else 0
        }
