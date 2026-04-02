"""
伏笔追踪管理系统
实现伏笔的埋设->追踪->预警->回收全生命周期管理
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, List, Any


class ForeshadowManager:
    """伏笔管理核心类"""

    # 伏笔类型
    TYPES = ["物品", "人物", "剧情", "悬念", "设定", "其他"]

    # 伏笔状态
    STATUS_ACTIVE = "active"      # 埋设中，待回收
    STATUS_RESOLVED = "resolved"  # 已回收
    STATUS_EXPIRED = "expired"    # 过期未回收（预警）
    STATUS_ABANDONED = "abandoned" # 已放弃（断头伏笔）

    # 预警阈值：超过多少章未回收触发预警
    WARNING_CHAPTER_THRESHOLD = 10  # 默认10章

    def __init__(self, project_path: str):
        """
        初始化伏笔管理器

        Args:
            project_path: 项目路径（如 projects/{book_name}）
        """
        self.project_path = project_path
        self.data_file = os.path.join(project_path, "foreshadowings.json")
        self._ensure_data_file()
        self._load_data()

    def _ensure_data_file(self):
        """确保数据文件存在"""
        os.makedirs(self.project_path, exist_ok=True)
        if not os.path.exists(self.data_file):
            self._save_data(self._get_default_data())

    def _get_default_data(self) -> Dict:
        """获取默认数据结构"""
        return {
            "foreshadowings": [],
            "settings": {
                "warning_chapter_threshold": self.WARNING_CHAPTER_THRESHOLD,
                "auto_detect_enabled": True  # 审稿时自动检测伏笔
            },
            "stats": {
                "total": 0,
                "active": 0,
                "resolved": 0,
                "expired": 0,
                "abandoned": 0
            }
        }

    def _load_data(self):
        """加载数据"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except (json.JSONDecodeError, IOError):
            self.data = self._get_default_data()
            self._save_data()

    def _save_data(self, data: Dict = None):
        """保存数据"""
        if data is None:
            data = self.data
        self._update_stats()
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _update_stats(self):
        """更新统计信息"""
        foreshadowings = self.data.get("foreshadowings", [])
        self.data["stats"] = {
            "total": len(foreshadowings),
            "active": len([f for f in foreshadowings if f["status"] == self.STATUS_ACTIVE]),
            "resolved": len([f for f in foreshadowings if f["status"] == self.STATUS_RESOLVED]),
            "expired": len([f for f in foreshadowings if f["status"] == self.STATUS_EXPIRED]),
            "abandoned": len([f for f in foreshadowings if f["status"] == self.STATUS_ABANDONED])
        }

    def _generate_id(self) -> str:
        """生成唯一ID"""
        existing_ids = [f["id"] for f in self.data["foreshadowings"]]
        counter = len(existing_ids) + 1
        while f"f{counter:03d}" in existing_ids:
            counter += 1
        return f"f{counter:03d}"

    # ==================== CRUD 操作 ====================

    def create_foreshadow(
        self,
        content: str,
        foreshadow_type: str = "剧情",
        source_chapter: int = 0,
        source_paragraph: str = "",
        target_chapter: int = None,
        importance: str = "medium",
        notes: str = ""
    ) -> Dict:
        """
        创建新伏笔

        Args:
            content: 伏笔内容描述
            foreshadow_type: 伏笔类型（物品/人物/剧情/悬念/设定/其他）
            source_chapter: 埋设章节编号
            source_paragraph: 埋设段落ID
            target_chapter: 预期回收章节（可选）
            importance: 重要程度（high/medium/low）
            notes: 备注

        Returns:
            新创建的伏笔对象
        """
        now = datetime.now().strftime("%Y-%m-%d")

        foreshadow = {
            "id": self._generate_id(),
            "content": content,
            "type": foreshadow_type,
            "source_chapter": source_chapter,
            "source_paragraph": source_paragraph,
            "target_chapter": target_chapter,
            "status": self.STATUS_ACTIVE,
            "resolved_chapter": None,
            "resolved_content": None,
            "importance": importance,
            "notes": notes,
            "created_at": now,
            "updated_at": now
        }

        self.data["foreshadowings"].append(foreshadow)
        self._save_data()

        return foreshadow

    def update_foreshadow(self, foreshadow_id: str, **kwargs) -> Optional[Dict]:
        """
        更新伏笔

        Args:
            foreshadow_id: 伏笔ID
            **kwargs: 要更新的字段

        Returns:
            更新后的伏笔对象，如果不存在返回 None
        """
        for foreshadow in self.data["foreshadowings"]:
            if foreshadow["id"] == foreshadow_id:
                # 更新字段
                for key, value in kwargs.items():
                    if key in foreshadow:
                        foreshadow[key] = value

                foreshadow["updated_at"] = datetime.now().strftime("%Y-%m-%d")
                self._save_data()
                return foreshadow

        return None

    def delete_foreshadow(self, foreshadow_id: str) -> bool:
        """
        删除伏笔

        Args:
            foreshadow_id: 伏笔ID

        Returns:
            是否成功删除
        """
        original_len = len(self.data["foreshadowings"])
        self.data["foreshadowings"] = [
            f for f in self.data["foreshadowings"] if f["id"] != foreshadow_id
        ]

        if len(self.data["foreshadowings"]) < original_len:
            self._save_data()
            return True

        return False

    def get_foreshadow(self, foreshadow_id: str) -> Optional[Dict]:
        """获取单个伏笔"""
        for foreshadow in self.data["foreshadowings"]:
            if foreshadow["id"] == foreshadow_id:
                return foreshadow
        return None

    def get_all_foreshadows(self) -> List[Dict]:
        """获取所有伏笔"""
        return self.data.get("foreshadowings", [])

    # ==================== 状态查询 ====================

    def get_active_foreshadows(self) -> List[Dict]:
        """获取所有活跃伏笔（待回收）"""
        return [f for f in self.data["foreshadowings"]
                if f["status"] == self.STATUS_ACTIVE]

    def get_resolved_foreshadows(self) -> List[Dict]:
        """获取所有已回收伏笔"""
        return [f for f in self.data["foreshadowings"]
                if f["status"] == self.STATUS_RESOLVED]

    def get_foreshadows_by_status(self, status: str) -> List[Dict]:
        """按状态获取伏笔"""
        return [f for f in self.data["foreshadowings"] if f["status"] == status]

    def get_foreshadows_by_type(self, foreshadow_type: str) -> List[Dict]:
        """按类型获取伏笔"""
        return [f for f in self.data["foreshadowings"] if f["type"] == foreshadow_type]

    def get_foreshadows_by_chapter(self, chapter: int, mode: str = "source") -> List[Dict]:
        """
        按章节获取伏笔

        Args:
            chapter: 章节编号
            mode: "source" 埋设章节, "resolved" 回收章节, "both" 两者

        Returns:
            匹配的伏笔列表
        """
        result = []
        for f in self.data["foreshadowings"]:
            if mode == "source" and f["source_chapter"] == chapter:
                result.append(f)
            elif mode == "resolved" and f["resolved_chapter"] == chapter:
                result.append(f)
            elif mode == "both":
                if f["source_chapter"] == chapter or f["resolved_chapter"] == chapter:
                    result.append(f)
        return result

    # ==================== 预警系统 ====================

    def check_warnings(self, current_chapter: int) -> List[Dict]:
        """
        检查伏笔预警

        Args:
            current_chapter: 当前章节编号

        Returns:
            预警伏笔列表，包含预警原因
        """
        threshold = self.data["settings"].get(
            "warning_chapter_threshold", self.WARNING_CHAPTER_THRESHOLD
        )

        warnings = []

        for f in self.data["foreshadowings"]:
            if f["status"] != self.STATUS_ACTIVE:
                continue

            # 计算距离埋设的章节数
            chapters_since = current_chapter - f["source_chapter"]

            # 检查超阈值预警
            if chapters_since >= threshold:
                f_copy = f.copy()
                f_copy["warning_type"] = "overdue"
                f_copy["warning_message"] = f"已过 {chapters_since} 章未回收（阈值：{threshold}章）"
                f_copy["chapters_since"] = chapters_since
                warnings.append(f_copy)

            # 检查预期章节预警
            if f.get("target_chapter") and current_chapter >= f["target_chapter"]:
                f_copy = f.copy()
                f_copy["warning_type"] = "target_missed"
                f_copy["warning_message"] = f"已超过预期回收章节（预期：第{f['target_chapter']}章）"
                f_copy["chapters_since"] = chapters_since
                # 如果已经在 overdue 列表中，更新信息
                existing = next(
                    (w for w in warnings if w["id"] == f["id"] and w["warning_type"] == "overdue"),
                    None
                )
                if existing:
                    existing["warning_type"] = "overdue_and_target_missed"
                    existing["warning_message"] = f"{existing['warning_message']}，且超过预期回收章节"
                else:
                    warnings.append(f_copy)

        # 按重要程度和章节距离排序
        warnings.sort(key=lambda w: (
            -({"high": 3, "medium": 2, "low": 1}.get(w.get("importance", "medium"), 2)),
            -w.get("chapters_since", 0)
        ))

        return warnings

    def mark_expired(self, foreshadow_id: str) -> Optional[Dict]:
        """标记伏笔为过期状态"""
        return self.update_foreshadow(foreshadow_id, status=self.STATUS_EXPIRED)

    def mark_abandoned(self, foreshadow_id: str, reason: str = "") -> Optional[Dict]:
        """标记伏笔为放弃状态（断头伏笔）"""
        return self.update_foreshadow(
            foreshadow_id,
            status=self.STATUS_ABANDONED,
            notes=f"{self.get_foreshadow(foreshadow_id).get('notes', '')} [放弃原因: {reason}]"
        )

    # ==================== 回收确认 ====================

    def resolve_foreshadow(
        self,
        foreshadow_id: str,
        resolved_chapter: int,
        resolved_content: str = ""
    ) -> Optional[Dict]:
        """
        确认伏笔回收

        Args:
            foreshadow_id: 伏笔ID
            resolved_chapter: 回收章节编号
            resolved_content: 回收方式描述

        Returns:
            更新后的伏笔对象
        """
        return self.update_foreshadow(
            foreshadow_id,
            status=self.STATUS_RESOLVED,
            resolved_chapter=resolved_chapter,
            resolved_content=resolved_content
        )

    def batch_resolve_from_review(
        self,
        resolved_list: List[Dict],
        current_chapter: int
    ) -> List[Dict]:
        """
        从审稿结果批量确认回收

        Args:
            resolved_list: 审稿发现的已回收伏笔列表
            current_chapter: 当前章节编号

        Returns:
            成功确认的伏笔列表
        """
        resolved_foreshadows = []

        # 尝试匹配已存在的伏笔
        for resolved in resolved_list:
            content = resolved.get("content", "")
            resolution = resolved.get("resolution", "")

            # 查找匹配的活跃伏笔
            matched = None
            for f in self.get_active_foreshadows():
                # 简单的内容匹配（可以后续优化为更智能的匹配）
                if f["content"] in content or content in f["content"]:
                    matched = f
                    break

            if matched:
                self.resolve_foreshadow(
                    matched["id"],
                    current_chapter,
                    resolution
                )
                resolved_foreshadows.append(matched)
            else:
                # 如果没有找到匹配的，可能是审稿误判或者伏笔库中没有记录
                # 可以选择记录为新的已回收伏笔，或者忽略
                pass

        return resolved_foreshadows

    # ==================== 审稿自动保存 ====================

    def save_from_review(
        self,
        new_foreshadows: List[Dict],
        current_chapter: int
    ) -> List[Dict]:
        """
        从审稿结果保存新伏笔

        Args:
            new_foreshadows: 审稿发现的新伏笔列表
            current_chapter: 当前章节编号

        Returns:
            新创建的伏笔列表
        """
        created = []

        for new_f in new_foreshadows:
            content = new_f.get("content", "")
            paragraph_id = new_f.get("paragraph_id", "")
            f_type = new_f.get("type", "剧情")

            # 检查是否已存在相同内容
            exists = any(
                f["content"] == content and f["source_chapter"] == current_chapter
                for f in self.data["foreshadowings"]
            )

            if not exists and content:
                foreshadow = self.create_foreshadow(
                    content=content,
                    foreshadow_type=f_type,
                    source_chapter=current_chapter,
                    source_paragraph=paragraph_id
                )
                created.append(foreshadow)

        return created

    # ==================== 统计信息 ====================

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.data.get("stats", {})

    def get_overview(self, current_chapter: int = None) -> Dict:
        """
        获取伏笔概览（用于 UI 展示）

        Args:
            current_chapter: 当前章节编号（用于计算预警）

        Returns:
            概览信息字典
        """
        stats = self.get_stats()
        warnings = []

        if current_chapter:
            warnings = self.check_warnings(current_chapter)

        return {
            "total": stats.get("total", 0),
            "active": stats.get("active", 0),
            "resolved": stats.get("resolved", 0),
            "expired": stats.get("expired", 0),
            "abandoned": stats.get("abandoned", 0),
            "warnings_count": len(warnings),
            "warnings": warnings[:5]  # 只返回前5个预警
        }

    # ==================== 配置管理 ====================

    def update_settings(self, **kwargs) -> Dict:
        """更新配置"""
        for key, value in kwargs.items():
            if key in self.data["settings"]:
                self.data["settings"][key] = value
        self._save_data()
        return self.data["settings"]

    def get_settings(self) -> Dict:
        """获取配置"""
        return self.data.get("settings", {})

    # ==================== 导入导出 ====================

    def export_to_dict(self) -> Dict:
        """导出为字典（用于备份）"""
        return {
            "foreshadowings": self.data["foreshadowings"],
            "settings": self.data["settings"],
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def import_from_dict(self, data: Dict, merge: bool = True) -> int:
        """
        从字典导入

        Args:
            data: 要导入的数据
            merge: 是否合并（True）还是替换（False）

        Returns:
            导入的伏笔数量
        """
        imported_count = 0

        if merge:
            # 合并模式：添加不存在的伏笔
            for f in data.get("foreshadowings", []):
                exists = any(
                    existing["content"] == f["content"] and
                    existing["source_chapter"] == f["source_chapter"]
                    for existing in self.data["foreshadowings"]
                )
                if not exists:
                    # 重新生成 ID
                    f["id"] = self._generate_id()
                    self.data["foreshadowings"].append(f)
                    imported_count += 1
        else:
            # 替换模式
            self.data["foreshadowings"] = data.get("foreshadowings", [])
            self.data["settings"] = data.get("settings", self._get_default_data()["settings"])
            imported_count = len(self.data["foreshadowings"])

        self._save_data()
        return imported_count


# ==================== 便捷函数 ====================

def get_foreshadow_manager(project_path: str) -> ForeshadowManager:
    """获取伏笔管理器实例"""
    return ForeshadowManager(project_path)