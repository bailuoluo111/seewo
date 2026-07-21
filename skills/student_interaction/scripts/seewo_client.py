#!/usr/bin/env python3
"""
seewo_client.py — 希沃课堂观察数据的最小 HTTP 客户端（自包含，无外部项目依赖）

本文件随每个 Skill 独立分发，使 Skill 可单独装配到任意 Agent 中。
只提供最基础的能力：加载凭证、发起 API 请求、取课程信息。
各 Skill 专属的提取逻辑放在同目录的 extract.py 中。

认证凭证按以下顺序解析（先到先得）：
  1. 构造函数参数 token / username
  2. 环境变量 SEEWO_TOKEN / SEEWO_USERNAME
  3. SEEWO_CONFIG.md（在当前目录及各级父目录中查找）
     文件内需包含一行： cookie: x-token=xxx; x-username=yyy
"""

import os
import re
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class SeewoClient:
    """希沃数据 API 的最小客户端。"""

    API_HOST = "https://edulyse.seewo.com"

    def __init__(self, report_id: str, token: str = None, username: str = None):
        self.report_id = report_id

        if not token or not username:
            cfg = self._load_config()
            token = token or os.environ.get("SEEWO_TOKEN") or cfg.get("token")
            username = username or os.environ.get("SEEWO_USERNAME") or cfg.get("username")
        if not token or not username:
            raise ValueError(
                "缺少 token/username：请通过构造参数、环境变量 "
                "SEEWO_TOKEN/SEEWO_USERNAME，或 SEEWO_CONFIG.md 提供"
            )

        self.token = token
        self.username = username
        self.api_template = f"{self.API_HOST}/api/analyse/course/report/{report_id}/{{atype}}"
        self.headers = {
            "Cookie": f"x-token={token}; x-samesite-none-token={token}; x-username={username}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": f"https://easiinsight.seewo.com/report/detail/{report_id}/home",
        }
        self._course_info_cache: Optional[Dict[str, Any]] = None

    @staticmethod
    def _load_config() -> Dict[str, str]:
        """在当前目录及各级父目录中查找 SEEWO_CONFIG.md 并解析凭证。"""
        for base in [Path.cwd(), *Path.cwd().parents, Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
            cfg = base / "SEEWO_CONFIG.md"
            if cfg.exists():
                try:
                    content = cfg.read_text(encoding="utf-8")
                    m = re.search(r"^cookie:\s*(.+)$", content, re.MULTILINE)
                    if m:
                        s = m.group(1)
                        tok = re.search(r"x-token=([^;]+)", s)
                        usr = re.search(r"x-username=([^;]+)", s)
                        return {
                            "token": tok.group(1).strip() if tok else None,
                            "username": usr.group(1).strip() if usr else None,
                        }
                except Exception:
                    pass
        return {}

    def fetch(self, analysis_type: str) -> Optional[Dict[str, Any]]:
        """调用某个分析类型接口，返回 data 字段，失败返回 None。"""
        url = self.api_template.format(atype=analysis_type)
        try:
            resp = requests.get(url, headers=self.headers, timeout=20)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if "code" in data and data["code"] != 0:
                return None
            return data.get("data", {})
        except Exception:
            return None

    def get_course_info(self) -> Dict[str, Any]:
        """取课程基础信息（含学段，供部分 Skill 使用）。"""
        if self._course_info_cache:
            return self._course_info_cache
        data = self.fetch("studentStudyStatistic")
        if not data:
            return {}

        def ts(v):
            return datetime.fromtimestamp(v / 1000).strftime("%Y-%m-%d %H:%M:%S") if v else None

        info = {
            "课程ID": data.get("virtualClassUid"),
            "课程名称": data.get("courseName"),
            "教师姓名": data.get("teacherName"),
            "学校名称": data.get("schoolName"),
            "学段": data.get("stageName"),
            "学科": data.get("subjectName"),
            "教室": data.get("roomName"),
            "上课时间": ts(data.get("classStartTime")),
            "下课时间": ts(data.get("classFinishTime")),
        }
        self._course_info_cache = info
        return info
