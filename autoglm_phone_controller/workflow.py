from __future__ import annotations

from typing import Any


def build_workflow_prompt(
    *,
    original_task: str,
    platform: str,
    steps: list[Any],
) -> str:
    step_lines = []
    completion_message = ""

    for step in steps:
        action = step.action or {}
        action_name = action.get("action") or ("finish" if action.get("_metadata") == "finish" else "Unknown")
        if action_name == "Launch":
            line = f"{step.index}. 启动{action.get('app', platform)}。"
        elif action_name == "Tap":
            target = _compact_text(step.thinking) or "点击当前页面中与任务相关的控件"
            line = f"{step.index}. {target}"
            if step.point_norm:
                line += f"\n   - 主手机参考坐标：{step.point_norm}"
            if step.image_url:
                line += f"\n   - 主手机参考截图：{step.image_url}"
        elif action_name in ("Type", "Type_Name"):
            line = f"{step.index}. 输入文本：{action.get('text', '')}。"
        elif action_name == "Swipe":
            line = f"{step.index}. 滑动页面查找目标内容。"
            start = action.get("start")
            end = action.get("end")
            if start and end:
                line += f"\n   - 主手机参考滑动：start={start}, end={end}"
        elif action_name == "Back":
            line = f"{step.index}. 返回上一级页面。"
        elif action_name == "Home":
            line = f"{step.index}. 回到系统桌面。"
        elif action_name == "Wait":
            line = f"{step.index}. 等待页面加载：{action.get('duration', '1 seconds')}。"
        elif action_name == "finish":
            completion_message = step.message or "任务已完成。"
            line = f"{step.index}. 确认任务完成并结束：{completion_message}"
        else:
            line = f"{step.index}. 执行动作 {action_name}。"
        step_lines.append(line)

    completion = completion_message or "当前页面满足用户任务目标。"
    verified_steps = "\n".join(step_lines) if step_lines else "无已验证步骤。"

    return f"""用户任务：
{original_task}

目标平台：
{platform}

这是主手机已经验证成功的执行流程。请参考流程完成任务，但不要照搬主手机坐标。每一步必须根据当前手机截图重新判断正确位置。

已验证流程：
{verified_steps}

执行约束：
1. 只操作{platform}。
2. 如果当前 App 不是{platform}，先执行 Launch {platform}。
3. 如果当前页面和主手机不同，请根据当前页面完成同等语义动作。
4. 主手机坐标只作为参考，不能作为唯一依据。
5. 如果出现广告、优惠券、活动弹窗，优先关闭。
6. 如果出现登录、验证码、权限授权，执行 Take_over。
7. 如果用户只要求搜索或浏览，不要进入下单、支付、提交订单页面。
8. 如果连续三步页面无明显变化，返回上一级重新搜索。

完成条件：
{completion}

请严格按照系统动作格式输出下一步动作。
"""


def _compact_text(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= 90:
        return cleaned
    return cleaned[:90] + "..."
