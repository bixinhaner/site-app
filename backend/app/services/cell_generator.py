"""
小区生成服务
根据站点规划数据生成小区配置，用于检查项生成
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.planning import SitePlanning, SitePlanningSector


class CellInfo:
    """小区信息"""
    def __init__(self, sector_id: str, band: str, cell_id: str, azimuth: float = None, downtilt: float = None):
        self.sector_id = sector_id
        self.band = band
        self.cell_id = cell_id
        self.azimuth = azimuth
        self.downtilt = downtilt

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sector_id": self.sector_id,
            "band": self.band,
            "cell_id": self.cell_id,
            "azimuth": self.azimuth,
            "downtilt": self.downtilt
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
        基于站点规划数据生成小区列表
        
        Args:
            db: 数据库会话
            site_id: 站点ID
            
        Returns:
            小区信息列表
        """
        planning = CellGenerator.get_site_planning(db, site_id)
        cells = []
        
        if not planning:
            # 如果没有规划数据，使用默认配置（3扇区，1个频段）
            for sector_num in range(1, 4):
                cell_id = f"{sector_num}_default"
                cells.append(CellInfo(
                    sector_id=str(sector_num),
                    band="default",
                    cell_id=cell_id
                ))
            return cells
        
        # 根据规划数据生成小区
        for sector in planning.sectors:
            sector_id = str(sector.sector_index)
            sector_bands = sector.bands or []
            
            # 如果扇区没有配置频段，使用站点级别的频段
            if not sector_bands:
                sector_bands = planning.bands or ["default"]
            
            # 为每个频段生成一个小区
            for band in sector_bands:
                cell_id = f"{sector_id}_{band}"
                cells.append(CellInfo(
                    sector_id=sector_id,
                    band=band,
                    cell_id=cell_id,
                    azimuth=sector.azimuth_deg,
                    downtilt=sector.downtilt_deg
                ))
        
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