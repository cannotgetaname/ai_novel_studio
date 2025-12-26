# modules/state.py
from nicegui import ui
import backend

# 初始化后端
manager = backend.NovelManager()
memory = backend.MemoryManager()
CFG = backend.CFG

class AppState:
    def __init__(self):
        # 数据层
        self.structure = manager.load_structure()
        self.settings = manager.load_settings()
        self.characters = manager.load_characters()
        self.items = manager.load_items()
        self.locations = manager.load_locations()
        
        # 运行时状态
        self.current_chapter_idx = 0
        self.current_content = ""
        
        # 全局回调函数 (由 main.py 注入)
        self.refresh_sidebar = None
        self.refresh_total_word_count = None

    # 辅助：获取当前章节对象
    def get_current_chapter(self):
        if not self.structure: return None
        # 越界保护
        if self.current_chapter_idx >= len(self.structure):
            self.current_chapter_idx = len(self.structure) - 1
        return self.structure[self.current_chapter_idx]

# 单例实例
app_state = AppState()

# UI 引用字典 (用于跨模块访问组件)
ui_refs = {
    'editor_title': None, 'editor_outline': None, 'editor_content': None,
    'char_container': None, 'item_container': None, 'loc_container': None,
    'chapter_list': None, 'rag_debug': None, 'review_panel': None,
    'right_tabs': None, 'tab_ctx': None, 'tab_rev': None,
    'char_count': None, 'total_count': None,
    'char_view_mode': None, 'char_graph_container': None,
    'time_label': None, 'time_events': None, 'timeline_container': None
}