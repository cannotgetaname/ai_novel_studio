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

        # 撤销/重做历史 - 为当前章节维护编辑历史
        self.undo_stack = []  # 存储编辑状态
        self.redo_stack = []  # 存储被撤销的状态

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

    def save_state_for_undo(self, title, outline, content, time_label, time_events):
        """保存当前编辑状态用于撤销 - 由用户直接编辑触发，会清空重做栈"""
        # 创建当前状态的快照
        state = {
            'title': title,
            'outline': outline,
            'content': content,
            'time_label': time_label,
            'time_events': time_events,
            'chapter_idx': self.current_chapter_idx
        }

        # 仅在与上一个状态显著不同时才保存（防抖）
        if (not self.undo_stack or
            self.undo_stack[-1]['content'] != content or
            self.undo_stack[-1]['title'] != title or
            self.undo_stack[-1]['outline'] != outline):

            # 保存到撤销栈
            self.undo_stack.append(state)

            # 限制撤销栈大小，避免内存占用过大
            if len(self.undo_stack) > 50:  # 保留最近50个状态
                self.undo_stack.pop(0)

            # 清空重做栈，因为新的用户编辑使之前的重做状态失效
            self.redo_stack.clear()

    def save_state_to_undo(self, state):
        """将状态保存到撤销栈 - 由重做操作触发，不清空重做栈"""
        # 只有在状态真正不同的时候才保存
        if (not self.undo_stack or
            self.undo_stack[-1]['content'] != state['content'] or
            self.undo_stack[-1]['title'] != state['title'] or
            self.undo_stack[-1]['outline'] != state['outline']):

            self.undo_stack.append(state)
            if len(self.undo_stack) > 50:
                self.undo_stack.pop(0)
        # 注意：这里不清空重做栈，因为这是从重做操作过来的，重做栈可能还有内容

    def can_undo(self):
        """检查是否可以撤销"""
        return len(self.undo_stack) > 0

    def can_redo(self):
        """检查是否可以重做"""
        return len(self.redo_stack) > 0

    def undo_state(self):
        """执行撤销操作，返回要恢复的状态"""
        if not self.can_undo():
            return None

        # 弹出最后一个状态
        return self.undo_stack.pop()

    def redo_state(self):
        """执行重做操作，返回要恢复的状态"""
        if not self.can_redo():
            return None

        # 弹出重做栈顶的状态
        return self.redo_stack.pop()

    def save_state_to_redo(self, state):
        """将状态保存到重做栈，带防抖机制"""
        # 只有在状态真正不同的时候才保存
        if (not self.redo_stack or
            self.redo_stack[-1]['content'] != state['content'] or
            self.redo_stack[-1]['title'] != state['title'] or
            self.redo_stack[-1]['outline'] != state['outline']):

            self.redo_stack.append(state)


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
    'save_status': None, 'config_container': None,
    # 【新增】地点视图控制
    'loc_view_mode': None,
    'loc_graph_container': None,
    # 【新增】费用管理
    'billing_container': None
}