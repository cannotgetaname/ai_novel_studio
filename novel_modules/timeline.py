from nicegui import ui, run
import backend
import json
from .state import app_state, ui_refs

async def analyze_time():
    content = ui_refs['editor_content'].value
    if not content or len(content) < 50:
        ui.notify('正文太短，无法分析', type='warning')
        return
    
    idx = app_state.current_chapter_idx
    prev_time = "故事开始"
    if idx > 0:
        prev_time = app_state.structure[idx-1].get('time_info', {}).get('label', '未知')
        
    ui.notify('正在推演时间线...', spinner=True)
    res = await run.io_bound(backend.sync_analyze_time, content, prev_time)
    
    try:
        clean_res = res.replace("```json", "").replace("```", "").strip()
        start = clean_res.find('{')
        end = clean_res.rfind('}')
        if start != -1 and end != -1:
            json_str = clean_res[start:end+1]
            data = json.loads(json_str)
            
            if ui_refs['time_label']: ui_refs['time_label'].value = data.get('label', '未知')
            if ui_refs['time_events']: 
                events = data.get('events', [])
                ui_refs['time_events'].value = "\n".join(events)
            
            ui.notify(f"时间推进: {data.get('duration')}", type='positive')
            ui.notify('请点击【保存】以更新时间轴', type='warning', close_button=True)
        else:
            raise ValueError("未找到有效的 JSON 结构")
    except Exception as e:
        ui.notify(f'解析失败: {e}', type='negative')

def refresh_timeline():
    if not ui_refs['timeline_container']: return
    ui_refs['timeline_container'].clear()
    
    with ui_refs['timeline_container']:
        has_data = False
        for chap in app_state.structure:
            t_info = chap.get('time_info', {})
            if t_info.get('events') or t_info.get('label') != "未知时间":
                has_data = True
                break
        
        if not has_data:
            ui.label("暂无时间线数据。请在写作页面点击【⏱️ 分析时间】并【保存】。").classes('text-grey italic p-4')
            return

        with ui.timeline(side='right'):
            for chap in app_state.structure:
                t_info = chap.get('time_info', {})
                events = t_info.get('events', [])
                
                if events or t_info.get('label') != "未知时间":
                    ui.timeline_entry(
                        title=f"第{chap['id']}章 {chap['title']}",
                        subtitle=t_info.get('label', ''),
                        body="\n".join([f"• {e}" for e in events]),
                        icon='schedule'
                    )