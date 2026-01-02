from nicegui import ui
import backend
import os

# 初始化库管理器
library = backend.LibraryManager()

# 全局配置 (不再硬编码 project_dir，而是动态变)
CFG = backend.CFG

class AppState:
    def __init__(self):
        self.current_book_name = ""
        # 初始暂时不加载具体数据，或者加载最后一次打开的书
        # 这里为了演示，我们先留空，等 UI 触发加载
        self.manager = None 
        self.memory = None
        
        # 数据层占位
        self.volumes = []
        self.structure = []
        self.settings = {}
        self.characters = []
        self.items = []
        self.locations = []
        
        # 运行时状态
        self.current_chapter_idx = 0
        self.current_content = ""
        self.expanded_volumes = set()
        self.current_volume_id = 1

        # 回调
        self.refresh_sidebar = None
        self.refresh_total_word_count = None
        
        # 尝试加载上次的书 (可选)
        last_book = CFG.get('last_open_book')
        if last_book and os.path.exists(os.path.join("projects", last_book)):
            self.load_project(last_book)
        else:
            # 如果没有历史记录，加载第一个或者创建一个默认的
            books = library.list_books()
            if books:
                self.load_project(books[0]['name'])
            else:
                library.create_book("MyFirstNovel")
                self.load_project("MyFirstNovel")

    def load_project(self, book_name):
        """【核心】切换书籍，重载所有上下文"""
        print(f"Loading Project: {book_name}")
        self.current_book_name = book_name
        
        # 1. 实例化新的管理器
        project_path = os.path.join("projects", book_name)
        self.manager = backend.NovelManager(project_root=project_path)
        self.memory = backend.MemoryManager(book_name=book_name)
        
        # 2. 更新全局引用 (非常重要，否则 backend.py 里的 manager 还是旧的)
        # 注意：这里我们修改 state.py 导出的 manager 对象
        # 但 Python 模块导入机制决定了直接替换全局变量比较麻烦
        # 更好的方式是 state.manager 指向最新的
        
        # 3. 重新加载所有数据到内存
        self.volumes = self.manager.load_volumes()
        self.structure = self.manager.load_structure()
        self.settings = self.manager.load_settings()
        self.characters = self.manager.load_characters()
        self.items = self.manager.load_items()
        self.locations = self.manager.load_locations()
        
        # 4. 重置 UI 状态
        self.current_chapter_idx = 0
        self.current_content = ""
        self.expanded_volumes = set()
        if self.volumes: self.expanded_volumes.add(self.volumes[0]['id'])
        
        # 5. 持久化记录
        CFG['last_open_book'] = book_name
        backend.save_global_config(CFG) # 保存到 config.json

        # 6. 触发全局 UI 刷新
        if self.refresh_sidebar: self.refresh_sidebar()
        if self.refresh_total_word_count: 
            # 这是一个 async 函数，这里只能尽力调用，或者由 UI 层触发
            pass 

    def get_current_chapter(self):
        if not self.structure: return None
        if self.current_chapter_idx >= len(self.structure):
            self.current_chapter_idx = len(self.structure) - 1
        return self.structure[self.current_chapter_idx]

# 实例化单例
app_state = AppState()
# ================= 核心修复：动态代理 =================
# 不要直接赋值 manager = app_state.manager，因为那样是“静态”的。
# 我们创建一个代理类，每次被调用时，它都会去 app_state 里找最新的对象。

class DynamicProxy:
    def __init__(self, attr_name):
        self.attr_name = attr_name
        
    def __getattr__(self, name):
        # 1. 获取当前的 manager 或 memory 对象
        current_obj = getattr(app_state, self.attr_name)
        # 2. 在当前对象上获取方法或属性（如 load_chapter_content）
        return getattr(current_obj, name)

# 使用代理替代原始对象
manager = DynamicProxy('manager')
memory = DynamicProxy('memory')

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