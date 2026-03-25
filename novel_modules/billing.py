"""
Token 计费管理系统
帮助用户了解 AI 调用成本，控制预算
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

# 默认模型价格（每 1000 tokens，单位：人民币）
# 更新于 2025-03，汇率按 1 USD = 7.2 CNY 计算
DEFAULT_PRICING = {
    "deepseek-chat": {"input": 0.00194, "output": 0.00792},  # $0.00027, $0.0011
    "deepseek-reasoner": {"input": 0.00396, "output": 0.01577},  # $0.00055, $0.00219
    "gpt-4": {"input": 0.216, "output": 0.432},  # $0.03, $0.06
    "gpt-4-turbo": {"input": 0.072, "output": 0.216},  # $0.01, $0.03
    "gpt-3.5-turbo": {"input": 0.0036, "output": 0.0108},  # $0.0005, $0.0015
    "claude-3-opus": {"input": 0.108, "output": 0.54},  # $0.015, $0.075
    "claude-3-sonnet": {"input": 0.0216, "output": 0.108},  # $0.003, $0.015
    "claude-3-haiku": {"input": 0.0018, "output": 0.009},  # $0.00025, $0.00125
}


class BillingService:
    """计费服务核心类"""

    def __init__(self, data_dir: str = "data/global"):
        self.data_dir = data_dir
        self.billing_file = os.path.join(data_dir, "billing.json")
        self._ensure_data_dir()
        self._load_data()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        os.makedirs(self.data_dir, exist_ok=True)

    def _load_data(self):
        """加载计费数据"""
        if os.path.exists(self.billing_file):
            try:
                with open(self.billing_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.data = self._get_default_data()
        else:
            self.data = self._get_default_data()
            self._save_data()

    def _get_default_data(self) -> Dict:
        """获取默认数据结构"""
        return {
            "balance": 0.0,
            "records": [],
            "stats": {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "total_calls": 0
            }
        }

    def _save_data(self):
        """保存计费数据"""
        with open(self.billing_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_pricing(self, model: str, config_pricing: Optional[Dict] = None) -> Dict:
        """
        获取模型价格
        优先使用配置文件中的价格，否则使用默认价格
        """
        if config_pricing and model in config_pricing:
            return config_pricing[model]
        return DEFAULT_PRICING.get(model, {"input": 0.0, "output": 0.0})

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量
        规则：
        - 中文字符约 1.5 tokens
        - 英文单词约 1.3 tokens
        - 其他字符约 0.5 tokens
        """
        if not text:
            return 0

        import re
        # 中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        # 英文单词
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        # 其他字符
        other_chars = len(text) - chinese_chars - sum(len(w) for w in re.findall(r'[a-zA-Z]+', text))

        return int(chinese_chars * 1.5 + english_words * 1.3 + other_chars * 0.5)

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int,
                       config_pricing: Optional[Dict] = None) -> float:
        """
        计算费用
        返回：费用（元）
        """
        pricing = self.get_pricing(model, config_pricing)
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    def record_call(self, book_name: str, task_type: str, model: str,
                    input_tokens: int, output_tokens: int, cost: float,
                    status: str = "success", config_pricing: Optional[Dict] = None) -> Dict:
        """
        记录一次 API 调用
        """
        # 如果没有提供 cost，自动计算
        if cost == 0 and (input_tokens > 0 or output_tokens > 0):
            cost = self.calculate_cost(model, input_tokens, output_tokens, config_pricing)

        record = {
            "id": len(self.data["records"]) + 1,
            "timestamp": datetime.now().isoformat(),
            "book_name": book_name,
            "task_type": task_type,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "status": status
        }

        self.data["records"].append(record)

        # 更新统计
        self.data["stats"]["total_input_tokens"] += input_tokens
        self.data["stats"]["total_output_tokens"] += output_tokens
        self.data["stats"]["total_cost"] += cost
        self.data["stats"]["total_calls"] += 1

        # 从余额中扣除
        self.data["balance"] -= cost

        self._save_data()
        return record

    def get_balance(self) -> float:
        """获取当前余额"""
        return self.data["balance"]

    def set_balance(self, balance: float):
        """设置余额"""
        self.data["balance"] = balance
        self._save_data()

    def add_balance(self, amount: float):
        """充值"""
        self.data["balance"] += amount
        self._save_data()

    def get_stats(self) -> Dict:
        """获取统计数据"""
        return self.data["stats"]

    def get_records(self, filters: Optional[Dict] = None) -> List[Dict]:
        """
        获取记录列表
        filters: {
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "model": "deepseek-chat",
            "task_type": "writer",
            "book_name": "MyNovel"
        }
        """
        records = self.data["records"]

        if filters:
            if filters.get("start_date"):
                start = datetime.fromisoformat(filters["start_date"])
                records = [r for r in records if datetime.fromisoformat(r["timestamp"]) >= start]

            if filters.get("end_date"):
                end = datetime.fromisoformat(filters["end_date"]) + timedelta(days=1)
                records = [r for r in records if datetime.fromisoformat(r["timestamp"]) < end]

            if filters.get("model"):
                records = [r for r in records if r["model"] == filters["model"]]

            if filters.get("task_type"):
                records = [r for r in records if r["task_type"] == filters["task_type"]]

            if filters.get("book_name"):
                records = [r for r in records if r["book_name"] == filters["book_name"]]

        return records

    def get_daily_stats(self, days: int = 7) -> List[Dict]:
        """
        获取最近 N 天的每日统计
        返回: [{"date": "2026-03-24", "cost": 0.5, "calls": 10}, ...]
        """
        today = datetime.now().date()
        daily_data = {}

        # 初始化所有日期
        for i in range(days):
            date = (today - timedelta(days=i)).isoformat()
            daily_data[date] = {"date": date, "cost": 0.0, "calls": 0}

        # 统计记录
        for record in self.data["records"]:
            date = datetime.fromisoformat(record["timestamp"]).date().isoformat()
            if date in daily_data:
                daily_data[date]["cost"] += record["cost"]
                daily_data[date]["calls"] += 1

        # 按日期排序（从旧到新）
        return sorted(daily_data.values(), key=lambda x: x["date"])

    def get_today_stats(self) -> Dict:
        """获取今日统计"""
        today = datetime.now().date().isoformat()
        today_records = [r for r in self.data["records"]
                         if datetime.fromisoformat(r["timestamp"]).date().isoformat() == today]

        return {
            "date": today,
            "cost": sum(r["cost"] for r in today_records),
            "calls": len(today_records),
            "input_tokens": sum(r["input_tokens"] for r in today_records),
            "output_tokens": sum(r["output_tokens"] for r in today_records)
        }

    def get_month_stats(self) -> Dict:
        """获取本月统计"""
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1)
        month_records = [r for r in self.data["records"]
                         if datetime.fromisoformat(r["timestamp"]) >= month_start]

        return {
            "month": f"{now.year}-{now.month:02d}",
            "cost": sum(r["cost"] for r in month_records),
            "calls": len(month_records),
            "input_tokens": sum(r["input_tokens"] for r in month_records),
            "output_tokens": sum(r["output_tokens"] for r in month_records)
        }

    def clear_records(self, before_date: Optional[str] = None):
        """
        清理记录
        before_date: 清理此日期之前的记录，格式 "2026-03-01"
        """
        if before_date is None:
            # 清理所有记录
            self.data["records"] = []
            self.data["stats"] = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "total_calls": 0
            }
        else:
            # 清理指定日期之前的记录
            cutoff = datetime.fromisoformat(before_date)
            old_records = [r for r in self.data["records"]
                           if datetime.fromisoformat(r["timestamp"]) < cutoff]

            # 计算需要扣除的统计
            for r in old_records:
                self.data["stats"]["total_input_tokens"] -= r["input_tokens"]
                self.data["stats"]["total_output_tokens"] -= r["output_tokens"]
                self.data["stats"]["total_cost"] -= r["cost"]
                self.data["stats"]["total_calls"] -= 1

            # 保留新记录
            self.data["records"] = [r for r in self.data["records"]
                                     if datetime.fromisoformat(r["timestamp"]) >= cutoff]

        self._save_data()


# 全局单例
_billing_service: Optional[BillingService] = None


def get_billing_service(data_dir: str = "data/global") -> BillingService:
    """获取计费服务单例"""
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService(data_dir)
    return _billing_service


def record_api_call(response, task_type: str, model: str, book_name: str = None,
                    config_pricing: Optional[Dict] = None, status: str = "success") -> Optional[Dict]:
    """
    便捷函数：从 API 响应中记录 token 使用量

    Args:
        response: OpenAI API 响应对象
        task_type: 任务类型 (writer, editor, reviewer 等)
        model: 模型名称
        book_name: 书籍名称（可选，会自动获取）
        config_pricing: 配置中的价格表
        status: 调用状态

    Returns:
        记录字典，失败时返回 None
    """
    try:
        if not hasattr(response, 'usage') or not response.usage:
            return None

        billing = get_billing_service()

        if book_name is None:
            try:
                from novel_modules.state import app_state
                book_name = app_state.current_book_name or "Unknown"
            except:
                book_name = "Unknown"

        return billing.record_call(
            book_name=book_name,
            task_type=task_type,
            model=model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            cost=0,
            status=status,
            config_pricing=config_pricing
        )
    except Exception as e:
        print(f"[Billing] 记录失败: {e}")
        return None


def estimate_and_record(prompt: str, result: str, task_type: str, model: str,
                        book_name: str = None, config_pricing: Optional[Dict] = None) -> Optional[Dict]:
    """
    便捷函数：估算并记录 token 使用量（用于流式调用）

    Args:
        prompt: 输入提示词
        result: 输出结果
        task_type: 任务类型
        model: 模型名称
        book_name: 书籍名称
        config_pricing: 配置中的价格表

    Returns:
        记录字典
    """
    try:
        billing = get_billing_service()

        if book_name is None:
            try:
                from novel_modules.state import app_state
                book_name = app_state.current_book_name or "Unknown"
            except:
                book_name = "Unknown"

        input_tokens = billing.estimate_tokens(prompt)
        output_tokens = billing.estimate_tokens(result)

        return billing.record_call(
            book_name=book_name,
            task_type=task_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=0,
            status="success",
            config_pricing=config_pricing
        )
    except Exception as e:
        print(f"[Billing] 估算记录失败: {e}")
        return None


def record_tokens(book_name: str, task_type: str, model: str,
                  input_tokens: int, output_tokens: int,
                  config_pricing: Optional[Dict] = None) -> Optional[Dict]:
    """
    便捷函数：直接从 token 数量记录费用（用于非流式调用）

    Args:
        book_name: 书籍名称
        task_type: 任务类型
        model: 模型名称
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数
        config_pricing: 配置中的价格表

    Returns:
        记录字典
    """
    try:
        billing = get_billing_service()

        if book_name is None:
            try:
                from novel_modules.state import app_state
                book_name = app_state.current_book_name or "Unknown"
            except:
                book_name = "Unknown"

        return billing.record_call(
            book_name=book_name,
            task_type=task_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=0,
            status="success",
            config_pricing=config_pricing
        )
    except Exception as e:
        print(f"[Billing] 记录失败: {e}")
        return None