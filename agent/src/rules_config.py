"""
Rules Configuration System with Hot-Reload Support.

This module provides runtime-configurable trading rules loaded from YAML.
Supports hot-reload via RulesConfig.reload() with fail-safe validation.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import time
from pydantic import BaseModel, Field, validator
import yaml

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Models
# =============================================================================

class TimeframeConfig(BaseModel):
    """Timeframe hierarchy configuration (Rules 1.1, 1.2)."""
    bias_timeframe: str = "1H"
    entry_timeframes: List[str] = Field(default_factory=lambda: ["15M", "5M"])
    min_candles_for_structure: int = 10
    swing_lookback: int = 2


class KillZoneWindow(BaseModel):
    """Single kill zone time window (Rule 8.1)."""
    enabled: bool = True
    start_est: str  # "HH:MM" format
    end_est: str    # "HH:MM" format

    @property
    def start_hour(self) -> int:
        return int(self.start_est.split(":")[0])

    @property
    def start_minute(self) -> int:
        return int(self.start_est.split(":")[1])

    @property
    def end_hour(self) -> int:
        return int(self.end_est.split(":")[0])

    @property
    def end_minute(self) -> int:
        return int(self.end_est.split(":")[1])


class KillZonesConfig(BaseModel):
    """All kill zone configurations (Rule 8.1)."""
    london: KillZoneWindow = Field(
        default_factory=lambda: KillZoneWindow(enabled=True, start_est="02:00", end_est="05:00")
    )
    new_york: KillZoneWindow = Field(
        default_factory=lambda: KillZoneWindow(enabled=True, start_est="07:00", end_est="10:00")
    )
    asia: KillZoneWindow = Field(
        default_factory=lambda: KillZoneWindow(enabled=False, start_est="20:00", end_est="00:00")
    )


class SilverbulletWindow(BaseModel):
    """Silverbullet time window (Rule 6.6)."""
    start_est: str
    end_est: str


class SilverbulletConfig(BaseModel):
    """Silverbullet configuration (Rule 6.6)."""
    enabled: bool = True
    windows: List[SilverbulletWindow] = Field(default_factory=lambda: [
        SilverbulletWindow(start_est="10:00", end_est="11:00"),
        SilverbulletWindow(start_est="14:00", end_est="15:00")
    ])


class RiskConfig(BaseModel):
    """Risk management configuration (Rules 7.1, 7.2)."""
    min_rr: float = 2.0
    default_risk_pct: float = 1.0
    max_risk_pct: float = 2.0
    pip_buffer: float = 0.0005
    pip_value_per_lot: float = 10.0

    @validator("min_rr")
    def min_rr_positive(cls, v):
        if v <= 0:
            raise ValueError("min_rr must be positive")
        return v

    @validator("default_risk_pct", "max_risk_pct")
    def risk_pct_range(cls, v):
        if not 0 < v <= 10:
            raise ValueError("risk percentage must be between 0 and 10")
        return v


class DisplacementConfig(BaseModel):
    """Displacement detection configuration (Rule 2.2)."""
    atr_multiplier: float = 2.0
    atr_period: int = 14


class NewsConfig(BaseModel):
    """News filter configuration (Rule 8.4)."""
    high_impact_window_minutes: int = 60
    high_impact_action: str = "BLOCK"  # BLOCK or CAUTION
    medium_impact_action: str = "CAUTION"  # CAUTION or ALLOW
    avoid_bank_holidays: bool = True


class EntryModelsConfig(BaseModel):
    """Entry model toggles (Rules 6.1-6.7)."""
    ote_enabled: bool = True           # Rule 6.1
    fvg_entry_enabled: bool = True     # Rule 6.2
    ict_2022_enabled: bool = True      # Rule 6.5
    silverbullet_enabled: bool = True  # Rule 6.6
    turtle_soup_enabled: bool = False  # Rule 6.7


class InvalidationConfig(BaseModel):
    """Trade invalidation rules (Rule 9.x)."""
    counter_trend_requires_htf_mss: bool = True
    max_trades_per_session: int = 2  # 0 = unlimited


class ConfluenceWeightsConfig(BaseModel):
    """Confluence scoring weights."""
    htf_bias_exists: int = 2
    ltf_aligned: int = 1
    fvg_or_ob_present: int = 2
    liquidity_sweep: int = 2
    pd_favorable: int = 1
    session_ok: int = 1
    news_ok: int = 1
    min_score_for_trade: int = 6


# =============================================================================
# Main Rules Configuration
# =============================================================================

class RulesConfig(BaseModel):
    """
    Master configuration container for all trading rules.

    Supports hot-reload with fail-safe validation:
    - If reload fails, previous valid config is retained
    - Validation errors are logged as warnings
    """
    version: str = "1.0"
    ruleset_name: str = "ICT Core Rules"

    timeframes: TimeframeConfig = Field(default_factory=TimeframeConfig)
    killzones: KillZonesConfig = Field(default_factory=KillZonesConfig)
    silverbullet: SilverbulletConfig = Field(default_factory=SilverbulletConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    displacement: DisplacementConfig = Field(default_factory=DisplacementConfig)
    news: NewsConfig = Field(default_factory=NewsConfig)
    entry_models: EntryModelsConfig = Field(default_factory=EntryModelsConfig)
    invalidation: InvalidationConfig = Field(default_factory=InvalidationConfig)
    confluence_weights: ConfluenceWeightsConfig = Field(default_factory=ConfluenceWeightsConfig)

    class Config:
        validate_assignment = True


# =============================================================================
# Rules Manager (Singleton with Hot-Reload)
# =============================================================================

class RulesManager:
    """
    Singleton manager for rules configuration with hot-reload support.

    Usage:
        manager = RulesManager()
        manager.load("rules/config.yaml")
        config = manager.config

        # Hot-reload
        success = manager.reload()
    """
    _instance: Optional["RulesManager"] = None
    _config: RulesConfig
    _config_path: Optional[Path] = None

    def __new__(cls) -> "RulesManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = RulesConfig()
            cls._instance._config_path = None
        return cls._instance

    @property
    def config(self) -> RulesConfig:
        """Get current rules configuration."""
        return self._config

    def load(self, path: str | Path) -> RulesConfig:
        """
        Load rules configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Loaded RulesConfig

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config validation fails
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Rules config not found: {path}")

        self._config_path = path

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self._config = self._parse_config(data)
        logger.info(f"Rules loaded from {path}: {self._config.ruleset_name} v{self._config.version}")
        return self._config

    def reload(self) -> tuple[bool, str]:
        """
        Hot-reload configuration from the last loaded path.

        Fail-safe: If reload fails, previous valid config is retained.

        Returns:
            Tuple of (success: bool, message: str)
        """
        if self._config_path is None:
            return False, "No config path set. Call load() first."

        if not self._config_path.exists():
            logger.warning(f"Config file missing: {self._config_path}")
            return False, f"Config file not found: {self._config_path}"

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            new_config = self._parse_config(data)

            # Validation passed - apply new config
            self._config = new_config
            logger.info(f"Rules hot-reloaded: {self._config.ruleset_name} v{self._config.version}")
            return True, f"Reloaded {self._config.ruleset_name} v{self._config.version}"

        except Exception as e:
            # Fail-safe: keep previous config
            logger.warning(f"Rules reload failed, keeping previous config: {e}")
            return False, f"Reload failed (previous config retained): {str(e)}"

    def _parse_config(self, data: Dict[str, Any]) -> RulesConfig:
        """Parse raw YAML data into RulesConfig with nested models."""
        config_dict = {
            "version": data.get("version", "1.0"),
            "ruleset_name": data.get("ruleset_name", "ICT Core Rules"),
        }

        # Parse nested configs
        if "timeframes" in data:
            config_dict["timeframes"] = TimeframeConfig(**data["timeframes"])

        if "killzones" in data:
            kz_data = data["killzones"]
            config_dict["killzones"] = KillZonesConfig(
                london=KillZoneWindow(**kz_data.get("london", {})) if "london" in kz_data else KillZoneWindow(enabled=True, start_est="02:00", end_est="05:00"),
                new_york=KillZoneWindow(**kz_data.get("new_york", {})) if "new_york" in kz_data else KillZoneWindow(enabled=True, start_est="07:00", end_est="10:00"),
                asia=KillZoneWindow(**kz_data.get("asia", {})) if "asia" in kz_data else KillZoneWindow(enabled=False, start_est="20:00", end_est="00:00")
            )

        if "silverbullet" in data:
            sb_data = data["silverbullet"]
            windows = [SilverbulletWindow(**w) for w in sb_data.get("windows", [])]
            config_dict["silverbullet"] = SilverbulletConfig(
                enabled=sb_data.get("enabled", True),
                windows=windows if windows else [
                    SilverbulletWindow(start_est="10:00", end_est="11:00"),
                    SilverbulletWindow(start_est="14:00", end_est="15:00")
                ]
            )

        if "risk" in data:
            config_dict["risk"] = RiskConfig(**data["risk"])

        if "displacement" in data:
            config_dict["displacement"] = DisplacementConfig(**data["displacement"])

        if "news" in data:
            config_dict["news"] = NewsConfig(**data["news"])

        if "entry_models" in data:
            config_dict["entry_models"] = EntryModelsConfig(**data["entry_models"])

        if "invalidation" in data:
            config_dict["invalidation"] = InvalidationConfig(**data["invalidation"])

        if "confluence_weights" in data:
            config_dict["confluence_weights"] = ConfluenceWeightsConfig(**data["confluence_weights"])

        return RulesConfig(**config_dict)

    def get_active_killzones(self) -> List[str]:
        """Get list of enabled kill zone names."""
        active = []
        if self._config.killzones.london.enabled:
            active.append("london")
        if self._config.killzones.new_york.enabled:
            active.append("new_york")
        if self._config.killzones.asia.enabled:
            active.append("asia")
        return active

    def get_enabled_entry_models(self) -> List[str]:
        """Get list of enabled entry model names."""
        models = []
        em = self._config.entry_models
        if em.ote_enabled:
            models.append("OTE")
        if em.fvg_entry_enabled:
            models.append("FVG")
        if em.ict_2022_enabled:
            models.append("ICT_2022")
        if em.silverbullet_enabled:
            models.append("SILVERBULLET")
        if em.turtle_soup_enabled:
            models.append("TURTLE_SOUP")
        return models


# =============================================================================
# Module-level convenience functions
# =============================================================================

_rules_manager: Optional[RulesManager] = None


def get_rules_manager() -> RulesManager:
    """Get the global RulesManager singleton."""
    global _rules_manager
    if _rules_manager is None:
        _rules_manager = RulesManager()
    return _rules_manager


def load_rules(path: str | Path = "rules/config.yaml") -> RulesConfig:
    """
    Load rules configuration from YAML file.

    Args:
        path: Path to YAML configuration file

    Returns:
        Loaded RulesConfig
    """
    return get_rules_manager().load(path)


def get_rules() -> RulesConfig:
    """Get current rules configuration."""
    return get_rules_manager().config


def reload_rules() -> tuple[bool, str]:
    """
    Hot-reload rules configuration.

    Returns:
        Tuple of (success: bool, message: str)
    """
    return get_rules_manager().reload()
