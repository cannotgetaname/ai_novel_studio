import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 清除代理设置，避免网络问题
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
for env_var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    if env_var in os.environ:
        del os.environ[env_var]

from nicegui import ui, run
import backend
from novel_modules.state import app_state, ui_refs, manager
from novel_modules import writing, settings, architect, timeline
from novel_modules import outline_ui  # <--- 新引入
from novel_modules import bookshelf # <--- 引入
from novel_modules import book_analysis # <--- 拆书分析
from novel_modules import toolbox # <--- 智能工具箱


# ==================== 世界观结构化编辑器 ====================

def create_world_view_editor():
    """创建结构化世界观编辑器"""

    # 获取或初始化结构化数据
    world_view_data = app_state.settings.get('world_view_structured', {
        "basic_info": {"genre": "", "era": "", "tech_level": ""},
        "core_settings": {"power_system": "", "social_structure": "", "special_rules": ""},
        "key_elements": {"important_items": "", "organizations": "", "locations": ""},
        "background": {"history": "", "main_conflict": "", "development": ""}
    })

    # 存储输入框引用
    inputs = {}

    with ui.row().classes('w-full h-full no-wrap gap-0'):
        # 左侧工具栏
        with ui.column().classes('w-52 h-full p-3 bg-grey-1 border-r shrink-0 gap-3'):
            ui.label('世界观设定').classes('text-lg font-bold text-grey-8')

            ui.separator()

            # 模板选择
            ui.label('快速模板').classes('text-xs text-grey-6')
            template_select = ui.select(
                options=list(backend.WORLD_VIEW_TEMPLATES.keys()),
                label='选择模板',
                value=None
            ).classes('w-full').props('dense clearable')

            def apply_template():
                selected = template_select.value
                if selected:
                    template = backend.WORLD_VIEW_TEMPLATES.get(selected, {})
                    # 更新数据
                    world_view_data['basic_info'] = template.get('basic_info', {}).copy()
                    world_view_data['core_settings'] = template.get('core_settings', {}).copy()
                    world_view_data['key_elements'] = template.get('key_elements', {}).copy()
                    world_view_data['background'] = template.get('background', {}).copy()
                    # 更新 UI
                    for section, fields in inputs.items():
                        for field_name, input_elem in fields.items():
                            value = world_view_data.get(section, {}).get(field_name, '')
                            input_elem.set_value(value)
                    ui.notify(f'已应用"{selected}"模板', type='info')
                    template_select.set_value(None)

            template_select.on('update:model-value', apply_template)

            ui.separator()

            # 操作按钮
            async def save_world_view():
                # 收集数据
                for section, fields in inputs.items():
                    for field_name, input_elem in fields.items():
                        world_view_data.setdefault(section, {})[field_name] = input_elem.value

                # 保存结构化数据
                app_state.settings['world_view_structured'] = world_view_data
                # 同时生成 Markdown 格式
                app_state.settings['world_view'] = backend.world_view_structured_to_markdown(world_view_data)

                await run.io_bound(manager.save_settings, app_state.settings)
                ui.notify('世界观已保存', type='positive')

            ui.button('保存设定', icon='save', on_click=save_world_view) \
                .props('color=green w-full unelevated')

            ui.separator()

            # 一致性检查
            async def check_consistency():
                # 收集数据
                for section, fields in inputs.items():
                    for field_name, input_elem in fields.items():
                        world_view_data.setdefault(section, {})[field_name] = input_elem.value

                ui.notify('正在检查一致性...', type='info', timeout=0)

                result = await run.io_bound(
                    backend.check_world_view_consistency,
                    world_view_data
                )

                ui.notify.dismiss()

                if result['success']:
                    show_consistency_result(result)
                else:
                    ui.notify('检查失败', type='negative')

            ui.button('一致性检查', icon='fact_check', on_click=check_consistency) \
                .props('color=blue w-full outline')

            ui.label('提示：设定会被 RAG 索引，用于保持剧情一致。').classes('text-xs text-grey-5 italic mt-auto')

        # 右侧编辑区
        with ui.column().classes('flex-grow h-full p-0 overflow-hidden'):
            with ui.scroll_area().classes('w-full h-full'):
                with ui.column().classes('w-full p-4 gap-4'):
                    # 基本信息
                    with ui.card().classes('w-full'):
                        with ui.expansion('基本信息', icon='info').classes('w-full'):
                            inputs['basic_info'] = {}
                            with ui.grid(columns=3).classes('w-full gap-4 p-2'):
                                with ui.column().classes('gap-1'):
                                    ui.label('题材类型').classes('text-xs text-grey-6')
                                    inputs['basic_info']['genre'] = ui.input(
                                        placeholder='如：玄幻修仙、科幻赛博'
                                    ).classes('w-full').props('dense')
                                with ui.column().classes('gap-1'):
                                    ui.label('时代背景').classes('text-xs text-grey-6')
                                    inputs['basic_info']['era'] = ui.input(
                                        placeholder='如：上古时代、现代都市'
                                    ).classes('w-full').props('dense')
                                with ui.column().classes('gap-1'):
                                    ui.label('科技水平').classes('text-xs text-grey-6')
                                    inputs['basic_info']['tech_level'] = ui.input(
                                        placeholder='如：无科技、现代科技'
                                    ).classes('w-full').props('dense')

                    # 核心设定
                    with ui.card().classes('w-full'):
                        with ui.expansion('核心设定', icon='settings').classes('w-full'):
                            inputs['core_settings'] = {}
                            with ui.column().classes('w-full gap-3 p-2'):
                                with ui.column().classes('gap-1'):
                                    ui.label('力量体系').classes('text-xs text-grey-6')
                                    inputs['core_settings']['power_system'] = ui.textarea(
                                        placeholder='修炼境界、等级划分、能力体系等'
                                    ).classes('w-full').props('rows=3 dense')
                                with ui.column().classes('gap-1'):
                                    ui.label('社会结构').classes('text-xs text-grey-6')
                                    inputs['core_settings']['social_structure'] = ui.textarea(
                                        placeholder='势力分布、阶级划分、社会规则等'
                                    ).classes('w-full').props('rows=3 dense')
                                with ui.column().classes('gap-1'):
                                    ui.label('特殊规则').classes('text-xs text-grey-6')
                                    inputs['core_settings']['special_rules'] = ui.textarea(
                                        placeholder='世界观特有的规则、机制等'
                                    ).classes('w-full').props('rows=3 dense')

                    # 关键元素
                    with ui.card().classes('w-full'):
                        with ui.expansion('关键元素', icon='category').classes('w-full'):
                            inputs['key_elements'] = {}
                            with ui.column().classes('w-full gap-3 p-2'):
                                with ui.column().classes('gap-1'):
                                    ui.label('重要物品').classes('text-xs text-grey-6')
                                    inputs['key_elements']['important_items'] = ui.textarea(
                                        placeholder='神器、法宝、关键道具等'
                                    ).classes('w-full').props('rows=2 dense')
                                with ui.column().classes('gap-1'):
                                    ui.label('势力组织').classes('text-xs text-grey-6')
                                    inputs['key_elements']['organizations'] = ui.textarea(
                                        placeholder='宗门、帮派、企业、机构等'
                                    ).classes('w-full').props('rows=2 dense')
                                with ui.column().classes('gap-1'):
                                    ui.label('主要地点').classes('text-xs text-grey-6')
                                    inputs['key_elements']['locations'] = ui.textarea(
                                        placeholder='城市、秘境、重要场所等'
                                    ).classes('w-full').props('rows=2 dense')

                    # 背景故事
                    with ui.card().classes('w-full'):
                        with ui.expansion('背景故事', icon='history_edu').classes('w-full'):
                            inputs['background'] = {}
                            with ui.column().classes('w-full gap-3 p-2'):
                                with ui.column().classes('gap-1'):
                                    ui.label('历史背景').classes('text-xs text-grey-6')
                                    inputs['background']['history'] = ui.textarea(
                                        placeholder='世界观的历史、重大事件等'
                                    ).classes('w-full').props('rows=3 dense')
                                with ui.column().classes('gap-1'):
                                    ui.label('主要矛盾').classes('text-xs text-grey-6')
                                    inputs['background']['main_conflict'] = ui.textarea(
                                        placeholder='核心冲突、对立势力、矛盾根源等'
                                    ).classes('w-full').props('rows=3 dense')
                                with ui.column().classes('gap-1'):
                                    ui.label('发展趋势').classes('text-xs text-grey-6')
                                    inputs['background']['development'] = ui.textarea(
                                        placeholder='未来走向、剧情发展方向等'
                                    ).classes('w-full').props('rows=3 dense')

                    # 预览
                    with ui.card().classes('w-full'):
                        with ui.expansion('Markdown 预览', icon='preview').classes('w-full'):
                            preview_content = ui.markdown('').classes('prose max-w-none p-2')

                            def update_preview():
                                # 收集数据
                                for section, fields in inputs.items():
                                    for field_name, input_elem in fields.items():
                                        world_view_data.setdefault(section, {})[field_name] = input_elem.value
                                # 生成预览
                                md = backend.world_view_structured_to_markdown(world_view_data)
                                preview_content.content = md

                            ui.button('刷新预览', on_click=update_preview).props('flat size=sm color=primary')

    # 初始化数据
    for section, fields in inputs.items():
        for field_name, input_elem in fields.items():
            value = world_view_data.get(section, {}).get(field_name, '')
            input_elem.set_value(value)


def show_consistency_result(result: dict):
    """显示一致性检查结果"""
    issues = result.get('issues', [])
    assessment = result.get('overall_assessment', '')

    with ui.dialog() as dialog, ui.card().classes('w-[600px] max-h-[80vh]'):
        ui.label('世界观一致性检查结果').classes('text-h6 font-bold mb-4')

        with ui.scroll_area().classes('w-full h-[60vh]'):
            # 总体评价
            with ui.card().classes('w-full bg-blue-50 mb-4'):
                ui.label('总体评价').classes('text-subtitle1 font-bold text-blue-800 mb-2')
                ui.markdown(assessment).classes('text-sm')

            # 问题列表
            if issues:
                ui.label(f'发现 {len(issues)} 个问题').classes('text-subtitle1 font-bold mb-2')

                for i, issue in enumerate(issues, 1):
                    with ui.card().classes('w-full mb-2 border-l-4 border-orange-500'):
                        with ui.row().classes('w-full items-center gap-2'):
                            ui.label(f'问题 {i}').classes('font-bold text-orange-800')
                            ui.label(f'字段：{issue.get("field", "未知")}').classes('text-xs text-grey-6')

                        ui.label(issue.get('issue', '')).classes('text-sm mt-1')

                        with ui.row().classes('w-full items-center gap-1 mt-2'):
                            ui.label('建议：').classes('text-xs text-grey-6')
                            ui.label(issue.get('suggestion', '')).classes('text-sm text-green-700')
            else:
                ui.label('未发现问题').classes('text-green-700 font-bold')

        ui.button('关闭', on_click=dialog.close).props('flat')

    dialog.open()


@ui.page('/')
async def main_page():
    # 1. 初始化 UI 引用
    ui_refs['editor_title'] = None
    ui_refs['editor_outline'] = None
    ui_refs['editor_content'] = None
    ui_refs['char_container'] = None
    ui_refs['item_container'] = None
    ui_refs['loc_container'] = None
    ui_refs['chapter_list'] = None
    ui_refs['rag_debug'] = None
    ui_refs['review_panel'] = None
    ui_refs['right_tabs'] = None
    ui_refs['tab_ctx'] = None
    ui_refs['tab_rev'] = None
    ui_refs['char_count'] = None
    ui_refs['total_count'] = None
    ui_refs['char_view_mode'] = None
    ui_refs['char_graph_container'] = None
    ui_refs['time_label'] = None
    ui_refs['time_events'] = None
    ui_refs['timeline_container'] = None
    ui_refs['save_status'] = None
    ui_refs['config_container'] = None
    ui_refs['loc_view_mode'] = None
    ui_refs['loc_graph_container'] = None
    ui_refs['api_container'] = None
    ui_refs['prompts_container'] = None

    # 2. 定义辅助函数
    async def refresh_total_word_count():
        if ui_refs['total_count']:
            ui_refs['total_count'].set_text("统计中...")
            total = await run.io_bound(manager.get_total_word_count)
            ui_refs['total_count'].set_text(f"全书字数: {total:,}")

    async def show_detailed_stats():
        """显示详细的字数统计信息"""
        stats = await run.io_bound(manager.get_detailed_word_stats)

        with ui.dialog() as dialog, ui.card().classes('w-[600px] max-h-[80vh]'):
            ui.label('作品统计信息').classes('text-h6 font-bold mb-2')

            with ui.scroll_area().classes('w-full h-[60vh]'):
                # 总体统计
                with ui.card().classes('w-full bg-blue-50 mb-4'):
                    ui.label('总体概况').classes('text-subtitle1 font-bold text-blue-800')
                    with ui.grid(columns=2).classes('w-full gap-2 p-2'):
                        ui.label(f'总字数: {stats["total_words"]:,}').classes('font-bold')
                        ui.label(f'中文字数: {stats["chinese"]:,}')
                        ui.label(f'英文词数: {stats["english"]:,}')
                        ui.label(f'平均章节: {stats["avg_words"]:,} 字')
                        ui.label(f'章节总数: {stats["chapter_count"]} 章')
                        ui.label(f'分卷数量: {stats["volume_count"]} 卷')

                # 分卷详情
                ui.label('分卷详情').classes('text-subtitle1 font-bold mb-2')

                for vol in stats['volumes']:
                    with ui.expansion(f"{vol['title']} - {vol['words']:,}字 ({vol['chapter_count']}章)") \
                            .classes('w-full bg-white border mb-1'):
                        with ui.column().classes('w-full p-2'):
                            # 分卷统计概要
                            with ui.row().classes('w-full gap-4 mb-2 text-sm text-grey-7'):
                                ui.label(f'中文: {vol["chinese"]:,}')
                                ui.label(f'英文: {vol["english"]:,}')

                            # 章节列表
                            ui.label('章节列表:').classes('text-xs text-grey-6 mt-2')
                            with ui.column().classes('w-full gap-1'):
                                for chap in vol['chapters']:
                                    with ui.row().classes('w-full justify-between text-xs'):
                                        ui.label(f"第{chap['id']}章 {chap['title']}")
                                        ui.label(f"{chap['words']:,}字").classes('text-grey-6')

            ui.button('关闭', on_click=dialog.close).props('flat')

        dialog.open()

    def refresh_sidebar():
        if not ui_refs['chapter_list']: return
        ui_refs['chapter_list'].clear()

        # 预加载所有章节的字数统计
        chapter_word_counts = {}
        for chap in app_state.structure:
            content = manager.load_chapter_content(chap['id'])
            stats = backend.count_words(content)
            chapter_word_counts[chap['id']] = stats['total_words']

        with ui_refs['chapter_list']:
            for vol in app_state.volumes:
                vol_chapters = [c for c in app_state.structure if c.get('volume_id') == vol['id']]
                is_expanded = vol['id'] in app_state.expanded_volumes

                # 计算分卷总字数
                vol_words = sum(chapter_word_counts.get(c['id'], 0) for c in vol_chapters)

                with ui.expansion(f"{vol['title']} ({len(vol_chapters)}章 · {vol_words:,}字)", icon='book', value=is_expanded) \
                        .classes('w-full bg-blue-50 mb-1 border rounded shadow-sm') \
                        .on_value_change(lambda e, v=vol['id']: (app_state.expanded_volumes.add(v) if e.value else app_state.expanded_volumes.discard(v))) as expansion:

                    with ui.column().classes('w-full pl-0 gap-1 bg-white p-1'):
                        for chap in vol_chapters:
                            real_idx = app_state.structure.index(chap)
                            color = 'purple' if real_idx == app_state.current_chapter_idx else 'grey-8'
                            status_icon = ''
                            if chap.get('review_data', {}).get('issues'): status_icon += '[审]'
                            if chap.get('time_info', {}).get('events'): status_icon += '[时]'

                            word_count = chapter_word_counts.get(chap['id'], 0)

                            with ui.row().classes('w-full items-center gap-1 pl-2'):
                                ui.button(f"{chap['id']}. {chap['title']} {status_icon}",
                                          on_click=lambda i=real_idx: writing.load_chapter(i)) \
                                    .props(f'flat color={color} align=left no-caps dense size=sm') \
                                    .classes('flex-grow text-left hover:bg-grey-100')
                                ui.label(f"{word_count:,}字").classes('text-xs text-grey-5 mr-2')

                        with ui.row().classes('w-full justify-end pr-2 pt-1 border-t border-dashed'):
                            ui.button(icon='edit', on_click=lambda v=vol['id']: writing.rename_volume(v)) \
                                .props('flat size=xs color=grey').tooltip('重命名分卷')

                            ui.button(icon='add', on_click=lambda v=vol['id']: writing.add_chapter_to_volume(v)) \
                                .props('flat size=xs color=green').tooltip('在此卷添加章节')

    # 3. 注册全局回调
    app_state.refresh_sidebar = refresh_sidebar
    app_state.refresh_total_word_count = refresh_total_word_count

    # 4. 布局开始 (修正：Header 和 Drawer 必须在最外层)

    # --- 4.1 Header (固定顶部) ---
    with ui.header().classes('bg-white text-black shadow-sm shrink-0'):
        ui.button(on_click=lambda: drawer.toggle(), icon='menu').props('flat color=black')
        ui.label('AI 网文工作站').classes('text-h6')

    # --- 4.2 Left Drawer (左侧边栏) ---
    with ui.left_drawer(value=True).classes('bg-blue-50 flex flex-col') as drawer:
        # === 新增：书架入口区 ===
        with ui.column().classes('w-full p-2 mb-2 bg-purple-100 rounded border border-purple-200'):
            ui.label('当前作品:').classes('text-xs text-purple-600 font-bold')
            # 绑定显示当前书名
            book_label = ui.label().bind_text_from(app_state, 'current_book_name') \
                .classes('text-lg font-bold text-purple-900 truncate w-full')
            
            ui.button('切换/管理书籍', on_click=bookshelf.open_bookshelf_dialog) \
                .props('size=sm color=purple icon=swap_horiz w-full')
                
        ui.separator().classes('mb-2')
        
        ui.label('章节目录').classes('text-h6 q-mb-md')
        
        with ui.card().classes('w-full q-mb-sm bg-white p-2'):
            ui_refs['total_count'] = ui.label('全书字数: ---').classes('text-sm font-bold')
            with ui.row().classes('w-full'):
                ui.button('刷新', on_click=lambda: refresh_total_word_count()).props('flat size=sm color=primary').classes('w-1/3')
                ui.button('详情', on_click=lambda: show_detailed_stats()).props('flat size=sm color=indigo').classes('w-1/3')
                ui.button('导出', on_click=lambda: writing.export_novel()).props('flat size=sm color=grey').classes('w-1/3')
            
            with ui.row().classes('w-full q-mt-sm'):
                async def show_book_summary():
                    settings = await run.io_bound(manager.load_settings)
                    summary = settings.get('book_summary', '暂无总结，请先保存章节触发生成。')
                    with ui.dialog() as d, ui.card().classes('w-1/2'):
                        ui.label('全书剧情总纲').classes('text-h6 font-bold')
                        with ui.scroll_area().classes('h-64 border p-4 bg-grey-1 rounded'):
                            ui.markdown(summary).classes('text-lg leading-relaxed')
                        ui.button('关闭', on_click=d.close).props('flat')
                    d.open()
                ui.button('全书梗概', on_click=show_book_summary).props('flat size=sm color=purple').classes('w-full')

        with ui.scroll_area().classes('w-full flex-grow'):
            ui_refs['chapter_list'] = ui.column().classes('w-full')
            refresh_sidebar()
        
        ui.separator().classes('my-2')
        with ui.grid(columns=2).classes('w-full gap-2 pb-2'):
            ui.button('新建分卷', on_click=writing.add_new_volume).props('outline color=indigo size=sm icon=create_new_folder')
            ui.button('删除分卷', on_click=writing.delete_volume_dialog).props('outline color=red size=sm icon=folder_delete')
            ui.button('新建章节', on_click=writing.add_new_chapter_auto).props('color=green size=sm icon=note_add')
            ui.button('删除章节', on_click=writing.delete_current_chapter).props('color=red size=sm icon=delete_forever')
        ui.separator().classes('my-2')
        ui.label('全局工具').classes('text-xs font-bold text-grey-6 mb-1')
        ui.button('全局查找与替换', on_click=settings.open_global_search_dialog) \
            .props('flat color=blue-grey icon=find_replace w-full align=left').classes('w-full')

    # --- 4.3 主内容区域 (Tabs) ---
    # 【关键修正】这里使用 calc(100vh - 60px) 来扣除 Header 的高度，防止滚动条。
    # Header 大约 50-60px，这里预留 60px 比较安全。
    with ui.column().classes('w-full h-[calc(100vh-60px)] p-0 gap-0 no-wrap'):

        # 4.3.1 Tabs 栏 (固定高度)
        with ui.tabs().classes('w-full bg-primary text-white shadow-2 shrink-0') as tabs:
            # tab_outline = ui.tab('大纲树', icon='account_tree')
            tab_write = ui.tab('写作', icon='edit')
            tab_setting = ui.tab('设定', icon='people')
            t_graph = ui.tab('图谱', icon='hub')
            tab_arch = ui.tab('架构', icon='construction')
            tab_timeline = ui.tab('时间轴', icon='schedule')
            tab_analysis = ui.tab('拆书分析', icon='menu_book')
            tab_toolbox = ui.tab('智能工具箱', icon='build')
            tab_sys = ui.tab('系统设置', icon='settings')

        # 4.3.2 Tab Panels (占据剩余所有高度)
        # flex-grow: 占据剩余空间
        # h-0: 强制 Flex 容器根据空间计算高度，而非内容
        with ui.tab_panels(tabs, value=tab_write).classes('w-full flex-grow p-0 h-0').props('keep-alive'):
            
            # --- Tab 1: 写作 ---
            with ui.tab_panel(tab_write).classes('h-full w-full p-0'):
                writing.create_writing_tab()

            # --- Tab 2: 设定 ---
            with ui.tab_panel(tab_setting).classes('h-full w-full p-0 flex flex-col'):
                # 二级 Tabs（书籍相关设定）
                with ui.tabs().classes('w-full bg-grey-2 shrink-0') as set_tabs:
                    t_world = ui.tab('世界观')
                    t_char = ui.tab('人物')
                    t_item = ui.tab('物品')
                    t_loc = ui.tab('地点')

                # 二级 Tab Panels
                with ui.tab_panels(set_tabs, value=t_world).classes('w-full flex-grow h-0'):

                    # 2.1 世界观（结构化编辑器）
                    with ui.tab_panel(t_world).classes('h-full w-full p-0'):
                        create_world_view_editor()

                    # 2.2 人物
                    with ui.tab_panel(t_char).classes('h-full w-full p-2 flex flex-col'):
                        with ui.row().classes('w-full justify-between items-center pb-2 shrink-0'):
                            with ui.button_group():
                                ui.button('列表', on_click=lambda: [ui_refs['char_view_mode'].set_text('list'), settings.refresh_char_ui()]).props('size=sm')
                                ui.button('图谱', on_click=lambda: [ui_refs['char_view_mode'].set_text('graph'), settings.refresh_char_ui()]).props('size=sm')
                            ui_refs['char_view_mode'] = ui.label('list').classes('hidden') 
                            with ui.row():
                                ui.button(icon='refresh', on_click=settings.refresh_char_ui).props('flat round dense')
                                ui.button('添加人物', icon='add', on_click=lambda: settings.open_char_dialog()).props('size=sm color=blue')
                        
                        # 内容容器
                        with ui.element('div').classes('w-full flex-grow relative bg-white border'):
                            with ui.scroll_area().classes('w-full h-full').bind_visibility_from(ui_refs['char_view_mode'], 'text', backward=lambda x: x == 'list'):
                                ui_refs['char_container'] = ui.column().classes('w-full p-1')
                            with ui.element('div').classes('w-full h-full').bind_visibility_from(ui_refs['char_view_mode'], 'text', backward=lambda x: x == 'graph'):
                                ui_refs['char_graph_container'] = ui.column().classes('w-full h-full')
                            settings.refresh_char_ui()

                    # 2.3 物品
                    with ui.tab_panel(t_item).classes('h-full w-full p-2 flex flex-col'):
                        with ui.row().classes('w-full justify-end pb-2 shrink-0'):
                            ui.button(icon='refresh', on_click=settings.refresh_item_ui).props('flat round dense')
                            ui.button('添加物品', icon='add', on_click=lambda: settings.open_item_dialog()).props('size=sm color=orange')
                        
                        with ui.scroll_area().classes('w-full flex-grow border'):
                            ui_refs['item_container'] = ui.column().classes('w-full p-1')
                            settings.refresh_item_ui()

                    # 2.4 地点
                    with ui.tab_panel(t_loc).classes('h-full w-full p-2 flex flex-col'):
                        with ui.row().classes('w-full justify-between items-center pb-2 shrink-0'):
                            with ui.button_group():
                                ui.button('列表', on_click=lambda: [ui_refs['loc_view_mode'].set_text('list'), settings.refresh_loc_ui()]).props('size=sm')
                                ui.button('地图', on_click=lambda: [ui_refs['loc_view_mode'].set_text('graph'), settings.refresh_loc_ui()]).props('size=sm')
                            ui_refs['loc_view_mode'] = ui.label('list').classes('hidden')
                            
                            with ui.row():
                                ui.button('整理', icon='build', on_click=settings.open_connection_manager).props('flat size=sm dense color=grey')
                                ui.button(icon='refresh', on_click=settings.refresh_loc_ui).props('flat round dense')
                                ui.button('添加地点', icon='add', on_click=lambda: settings.open_loc_dialog()).props('size=sm color=green')
                        
                        with ui.element('div').classes('w-full flex-grow relative border'):
                            with ui.scroll_area().classes('w-full h-full').bind_visibility_from(ui_refs['loc_view_mode'], 'text', backward=lambda x: x == 'list'):
                                ui_refs['loc_container'] = ui.column().classes('w-full p-1')

                            with ui.element('div').classes('w-full h-full').bind_visibility_from(ui_refs['loc_view_mode'], 'text', backward=lambda x: x == 'graph'):
                                ui_refs['loc_graph_container'] = ui.column().classes('w-full h-full')
                            settings.refresh_loc_ui()

            # --- Tab 3: 图谱 ---
            with ui.tab_panel(t_graph).classes('h-full w-full p-0 flex flex-col'):
                settings.create_global_graph_panel()

            # --- Tab 4: 架构师 ---
            with ui.tab_panel(tab_arch).classes('h-full w-full p-4 flex flex-col'):
                architect.create_architect_ui()

            # --- Tab 5: 时间轴 ---
            with ui.tab_panel(tab_timeline).classes('h-full w-full p-4 flex flex-col'):
                with ui.row().classes('w-full justify-between items-center mb-4 shrink-0'):
                    ui.label('剧情时间轴').classes('text-h6')
                    ui.button('刷新', on_click=timeline.refresh_timeline).props('flat icon=refresh')
                with ui.scroll_area().classes('w-full flex-grow bg-grey-1 p-4 rounded'):
                    ui_refs['timeline_container'] = ui.column().classes('w-full')
                    timeline.refresh_timeline()

            # --- Tab 6: 拆书分析 ---
            with ui.tab_panel(tab_analysis).classes('h-full w-full p-0 flex flex-col'):
                book_analysis.create_analysis_ui()

            # --- Tab 7: 智能工具箱 ---
            with ui.tab_panel(tab_toolbox).classes('h-full w-full p-0 flex flex-col'):
                toolbox.create_toolbox_ui()

            # --- Tab 8: 系统设置 ---
            with ui.tab_panel(tab_sys).classes('h-full w-full p-0 flex flex-col'):
                # 二级 Tabs（全局系统设置）
                with ui.tabs().classes('w-full bg-grey-2 shrink-0') as sys_tabs:
                    t_api = ui.tab('API与模型')
                    t_prompts = ui.tab('提示词管理')
                    t_billing = ui.tab('费用管理')
                    t_goals = ui.tab('写作目标')

                # 二级 Tab Panels
                with ui.tab_panels(sys_tabs, value=t_api).classes('w-full flex-grow h-0'):

                    # 6.1 API与模型
                    with ui.tab_panel(t_api).classes('h-full w-full p-2 flex flex-col'):
                        with ui.scroll_area().classes('w-full flex-grow'):
                            ui_refs['api_container'] = ui.column().classes('w-full')
                            settings.refresh_api_ui()

                    # 6.2 提示词管理
                    with ui.tab_panel(t_prompts).classes('h-full w-full p-2 flex flex-col'):
                        with ui.scroll_area().classes('w-full flex-grow'):
                            ui_refs['prompts_container'] = ui.column().classes('w-full')
                            settings.refresh_prompts_ui()

                    # 6.3 费用管理
                    with ui.tab_panel(t_billing).classes('h-full w-full p-2 flex flex-col'):
                        with ui.scroll_area().classes('w-full flex-grow'):
                            ui_refs['billing_container'] = ui.column().classes('w-full')
                            settings.refresh_billing_ui()

                    # 6.4 写作目标
                    with ui.tab_panel(t_goals).classes('h-full w-full p-2 flex flex-col'):
                        with ui.scroll_area().classes('w-full flex-grow'):
                            ui_refs['goals_container'] = ui.column().classes('w-full')
                            settings.refresh_goals_ui()

    # 启动加载
    await writing.load_chapter(0)
    await refresh_total_word_count()

ui.run(title='AI Novel Studio', port=8081, reload=False)