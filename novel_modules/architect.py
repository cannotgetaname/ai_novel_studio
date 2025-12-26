from nicegui import ui, run
import backend
import json
from .state import app_state, manager, memory, CFG

async def run_architect(theme_input, count_slider):
    if not app_state.structure:
        ui.notify('请先创建第一章', type='warning')
        return
    ui.notify('架构师正在回顾剧情...', spinner=True)
    
    recent_chapters = app_state.structure[-3:] 
    recent_context_text = ""
    for chap in recent_chapters:
        recent_context_text += f"第{chap['id']}章 [{chap['title']}]: {chap['outline']}\n"
    
    ui.notify('正在检索相关伏笔...', spinner=True)
    query = f"{theme_input.value}"
    valid_docs, _ = await run.io_bound(memory.query_related_memory, query)
    rag_context_text = "\n".join(valid_docs)
    
    start_id = app_state.structure[-1]['id'] + 1
    prompt = f"""
    【角色与世界观】{app_state.settings['world_view']}
    【相关历史伏笔】{rag_context_text}
    【最近剧情回顾】{recent_context_text}
    【接下来的剧情要求】{theme_input.value}
    【任务】请规划接下来的 {count_slider.value} 章大纲（从第 {start_id} 章开始）。
    要求：1. 剧情必须紧接“最近剧情回顾”，逻辑连贯。2. 利用“相关历史伏笔”中的信息。3. 严格遵守 JSON 格式，不要废话。
    """
    
    ui.notify('架构师正在推演...', spinner=True)
    res = await run.io_bound(backend.sync_call_llm, prompt, CFG['prompts']['architect_system'], task_type="architect")
    
    try:
        start_idx = res.find('[')
        end_idx = res.rfind(']')
        if start_idx == -1 or end_idx == -1: raise ValueError("未找到JSON数组")
        json_str = res[start_idx : end_idx + 1]
        new_data = json.loads(json_str)
        
        with ui.dialog() as dialog, ui.card().classes('w-1/2'):
            ui.label(f"✅ 成功规划 {len(new_data)} 章").classes('text-h6 text-green')
            with ui.scroll_area().classes('h-64 border p-2'):
                for item in new_data:
                    ui.label(f"📌 {item['title']}").classes('font-bold')
                    ui.label(f"{item['outline']}").classes('text-sm text-grey q-mb-sm')
            
            with ui.row().classes('w-full justify-end'):
                ui.button('放弃', on_click=dialog.close).props('flat color=grey')
                def confirm():
                    for item in new_data:
                        app_state.structure.append({
                            "id": app_state.structure[-1]['id'] + 1, 
                            "title": item['title'], 
                            "outline": item['outline'], 
                            "summary": "",
                            "time_info": {"label": "未知", "events": []}
                        })
                    run.io_bound(manager.save_structure, app_state.structure)
                    if app_state.refresh_sidebar: app_state.refresh_sidebar()
                    dialog.close()
                    ui.notify('大纲已导入！', type='positive')
                ui.button('确认导入', on_click=confirm).props('color=green')
        dialog.open()
    except Exception as e:
        ui.notify('格式解析失败', type='negative')