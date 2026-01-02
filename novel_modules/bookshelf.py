# novel_modules/bookshelf.py
from nicegui import ui
from .state import app_state, library,ui_refs
import backend

def open_bookshelf_dialog():
    """打开书架弹窗"""
    
    # 定义对话框 (dialog)
    # 使用 value=True 替代 .open()，效果一样
    with ui.dialog() as dialog, ui.card().classes('w-3/4 h-3/4 bg-gray-50'):
        
        # --- 顶部栏 ---
        with ui.row().classes('w-full items-center justify-between mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('library_books', size='md', color='purple')
                ui.label('我的书架').classes('text-2xl font-bold text-gray-800')
            ui.button(icon='close', on_click=dialog.close).props('flat round')

        # --- 内容区 ---
        content_area = ui.column().classes('w-full flex-grow overflow-auto')

        # --- 核心逻辑函数定义 (放在前面确保引用正常) ---
        
        async def switch_and_close(name):
            if name == app_state.current_book_name:
                ui.notify(f'当前已经是《{name}》了', type='info')
                return # 别关弹窗
            
            ui.notify(f'正在切换至《{name}》...', type='info', spinner=True)
            app_state.load_project(name)
            
            # 刷新相关模块
            from . import writing, settings
            # 尝试加载第一章
            if app_state.structure:
                await writing.load_chapter(0)
            else:
                # 清理 UI
                if ui_refs.get('editor_title'): ui_refs['editor_title'].value = ""
                if ui_refs.get('editor_content'): ui_refs['editor_content'].value = ""
                if ui_refs.get('editor_outline'): ui_refs['editor_outline'].value = ""
            
            settings.refresh_char_ui()
            settings.refresh_loc_ui()
            
            dialog.close()
            ui.notify(f'已切换至《{name}》', type='positive')

        def open_delete_confirm(book_name):
            # 定义一个局部弹窗
            with ui.dialog() as d_confirm, ui.card().classes('w-96 border-l-4 border-red-500'):
                with ui.row().classes('items-center gap-2 text-red-600 mb-2'):
                    ui.icon('warning', size='md')
                    ui.label('危险操作').classes('text-lg font-bold')
                
                ui.label(f'确定要永久删除《{book_name}》吗？').classes('font-bold text-gray-800')
                ui.label('所有章节、设定、大纲和向量记忆都将被清空且无法恢复！').classes('text-sm text-gray-500 mt-1')
                
                if book_name == app_state.current_book_name:
                    with ui.row().classes('bg-red-50 p-2 rounded mt-2 w-full'):
                        ui.icon('error', color='red')
                        ui.label('这是当前打开的书，删除后将强制重置！').classes('text-xs text-red-600')

                async def do_delete():
                    ui.notify('正在执行删除...', type='warning', spinner=True)
                    success, msg = library.delete_book(book_name)
                    
                    if success:
                        ui.notify(msg, type='positive')
                        
                        # 如果删的是当前书
                        if book_name == app_state.current_book_name:
                            remain = library.list_books()
                            if remain:
                                await switch_and_close(remain[0]['name'])
                            else:
                                library.create_book("MyFirstNovel")
                                await switch_and_close("MyFirstNovel")
                        else:
                            refresh_grid() # 仅刷新界面
                        
                        d_confirm.close()
                    else:
                        ui.notify(f'删除失败: {msg}', type='negative')

                with ui.row().classes('w-full justify-end mt-4 gap-2'):
                    ui.button('取消', on_click=d_confirm.close).props('flat color=grey')
                    ui.button('确认删除', on_click=do_delete).props('unelevated color=red icon=delete_forever')
            
            d_confirm.open()

        def open_rename_dialog(old_name):
            with ui.dialog() as d_rename, ui.card():
                ui.label(f'重命名: {old_name}').classes('text-lg font-bold')
                name_input = ui.input('新书名', value=old_name).classes('w-64').props('autofocus')
                
                async def do_rename():
                    new_name = name_input.value
                    if not new_name or new_name == old_name: 
                        d_rename.close()
                        return
                    success, res = library.rename_book(old_name, new_name)
                    if success:
                        ui.notify(f'已重命名为: {res}', type='positive')
                        if app_state.current_book_name == old_name:
                            app_state.load_project(res)
                            backend.CFG['last_open_book'] = res
                            backend.save_global_config(backend.CFG)
                        d_rename.close()
                        refresh_grid()
                    else:
                        ui.notify(f'重命名失败: {res}', type='negative')

                with ui.row().classes('w-full justify-end mt-4'):
                    ui.button('取消', on_click=d_rename.close).props('flat')
                    ui.button('确认', on_click=do_rename).props('color=purple')
            d_rename.open()

        def create_new_book_dialog():
            with ui.dialog() as d_create, ui.card():
                ui.label('新建小说').classes('text-lg font-bold')
                name_input = ui.input('书名').classes('w-64').props('autofocus')
                
                def do_create():
                    name = name_input.value
                    if not name: return
                    success, msg = library.create_book(name)
                    if success:
                        ui.notify(f'创建成功: {msg}', type='positive')
                        d_create.close()
                        refresh_grid()
                    else:
                        ui.notify(f'创建失败: {msg}', type='negative')
                
                with ui.row().classes('w-full justify-end mt-4'):
                    ui.button('取消', on_click=d_create.close).props('flat')
                    ui.button('创建', on_click=do_create).props('color=purple')
            d_create.open()

        # --- 界面刷新函数 ---
        def refresh_grid():
            content_area.clear()
            books = library.list_books()
            
            with content_area:
                ui.label(f'共 {len(books)} 部作品').classes('text-sm text-gray-500 mb-2')
                
                with ui.grid(columns=4).classes('w-full gap-4'):
                    # 1. 新建卡片
                    with ui.card().classes('w-full h-40 items-center justify-center border-2 border-dashed border-gray-300 hover:border-purple-500 hover:bg-purple-50 cursor-pointer transition-all') \
                            .on('click', create_new_book_dialog):
                        ui.icon('add', size='lg', color='grey')
                        ui.label('新建小说').classes('text-gray-500 font-bold')

                    # 2. 书籍卡片
                    for book in books:
                        is_active = book['name'] == app_state.current_book_name
                        border_cls = 'border-2 border-purple-600' if is_active else 'border border-gray-200 hover:shadow-lg'
                        bg_cls = 'bg-purple-50' if is_active else 'bg-white'
                        
                        # 【重要修改】卡片不再整体响应点击，而是拆分为两个区域
                        with ui.card().classes(f'w-full h-40 p-0 flex flex-col justify-between transition-all {border_cls} {bg_cls}'):
                            
                            # 区域A：上半部分 (点击切换书籍)
                            # 使用 w-full flex-grow 让它占据除按钮外的所有空间
                            with ui.column().classes('w-full flex-grow p-4 cursor-pointer gap-1') \
                                    .on('click', lambda b=book['name']: switch_and_close(b)):
                                
                                ui.icon('book', color='purple' if is_active else 'gray').classes('mb-1')
                                ui.label(book['name']).classes('text-lg font-bold leading-tight truncate w-full')
                                if is_active:
                                    ui.badge('当前编辑', color='purple').props('outline size=xs')
                            
                            # 区域B：下半部分 (操作按钮)
                            # 独立的背景色区分，且不绑定切换事件
                            with ui.row().classes('w-full p-2 bg-gray-50 border-t border-gray-100 justify-end gap-2'):
                                
                                # 按钮本身会拦截点击，因为它们不在 区域A 内部
                                ui.button(icon='edit', on_click=lambda e, b=book['name']: open_rename_dialog(b)) \
                                    .props('flat round dense color=grey size=sm').tooltip('重命名')
                                
                                ui.button(icon='delete', on_click=lambda e, b=book['name']: open_delete_confirm(b)) \
                                    .props('flat round dense color=red size=sm').tooltip('删除')

        refresh_grid()
    
    dialog.open()