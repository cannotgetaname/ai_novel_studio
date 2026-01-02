# novel_modules/bookshelf.py
from nicegui import ui
# 【关键修复】必须确保这里导入了 library
from .state import app_state, library ,ui_refs
import backend


def open_bookshelf_dialog():
    """打开书架弹窗"""
    
    with ui.dialog() as dialog, ui.card().classes('w-3/4 h-3/4 bg-gray-50'):
        # 顶部栏
        with ui.row().classes('w-full items-center justify-between mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('library_books', size='md', color='purple')
                ui.label('我的书架').classes('text-2xl font-bold text-gray-800')
            
            ui.button(icon='close', on_click=dialog.close).props('flat round')

        # 内容区
        content_area = ui.column().classes('w-full flex-grow overflow-auto')
        
        def refresh_grid():
            content_area.clear()
            books = library.list_books()
            
            with content_area:
                # 统计信息
                ui.label(f'共 {len(books)} 部作品').classes('text-sm text-gray-500 mb-2')
                
                # 网格布局
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
                        
                        # 卡片容器
                        with ui.card().classes(f'w-full h-40 p-3 flex flex-col justify-between transition-all {border_cls} {bg_cls} relative group'):
                            
                            # 点击卡片主体 -> 切换书籍
                            # 使用一个覆盖层的 div 来处理点击，避免和编辑按钮冲突
                            ui.element('div').classes('absolute inset-0 z-0 cursor-pointer') \
                                .on('click', lambda b=book['name']: switch_and_close(b))

                            # 上半部分：图标和标题
                            with ui.column().classes('gap-1 z-10 pointer-events-none'): # pointer-events-none 让点击穿透到底层 div
                                ui.icon('book', color='purple' if is_active else 'gray').classes('mb-1')
                                ui.label(book['name']).classes('text-lg font-bold leading-tight truncate w-full')
                                if is_active:
                                    ui.badge('当前编辑', color='purple').props('outline size=xs')

                            # 下半部分：操作按钮栏 (z-index 提高，确保能被点击)
                            with ui.row().classes('w-full justify-between items-end z-20'):
                                ui.label('点击打开').classes('text-xs text-gray-400')
                                
                                # === 新增：重命名按钮 ===
                                ui.button(icon='edit', on_click=lambda e, b=book['name']: open_rename_dialog(b)) \
                                    .props('flat round dense color=grey size=sm') \
                                    .classes('opacity-0 group-hover:opacity-100 transition-opacity bg-white hover:bg-gray-100 shadow-sm') \
                                    .tooltip('重命名')

        async def switch_and_close(name):
            if name == app_state.current_book_name:
                dialog.close()
                return
            
            ui.notify(f'正在切换至《{name}》...', type='info', spinner=True)
            
            # 切换数据 (这是一个同步函数，直接调用即可)
            app_state.load_project(name)
            
            # 刷新主界面
            from . import writing, settings
            
            # 重新加载第一章
            # 【关键修改】这里增加了 await
            if app_state.structure:
                await writing.load_chapter(0)
            else:
                # 如果新书没有章节，手动清空编辑器，防止残留上一本书的内容
                if ui_refs.get('editor_title'): ui_refs['editor_title'].value = ""
                if ui_refs.get('editor_outline'): ui_refs['editor_outline'].value = ""
                if ui_refs.get('editor_content'): ui_refs['editor_content'].value = ""
                if ui_refs.get('time_label'): ui_refs['time_label'].value = ""
                if ui_refs.get('time_events'): ui_refs['time_events'].value = ""
            
            # 刷新设定集 UI
            settings.refresh_char_ui()
            settings.refresh_loc_ui()
            settings.refresh_item_ui() # 建议加上物品刷新
            settings.refresh_config_ui() # 建议加上配置刷新
            
            dialog.close()
            ui.notify(f'已切换至《{name}》', type='positive')

        def create_new_book_dialog():
            with ui.dialog() as d, ui.card():
                ui.label('新建小说项目').classes('text-lg font-bold')
                name_input = ui.input('书名 (推荐英文或拼音)').classes('w-64').props('autofocus')
                
                async def create():
                    name = name_input.value
                    if not name: return
                    success, msg = library.create_book(name)
                    if success:
                        ui.notify(f'创建成功: {msg}', type='positive')
                        d.close()
                        refresh_grid() # 刷新书架
                    else:
                        ui.notify(f'创建失败: {msg}', type='negative')
                
                with ui.row().classes('w-full justify-end mt-4'):
                    ui.button('取消', on_click=d.close).props('flat')
                    ui.button('创建', on_click=create).props('color=purple')
            d.open()
        # === 新增：重命名弹窗逻辑 ===
        def open_rename_dialog(old_name):
            with ui.dialog() as d, ui.card():
                ui.label(f'重命名: {old_name}').classes('text-lg font-bold')
                name_input = ui.input('新书名', value=old_name).classes('w-64').props('autofocus')
                
                async def confirm_rename():
                    new_name = name_input.value
                    if not new_name or new_name == old_name: 
                        d.close()
                        return

                    success, res = library.rename_book(old_name, new_name)
                    
                    if success:
                        final_name = res
                        ui.notify(f'已重命名为: {final_name}', type='positive')
                        
                        # 特殊情况处理：如果改的是当前正在编辑的书
                        if app_state.current_book_name == old_name:
                            app_state.current_book_name = final_name
                            # 更新全局配置，防止下次启动找不到旧名字
                            backend.CFG['last_open_book'] = final_name
                            backend.save_global_config(backend.CFG)
                            
                            # 还需要更新 app_state.manager 里的 root_dir，否则文件读写会报错
                            # 最简单的办法：重新加载一次项目
                            app_state.load_project(final_name)
                            
                        d.close()
                        refresh_grid() # 刷新网格显示新名字
                    else:
                        ui.notify(f'重命名失败: {res}', type='negative')

                with ui.row().classes('w-full justify-end mt-4'):
                    ui.button('取消', on_click=d.close).props('flat')
                    ui.button('确认', on_click=confirm_rename).props('color=purple')
            d.open()

        refresh_grid()
    
    dialog.open()