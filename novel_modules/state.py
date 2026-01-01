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
        self.volumes = manager.load_volumes()
        self.structure = manager.load_structure()
        self.settings = manager.load_settings()
        self.characters = manager.load_characters()
        self.items = manager.load_items()
        self.locations = manager.load_locations()
        
        # 运行时状态
        self.current_chapter_idx = 0
        self.current_content = ""
        
        # UI状态：记录展开的分卷ID集合
        self.expanded_volumes = set()
        if self.volumes:
            self.expanded_volumes.add(self.volumes[0]['id'])

        # 全局回调函数
        self.refresh_sidebar = None
        self.refresh_total_word_count = None

        self.current_volume_id = 1 # 默认选中第一卷

    def get_current_chapter(self):
        if not self.structure: return None
        if self.current_chapter_idx >= len(self.structure):
            self.current_chapter_idx = len(self.structure) - 1
        return self.structure[self.current_chapter_idx]

# 单例实例
app_state = AppState()

# UI 引用字典
ui_refs = {
    'editor_title': None, 'editor_outline': None, 'editor_content': None,
    'char_container': None, 'item_container': None, 'loc_container': None,
    'chapter_list': None, 'rag_debug': None, 'review_panel': None,
    'right_tabs': None, 'tab_ctx': None, 'tab_rev': None,
    'char_count': None, 'total_count': None,
    'char_view_mode': None, 'char_graph_container': None,
    'time_label': None, 'time_events': None, 'timeline_container': None,
    'save_status': None,  # 【新增】用于显示自动保存状态
    'time_label': None, 'time_events': None, 'timeline_container': None,
    'save_status': None, 'config_container': None,
    
    # 【新增】地点视图控制
    'loc_view_mode': None, 
    'loc_graph_container': None
}