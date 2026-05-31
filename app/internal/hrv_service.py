"""
HRV Calculation Service
心率变异性(HRV)计算服务

从心率序列计算HRV指标，或从原始RRI数据计算精确HRV指标
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import math


@dataclass
class HRVMetrics:
    """HRV指标数据类"""
    rmssd: float  # RMSSD值 (ms)
    sdnn: float   # SDNN值 (ms)
    pnn50: float # pNN50值 (%)
    heart_rate: float  # 平均心率 (BPM)
    raw_rri: Optional[List[int]] = None  # 原始RRI数据


@dataclass
class HRVStatus:
    """HRV状态判定结果"""
    status: str  # relaxed / normal / stressed / anxious
    level: int  # 1-5, 1=深度放松, 5=焦虑状态
    description: str
    bpm_adjustment: int  # 建议的BPM调整值


class HRVService:
    """
    HRV计算服务

    支持两种模式：
    1. 心率序列模式：从心率数组估算HRV指标（精度有限）
    2. RRI模式：从原始RRI数据计算精确HRV指标（华为手表支持）
    """

    # HRV状态阈值（基于RMSSD）
    RMSSD_RELAXED = 80   # >80ms 深度放松
    RMSSD_NORMAL = 50    # 50-80ms 正常放松
    RMSSD_STRESSED = 30  # 30-50ms 中度压力
    RMSSD_ANXIOUS = 15   # <15ms 焦虑状态

    def calculate_metrics_from_heart_rates(self, heart_rates: List[float], interval_seconds: float = 1.0) -> HRVMetrics:
        """
        从心率序列估算HRV指标（精度有限，Apple Watch模式）

        Args:
            heart_rates: 心率序列 (BPM)
            interval_seconds: 心率采样间隔（秒）

        Returns:
            HRVMetrics: HRV指标
        """
        if len(heart_rates) < 2:
            return HRVMetrics(rmssd=0, sdnn=0, pnn50=0, heart_rate=sum(heart_rates)/len(heart_rates) if heart_rates else 0)

        # 将心率转换为RRI估算值 (ms)
        # RRI = 60000 / BPM
        rri_estimates = [60000.0 / hr for hr in heart_rates if hr > 0]

        return self._calculate_from_rri(rri_estimates)

    def calculate_metrics_from_rri(self, rri_data: List[int]) -> HRVMetrics:
        """
        从原始RRI数据计算精确HRV指标（华为手表模式）

        Args:
            rri_data: 原始RRI数据 (毫秒)

        Returns:
            HRVMetrics: HRV指标
        """
        if len(rri_data) < 2:
            return HRVMetrics(rmssd=0, sdnn=0, pnn50=0, heart_rate=0, raw_rri=rri_data)

        return self._calculate_from_rri(rri_data)

    def _calculate_from_rri(self, rri_data: List[float]) -> HRVMetrics:
        """
        内部方法：从RRI数据计算HRV指标

        Args:
            rri_data: RRI数据 (毫秒)

        Returns:
            HRVMetrics: HRV指标
        """
        n = len(rri_data)
        avg_rri = sum(rri_data) / n

        # 1. 计算平均心率
        heart_rate = 60000.0 / avg_rri if avg_rri > 0 else 0

        # 2. 计算SDNN (标准差)
        variance = sum((rri - avg_rri) ** 2 for rri in rri_data) / n
        sdnn = math.sqrt(variance)

        # 3. 计算RMSSD (相邻RRI差的方均根)
        diff_squared = [(rri_data[i + 1] - rri_data[i]) ** 2 for i in range(n - 1)]
        rmssd = math.sqrt(sum(diff_squared) / (n - 1)) if diff_squared else 0

        # 4. 计算pNN50 (相邻RRI差>50ms的比例)
        nn50_count = sum(1 for i in range(n - 1) if abs(rri_data[i + 1] - rri_data[i]) > 50)
        pnn50 = (nn50_count / (n - 1)) * 100 if n > 1 else 0

        return HRVMetrics(
            rmssd=rmssd,
            sdnn=sdnn,
            pnn50=pnn50,
            heart_rate=heart_rate,
            raw_rri=[int(r) for r in rri_data]
        )

    def determine_status(self, metrics: HRVMetrics) -> HRVStatus:
        """
        根据HRV指标判断当前状态

        Args:
            metrics: HRV指标

        Returns:
            HRVStatus: 状态判定结果
        """
        rmssd = metrics.rmssd

        if rmssd >= self.RMSSD_RELAXED:
            return HRVStatus(
                status="relaxed",
                level=1,
                description="深度放松，副交感神经主导",
                bpm_adjustment=0
            )
        elif rmssd >= self.RMSSD_NORMAL:
            return HRVStatus(
                status="normal",
                level=2,
                description="正常放松，交感副交感平衡",
                bpm_adjustment=0
            )
        elif rmssd >= self.RMSSD_STRESSED:
            return HRVStatus(
                status="stressed",
                level=3,
                description="中度压力，交感神经上升",
                bpm_adjustment=-5
            )
        elif rmssd >= self.RMSSD_ANXIOUS:
            return HRVStatus(
                status="anxious",
                level=4,
                description="高压力，交感神经主导",
                bpm_adjustment=-10
            )
        else:
            return HRVStatus(
                status="anxious",
                level=5,
                description="焦虑状态，过度激活",
                bpm_adjustment=-15
            )

    def calculate_bpm_adjustment(self, status: HRVStatus, current_bpm: int) -> Tuple[int, int]:
        """
        根据HRV状态计算BPM调整

        Args:
            status: HRV状态
            current_bpm: 当前BPM

        Returns:
            Tuple[int, int]: (调整值, 目标BPM)
        """
        target_bpm = max(40, current_bpm + status.bpm_adjustment)
        return status.bpm_adjustment, target_bpm

    def calculate_healing_progress(self, initial_hrv: float, current_hrv: float, target_hrv: float = 65.0) -> int:
        """
        计算疗愈进度百分比

        Args:
            initial_hrv: 初始HRV值
            current_hrv: 当前HRV值
            target_hrv: 目标HRV值（默认65ms为正常放松下限）

        Returns:
            int: 疗愈进度百分比 (0-100)
        """
        if initial_hrv >= current_hrv:
            return 100

        # 进度 = (当前 - 初始) / (目标 - 初始) * 100
        progress = ((current_hrv - initial_hrv) / (target_hrv - initial_hrv)) * 100
        return min(100, max(0, int(progress)))


# 全局实例
hrv_service = HRVService()