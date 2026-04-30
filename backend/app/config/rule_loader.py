import os
import threading
from functools import lru_cache
from typing import Dict, List, Optional

import yaml


class RuleConfig:
    """从 YAML 配置文件加载 Agent 规则，支持热加载"""

    _instance: Optional["RuleConfig"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "RuleConfig":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config",
            "agent_rules.yaml",
        )
        self._intent_rules: Dict[str, List[str]] = {}
        self._fast_track_intents: List[str] = []
        self._product_intents: List[str] = []
        self._templates: Dict[str, str] = {}
        self._loading_hints: Dict[str, str] = {}
        self._mtime: float = 0.0
        self._load()
        self._loaded = True

    def _load(self):
        """从 YAML 文件加载配置"""
        if not os.path.exists(self._config_path):
            raise FileNotFoundError(f"规则配置文件不存在: {self._config_path}")

        with open(self._config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self._intent_rules = {}
        for intent_name, intent_config in data.get("intents", {}).items():
            self._intent_rules[intent_name] = intent_config.get("keywords", [])

        self._fast_track_intents = data.get("fast_track_intents", [])
        self._product_intents = data.get("product_intents", [])
        self._templates = data.get("templates", {})
        self._loading_hints = data.get("loading_hints", {})
        self._mtime = os.path.getmtime(self._config_path)

    def _check_reload(self):
        """检查文件是否变更，如果变更则重新加载"""
        try:
            current_mtime = os.path.getmtime(self._config_path)
            if current_mtime > self._mtime:
                self._load()
        except OSError:
            pass

    @property
    def intent_rules(self) -> Dict[str, List[str]]:
        """意图关键词规则 {intent_name: [keywords]}"""
        self._check_reload()
        return self._intent_rules

    @property
    def fast_track_intents(self) -> set:
        """快速通道意图集合"""
        self._check_reload()
        return set(self._fast_track_intents)

    @property
    def product_intents(self) -> set:
        """产品相关意图集合"""
        self._check_reload()
        return set(self._product_intents)

    @property
    def templates(self) -> Dict[str, str]:
        """模板回复 {intent_name: template_text}"""
        self._check_reload()
        return self._templates

    @property
    def loading_hints(self) -> Dict[str, str]:
        """加载阶段提示语 {stage: hint_text}"""
        self._check_reload()
        return self._loading_hints


@lru_cache()
def get_rule_config() -> RuleConfig:
    return RuleConfig()


rule_config = get_rule_config()
