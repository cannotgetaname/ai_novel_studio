"""
智能工具箱模块
提供多种 AI 辅助创作工具，支持参数配置和保存到素材库
"""

from nicegui import ui, run
from novel_modules.state import app_state, manager, ui_refs
import backend


# ==================== 工具配置 ====================

TOOL_CONFIG = {
    "naming": {
        "name": "起名大全",
        "icon": "badge",
        "color": "blue",
        "description": "生成各类名称，包括人名、组织、功法、法宝等",
        "sub_tools": [
            {"id": "name_char_cn", "name": "东方人名", "params": ["genre", "count"], "desc": "生成东方风格人名"},
            {"id": "name_char_en", "name": "西幻人名", "params": ["count"], "desc": "生成西方奇幻风格人名"},
            {"id": "name_org", "name": "组织势力", "params": ["genre", "count"], "desc": "生成宗门帮派名称"},
            {"id": "name_skill", "name": "功法武技", "params": ["genre", "count"], "desc": "生成武功功法名称"},
            {"id": "name_item", "name": "法宝丹药", "params": ["genre", "count"], "save_to": "items", "desc": "生成法宝丹药名称"},
            {"id": "name_location", "name": "地名场景", "params": ["genre", "count"], "save_to": "locations", "desc": "生成地名场景名称"},
        ]
    },
    "character": {
        "name": "角色生成器",
        "icon": "person",
        "color": "purple",
        "description": "生成完整角色设定，可直接保存到人物库",
        "sub_tools": [
            {"id": "char_protagonist", "name": "主角", "params": ["genre", "gender"], "save_to": "characters", "desc": "生成主角完整设定"},
            {"id": "char_supporting", "name": "配角", "params": ["genre", "gender"], "save_to": "characters", "desc": "生成配角完整设定"},
            {"id": "char_villain", "name": "反派", "params": ["genre", "gender"], "save_to": "characters", "desc": "生成反派完整设定"},
        ]
    },
    "title": {
        "name": "书名生成器",
        "icon": "menu_book",
        "color": "teal",
        "description": "根据题材生成吸引眼球的书名",
        "sub_tools": [
            {"id": "title_genre", "name": "按题材生成", "params": ["genre", "count"], "desc": "根据题材生成书名"},
        ]
    },
    "conflict": {
        "name": "冲突生成器",
        "icon": "bolt",
        "color": "orange",
        "description": "设计戏剧性冲突，推动剧情发展",
        "sub_tools": [
            {"id": "conflict_person", "name": "人物冲突", "params": ["genre"], "desc": "设计人物间冲突"},
            {"id": "conflict_plot", "name": "剧情冲突", "params": ["genre"], "desc": "设计剧情层面冲突"},
            {"id": "conflict_world", "name": "世界观冲突", "params": ["genre"], "desc": "设计世界观层面冲突"},
        ]
    },
    "synopsis": {
        "name": "简介生成器",
        "icon": "description",
        "color": "indigo",
        "description": "生成吸引读者的作品简介",
        "sub_tools": [
            {"id": "synopsis_short", "name": "简短简介", "params": ["genre"], "desc": "生成100字以内简介"},
            {"id": "synopsis_long", "name": "详细简介", "params": ["genre"], "desc": "生成详细完整简介"},
        ]
    },
    "scene": {
        "name": "场景生成器",
        "icon": "landscape",
        "color": "green",
        "description": "生成环境与场景描写",
        "sub_tools": [
            {"id": "scene_environment", "name": "环境描写", "params": ["genre", "scene_type"], "desc": "生成环境氛围描写"},
            {"id": "scene_battle", "name": "战斗场景", "params": ["genre"], "desc": "生成战斗场面描写"},
            {"id": "scene_emotion", "name": "情感场景", "params": ["genre", "emotion_type"], "desc": "生成情感场景描写"},
        ]
    },
    "goldfinger": {
        "name": "金手指生成器",
        "icon": "stars",
        "color": "amber",
        "description": "生成独特的金手指设定",
        "sub_tools": [
            {"id": "goldfinger_system", "name": "系统类", "params": ["genre"], "desc": "生成系统类金手指"},
            {"id": "goldfinger_talent", "name": "天赋类", "params": ["genre"], "desc": "生成天赋类金手指"},
            {"id": "goldfinger_item", "name": "物品类", "params": ["genre"], "desc": "生成物品类金手指"},
        ]
    },
    "twist": {
        "name": "剧情转折",
        "icon": "shuffle",
        "color": "deep-purple",
        "description": "生成意想不到的剧情转折",
        "sub_tools": [
            {"id": "twist_unexpected", "name": "意外转折", "params": ["genre"], "desc": "生成意外转折"},
            {"id": "twist_reversal", "name": "反转剧情", "params": ["genre"], "desc": "生成剧情反转"},
        ]
    }
}

# 题材选项
GENRE_OPTIONS = ["玄幻", "仙侠", "都市", "科幻", "武侠", "历史", "悬疑", "言情", "奇幻", "游戏"]

# 场景类型
SCENE_TYPES = ["山林", "城市", "宫殿", "洞府", "战场", "遗迹", "异世界"]

# 情感类型
EMOTION_TYPES = ["温馨", "悲伤", "愤怒", "感动", "紧张"]


# ==================== UI 组件 ====================

def create_toolbox_ui():
    """创建智能工具箱主界面"""

    with ui.column().classes('w-full h-full p-4 gap-4'):
        # 顶部标题
        with ui.row().classes('w-full items-center gap-2'):
            ui.icon('build', size='md').classes('text-primary')
            ui.label('智能工具箱').classes('text-h5 font-bold')
            ui.label('选择工具开始创作').classes('text-grey-6 ml-2')

        # 主内容区 - 工具类别卡片网格
        ui_refs['toolbox_panel'] = ui.column().classes('w-full')
        show_tool_categories()


def show_tool_categories():
    """显示工具类别卡片"""
    panel = ui_refs.get('toolbox_panel')
    if not panel:
        return

    panel.clear()

    with panel:
        # 使用网格布局，每行4个固定宽度卡片
        with ui.row().classes('w-full gap-4 flex-wrap justify-start'):
            for tool_key in TOOL_CONFIG.keys():
                create_category_card(tool_key, TOOL_CONFIG[tool_key])


def create_category_card(tool_key: str, tool: dict):
    """创建工具类别卡片"""
    color = tool.get('color', 'blue')

    card = ui.card().classes(
        'w-[340px] h-[200px] cursor-pointer hover:shadow-lg transition-shadow'
    )
    card.on('click', lambda tk=tool_key: show_sub_tools(tk))

    with card:
        with ui.column().classes('w-full h-full items-center justify-center gap-3'):
            ui.icon(tool['icon'], size='48px').props(f'color={color}')
            with ui.column().classes('items-center'):
                ui.label(tool['name']).classes('text-subtitle1 font-bold text-center')
                ui.label(tool['description']).classes('text-xs text-grey-6 text-center')


def show_sub_tools(tool_key: str):
    """显示子工具列表"""
    panel = ui_refs.get('toolbox_panel')
    if not panel:
        return

    panel.clear()
    tool = TOOL_CONFIG[tool_key]
    color = tool.get('color', 'blue')

    with panel:
        # 返回按钮和标题
        with ui.row().classes('w-full items-center gap-2 mb-4'):
            ui.button(icon='arrow_back', on_click=lambda: show_tool_categories()) \
                .props('flat round color=grey')
            ui.icon(tool['icon'], size='md').props(f'color={color}')
            ui.label(tool['name']).classes('text-h6 font-bold')

        # 子工具卡片网格
        with ui.row().classes('w-full gap-4 flex-wrap'):
            for sub in tool['sub_tools']:
                create_sub_tool_card(tool_key, sub, color)


def create_sub_tool_card(tool_key: str, sub_tool: dict, color: str):
    """创建子工具卡片"""
    save_to = sub_tool.get('save_to')
    save_badge = ''
    if save_to:
        save_names = {'characters': '人物', 'items': '物品', 'locations': '地点'}
        save_badge = f' [{save_names.get(save_to, save_to)}]'

    with ui.card().classes(
        f'w-[280px] cursor-pointer hover:shadow-lg transition-all hover:scale-[1.02] border border-grey-3'
    ).on('click', lambda s=sub_tool, c=color, tk=tool_key: open_tool_panel(tk, s, c)):
        with ui.column().classes('w-full gap-2 p-2'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label(sub_tool['name']).classes('text-subtitle1 font-bold')
                if save_to:
                    ui.badge(save_names.get(save_to, save_to), color='green').classes('text-xs')
            ui.label(sub_tool.get('desc', '')).classes('text-xs text-grey-6')


def open_tool_panel(tool_key: str, sub_tool: dict, color: str):
    """打开工具面板"""
    panel = ui_refs.get('toolbox_panel')
    if not panel:
        return

    panel.clear()

    with panel:
        # 标题区
        with ui.row().classes('w-full items-center gap-2 mb-4'):
            ui.button(icon='arrow_back', on_click=lambda tk=tool_key: show_sub_tools(tk)) \
                .props('flat round color=grey')
            ui.label(sub_tool['name']).classes('text-h6 font-bold')

        # 参数设置卡片
        params = sub_tool.get('params', [])
        param_values = {}

        with ui.card().classes('w-full mb-4'):
            with ui.row().classes('w-full items-center gap-2 p-2 bg-grey-1'):
                ui.icon('tune').classes('text-grey-6')
                ui.label('参数设置').classes('font-bold')

            with ui.row().classes('w-full gap-4 p-4'):
                # 题材参数
                if 'genre' in params:
                    with ui.column().classes('gap-1 flex-1'):
                        ui.label('题材').classes('text-xs text-grey-6')
                        param_values['genre'] = ui.select(
                            options=GENRE_OPTIONS,
                            value='玄幻'
                        ).classes('w-full').props('dense outlined')

                # 数量参数
                if 'count' in params:
                    with ui.column().classes('gap-1 flex-1'):
                        ui.label('数量').classes('text-xs text-grey-6')
                        param_values['count'] = ui.number(
                            value=5,
                            min=1,
                            max=20
                        ).classes('w-full').props('dense outlined')

                # 性别参数
                if 'gender' in params:
                    with ui.column().classes('gap-1 flex-1'):
                        ui.label('性别').classes('text-xs text-grey-6')
                        param_values['gender'] = ui.select(
                            options=['男', '女', '随机'],
                            value='随机'
                        ).classes('w-full').props('dense outlined')

                # 场景类型
                if 'scene_type' in params:
                    with ui.column().classes('gap-1 flex-1'):
                        ui.label('场景类型').classes('text-xs text-grey-6')
                        param_values['scene_type'] = ui.select(
                            options=SCENE_TYPES,
                            value='山林'
                        ).classes('w-full').props('dense outlined')

                # 情感类型
                if 'emotion_type' in params:
                    with ui.column().classes('gap-1 flex-1'):
                        ui.label('情感类型').classes('text-xs text-grey-6')
                        param_values['emotion_type'] = ui.select(
                            options=EMOTION_TYPES,
                            value='温馨'
                        ).classes('w-full').props('dense outlined')

        # 结果区
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center gap-2 p-2 bg-grey-1'):
                ui.icon('article').classes('text-grey-6')
                ui.label('生成结果').classes('font-bold')

            result_area = ui.textarea(
                placeholder='点击"开始生成"按钮...'
            ).classes('w-full p-2').props('rows=12 outlined')

        # 操作按钮
        with ui.row().classes('w-full gap-2 mt-4'):
            ui.button('开始生成', icon='play_arrow',
                      on_click=lambda: generate_result(sub_tool, param_values, result_area)) \
                .props(f'color={color} unelevated').classes('flex-1')

            ui.button('复制', icon='content_copy',
                      on_click=lambda: copy_result(result_area)) \
                .props('outline').classes('flex-1')

            # 保存按钮
            save_to = sub_tool.get('save_to')
            if save_to:
                ui.button(f'保存到{get_save_target_name(save_to)}', icon='save',
                          on_click=lambda: save_result(sub_tool, result_area)) \
                    .props('outline color=green').classes('flex-1')


def get_save_target_name(save_to: str) -> str:
    """获取保存目标名称"""
    names = {
        'characters': '人物库',
        'items': '物品库',
        'locations': '地点库'
    }
    return names.get(save_to, save_to)


# ==================== 核心功能 ====================

async def generate_result(sub_tool: dict, param_values: dict, result_area):
    """生成结果"""
    tool_id = sub_tool['id']
    params = {k: v.value if hasattr(v, 'value') else v for k, v in param_values.items()}

    result_area.value = '正在生成...'
    ui.notify('正在生成，请稍候...', type='info')

    try:
        result = await run.io_bound(
            backend.generate_toolbox_content,
            tool_id,
            params
        )
        result_area.value = result
        ui.notify('生成完成', type='positive')
    except Exception as e:
        result_area.value = f'生成失败: {str(e)}'
        ui.notify('生成失败', type='negative')


def copy_result(result_area):
    """复制结果"""
    if result_area.value and not result_area.value.startswith('正在'):
        import json
        safe_content = json.dumps(result_area.value)
        ui.run_javascript(f'navigator.clipboard.writeText(JSON.parse({safe_content}))')
        ui.notify('已复制到剪贴板', type='positive')


async def save_result(sub_tool: dict, result_area):
    """保存结果到素材库"""
    save_to = sub_tool.get('save_to')
    content = result_area.value

    if not content or content.startswith('正在') or content.startswith('生成失败'):
        ui.notify('没有可保存的内容', type='warning')
        return

    try:
        if save_to == 'characters':
            await save_to_characters(content)
        elif save_to == 'items':
            await save_to_items(content)
        elif save_to == 'locations':
            await save_to_locations(content)
        else:
            ui.notify('未知的保存目标', type='warning')
    except Exception as e:
        ui.notify(f'保存失败: {str(e)}', type='negative')


async def save_to_characters(content: str):
    """保存到人物库"""
    with ui.dialog() as dialog, ui.card().classes('w-[500px] p-4'):
        ui.label('保存人物').classes('text-h6 mb-4')

        name_input = ui.input(label='人物名称').classes('w-full mb-2')
        gender_select = ui.select(options=['男', '女', '未知'], label='性别', value='未知').classes('w-full mb-2')
        role_select = ui.select(options=['主角', '重要配角', '普通配角', '反派', '龙套'], label='角色定位', value='普通配角').classes('w-full mb-2')
        bio_input = ui.textarea(label='人物简介', value=content[:500]).classes('w-full mb-2').props('rows=4')

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('取消', on_click=dialog.close).props('flat')

            async def do_save():
                if not name_input.value:
                    ui.notify('请输入人物名称', type='warning')
                    return

                char = {
                    "name": name_input.value,
                    "gender": gender_select.value,
                    "role": role_select.value,
                    "status": "存活",
                    "bio": bio_input.value,
                    "relations": []
                }

                characters = app_state.characters
                characters.append(char)
                await run.io_bound(manager.save_characters, characters)
                app_state.characters = characters

                ui.notify(f'已保存人物: {name_input.value}', type='positive')
                dialog.close()

            ui.button('保存', on_click=do_save).props('color=primary')

    dialog.open()


async def save_to_items(content: str):
    """保存到物品库"""
    with ui.dialog() as dialog, ui.card().classes('w-[500px] p-4'):
        ui.label('保存物品').classes('text-h6 mb-4')

        name_input = ui.input(label='物品名称').classes('w-full mb-2')
        type_select = ui.select(
            options=['法宝', '丹药', '武器', '防具', '材料', '其他'],
            label='物品类型',
            value='其他'
        ).classes('w-full mb-2')
        desc_input = ui.textarea(label='物品描述', value=content[:500]).classes('w-full mb-2').props('rows=4')

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('取消', on_click=dialog.close).props('flat')

            async def do_save():
                if not name_input.value:
                    ui.notify('请输入物品名称', type='warning')
                    return

                item = {
                    "name": name_input.value,
                    "type": type_select.value,
                    "owner": "主角",
                    "desc": desc_input.value
                }

                items = app_state.items
                items.append(item)
                await run.io_bound(manager.save_items, items)
                app_state.items = items

                ui.notify(f'已保存物品: {name_input.value}', type='positive')
                dialog.close()

            ui.button('保存', on_click=do_save).props('color=primary')

    dialog.open()


async def save_to_locations(content: str):
    """保存到地点库"""
    with ui.dialog() as dialog, ui.card().classes('w-[500px] p-4'):
        ui.label('保存地点').classes('text-h6 mb-4')

        name_input = ui.input(label='地点名称').classes('w-full mb-2')
        desc_input = ui.textarea(label='地点描述', value=content[:500]).classes('w-full mb-2').props('rows=4')

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('取消', on_click=dialog.close).props('flat')

            async def do_save():
                if not name_input.value:
                    ui.notify('请输入地点名称', type='warning')
                    return

                location = {
                    "name": name_input.value,
                    "desc": desc_input.value,
                    "neighbors": []
                }

                locations = app_state.locations
                locations.append(location)
                await run.io_bound(manager.save_locations, locations)
                app_state.locations = locations

                ui.notify(f'已保存地点: {name_input.value}', type='positive')
                dialog.close()

            ui.button('保存', on_click=do_save).props('color=primary')

    dialog.open()