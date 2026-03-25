"""
写作目标管理系统
激励用户持续创作，追踪写作进度
"""

import json
import os
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List, Any

class GoalsService:
    """写作目标管理核心类"""

    def __init__(self, data_dir: str = "data/global"):
        self.data_dir = data_dir
        self.goals_file = os.path.join(data_dir, "writing_goals.json")
        self._ensure_data_dir()
        self._load_data()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        os.makedirs(self.data_dir, exist_ok=True)

    def _load_data(self):
        """加载目标数据"""
        if os.path.exists(self.goals_file):
            try:
                with open(self.goals_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.data = self._get_default_data()
        else:
            self.data = self._get_default_data()
            self._save_data()

    def _get_default_data(self) -> Dict:
        """获取默认数据结构"""
        return {
            "goals": [],
            "streak": {
                "current": 0,
                "best": 0,
                "last_write_date": None
            },
            "history": []
        }

    def _save_data(self):
        """保存目标数据"""
        with open(self.goals_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # ==================== 目标管理 ====================

    def create_goal(self, title: str, goal_type: str, target_value: int,
                    unit: str = "字", start_date: str = None,
                    end_date: str = None, priority: int = 0) -> Dict:
        """
        创建写作目标

        Args:
            title: 目标标题
            goal_type: daily/weekly/monthly/custom
            target_value: 目标值
            unit: 单位（字/章）
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            priority: 优先级

        Returns:
            新创建的目标
        """
        today = date.today().isoformat()

        # 根据类型自动设置日期范围
        if goal_type == "daily":
            start_date = today
            end_date = today
        elif goal_type == "weekly":
            # 本周（周一到周日）
            today_date = date.today()
            start = today_date - timedelta(days=today_date.weekday())
            end = start + timedelta(days=6)
            start_date = start.isoformat()
            end_date = end.isoformat()
        elif goal_type == "monthly":
            # 本月
            today_date = date.today()
            start_date = date(today_date.year, today_date.month, 1).isoformat()
            # 计算月末
            if today_date.month == 12:
                end_date = date(today_date.year + 1, 1, 1).isoformat()
            else:
                next_month = date(today_date.year, today_date.month + 1, 1)
                end_date = (next_month - timedelta(days=1)).isoformat()

        goal = {
            "id": len(self.data["goals"]) + 1,
            "title": title,
            "type": goal_type,
            "target_value": target_value,
            "current_value": 0,
            "unit": unit,
            "start_date": start_date or today,
            "end_date": end_date or today,
            "status": "active",
            "priority": priority,
            "created_at": today
        }

        self.data["goals"].append(goal)
        self._save_data()
        return goal

    def update_goal(self, goal_id: int, **kwargs) -> Optional[Dict]:
        """更新目标"""
        for goal in self.data["goals"]:
            if goal["id"] == goal_id:
                goal.update(kwargs)
                self._save_data()
                return goal
        return None

    def delete_goal(self, goal_id: int) -> bool:
        """删除目标"""
        original_len = len(self.data["goals"])
        self.data["goals"] = [g for g in self.data["goals"] if g["id"] != goal_id]
        if len(self.data["goals"]) < original_len:
            self._save_data()
            return True
        return False

    def get_goal(self, goal_id: int) -> Optional[Dict]:
        """获取单个目标"""
        for goal in self.data["goals"]:
            if goal["id"] == goal_id:
                return goal
        return None

    def get_active_goals(self) -> List[Dict]:
        """获取所有活跃目标"""
        today = date.today().isoformat()
        return [g for g in self.data["goals"]
                if g["status"] == "active" and g["end_date"] >= today]

    def get_goals_by_type(self, goal_type: str) -> List[Dict]:
        """按类型获取目标"""
        return [g for g in self.data["goals"] if g["type"] == goal_type]

    # ==================== 进度更新 ====================

    def add_progress(self, words: int, chapters: int = 0, book_name: str = None):
        """
        添加写作进度

        Args:
            words: 新增字数
            chapters: 新增章节数
            book_name: 书名（可选）
        """
        today = date.today().isoformat()

        # 更新所有活跃目标
        for goal in self.data["goals"]:
            if goal["status"] != "active":
                continue

            # 检查是否在日期范围内
            if goal["start_date"] <= today <= goal["end_date"]:
                if goal["unit"] == "字":
                    goal["current_value"] += words
                elif goal["unit"] == "章":
                    goal["current_value"] += chapters

                # 检查是否完成
                if goal["current_value"] >= goal["target_value"]:
                    goal["status"] = "completed"

        # 更新连续写作天数
        self._update_streak(words)

        # 记录历史
        self._add_history(today, words, chapters, book_name)

        self._save_data()

    def _update_streak(self, words: int):
        """更新连续写作天数"""
        today = date.today()
        today_str = today.isoformat()

        if words > 0:
            last_write = self.data["streak"]["last_write_date"]

            if last_write is None:
                # 首次写作
                self.data["streak"]["current"] = 1
            elif last_write == (today - timedelta(days=1)).isoformat():
                # 连续写作
                self.data["streak"]["current"] += 1
            elif last_write == today_str:
                # 同一天，不增加
                pass
            else:
                # 中断了
                self.data["streak"]["current"] = 1

            # 更新最佳记录
            if self.data["streak"]["current"] > self.data["streak"]["best"]:
                self.data["streak"]["best"] = self.data["streak"]["current"]

            self.data["streak"]["last_write_date"] = today_str

    def _add_history(self, date_str: str, words: int, chapters: int, book_name: str):
        """添加历史记录"""
        # 查找今天的记录
        for record in self.data["history"]:
            if record["date"] == date_str:
                record["words"] += words
                record["chapters"] += chapters
                return

        # 新建今天的记录
        self.data["history"].append({
            "date": date_str,
            "words": words,
            "chapters": chapters,
            "book_name": book_name
        })

        # 只保留最近30天的历史
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        self.data["history"] = [h for h in self.data["history"] if h["date"] >= cutoff]

    # ==================== 统计信息 ====================

    def get_streak(self) -> Dict:
        """获取连续写作信息"""
        return self.data["streak"]

    def get_today_progress(self) -> Dict:
        """获取今日写作进度"""
        today = date.today().isoformat()
        today_record = next(
            (h for h in self.data["history"] if h["date"] == today),
            {"date": today, "words": 0, "chapters": 0}
        )

        # 获取今日目标
        daily_goals = [g for g in self.get_active_goals() if g["type"] == "daily"]

        return {
            "words": today_record.get("words", 0),
            "chapters": today_record.get("chapters", 0),
            "daily_goals": daily_goals
        }

    def get_week_stats(self) -> Dict:
        """获取本周统计"""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        week_words = 0
        week_chapters = 0

        for record in self.data["history"]:
            record_date = date.fromisoformat(record["date"])
            if week_start <= record_date <= week_end:
                week_words += record.get("words", 0)
                week_chapters += record.get("chapters", 0)

        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "words": week_words,
            "chapters": week_chapters
        }

    def get_month_stats(self) -> Dict:
        """获取本月统计"""
        today = date.today()
        month_start = date(today.year, today.month, 1)

        month_words = 0
        month_chapters = 0

        for record in self.data["history"]:
            record_date = date.fromisoformat(record["date"])
            if record_date >= month_start:
                month_words += record.get("words", 0)
                month_chapters += record.get("chapters", 0)

        return {
            "month": f"{today.year}-{today.month:02d}",
            "words": month_words,
            "chapters": month_chapters
        }

    def get_recent_history(self, days: int = 7) -> List[Dict]:
        """获取最近N天的历史"""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        return sorted(
            [h for h in self.data["history"] if h["date"] >= cutoff],
            key=lambda x: x["date"],
            reverse=True
        )

    def reset_daily_goals(self):
        """重置每日目标（每天自动调用）"""
        today = date.today().isoformat()
        for goal in self.data["goals"]:
            if goal["type"] == "daily" and goal["status"] == "completed":
                # 重新激活每日目标
                goal["status"] = "active"
                goal["current_value"] = 0
                goal["start_date"] = today
                goal["end_date"] = today
        self._save_data()


# 全局单例
_goals_service: Optional[GoalsService] = None


def get_goals_service(data_dir: str = "data/global") -> GoalsService:
    """获取目标服务单例"""
    global _goals_service
    if _goals_service is None:
        _goals_service = GoalsService(data_dir)
    return _goals_service


def record_writing_progress(words: int, chapters: int = 0, book_name: str = None):
    """
    便捷函数：记录写作进度

    在保存章节时调用此函数
    """
    goals = get_goals_service()
    goals.add_progress(words, chapters, book_name)