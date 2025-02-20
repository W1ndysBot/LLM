# script/LLM/main.py

import logging
import os
import sys
import json
import asyncio

# 添加项目根目录到sys.path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.config import *
from app.api import *
from app.switch import load_switch, save_switch
from app.scripts.LLM.LLM import send_dify_request, handle_dify_response

# 数据存储路径，实际开发时，请将LLM替换为具体的数据存放路径
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "LLM",
)

# 临时消息id列表
temp_message_ids = []


# 查看功能开关状态
def load_function_status(group_id):
    return load_switch(group_id, "LLM")


# 保存功能开关状态
def save_function_status(group_id, status):
    save_switch(group_id, "LLM", status)


# 处理元事件，用于启动时确保数据目录存在
async def handle_meta_event(websocket, msg):
    """处理元事件"""
    os.makedirs(DATA_DIR, exist_ok=True)


# 处理开关状态
async def toggle_function_status(websocket, group_id, message_id, authorized):
    if not authorized:
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]❌❌❌你没有权限对LLM功能进行操作,请联系管理员。",
        )
        return

    if load_function_status(group_id):
        save_function_status(group_id, False)
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]🚫🚫🚫LLM功能已关闭",
        )
    else:
        save_function_status(group_id, True)
        await send_group_msg(
            websocket, group_id, f"[CQ:reply,id={message_id}]✅✅✅LLM功能已开启"
        )


# 群消息处理函数
async def handle_group_message(websocket, msg):
    """处理群消息"""
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        group_id = str(msg.get("group_id"))
        raw_message = str(msg.get("raw_message"))
        message_id = str(msg.get("message_id"))
        self_id = str(msg.get("self_id"))
        authorized = user_id in owner_id

        # 处理开关命令
        if raw_message == "LLM":
            await toggle_function_status(websocket, group_id, message_id, authorized)
            return
        # 检查功能是否开启
        if load_function_status(group_id):
            # 其他群消息处理逻辑
            if raw_message.startswith("卷卷") or f"[CQ:at,qq={self_id}]" in raw_message:
                await send_group_msg(
                    websocket,
                    group_id,
                    [
                        {"type": "reply", "data": {"id": message_id}},
                        {"type": "text", "data": {"text": "💬💬💬正在思考中..."}},
                    ],
                )
                response = await send_dify_request(user_id, raw_message)
                response = json.loads(response)
                answer, total_tokens, total_price, currency = handle_dify_response(
                    response
                )
                message = [
                    {"type": "reply", "data": {"id": message_id}},
                    {
                        "type": "text",
                        "data": {
                            "text": f"{answer}\n\n{total_tokens} tokens\n{total_price} {currency}"
                        },
                    },
                ]
                await send_group_msg(websocket, group_id, message)
                await asyncio.sleep(0.1)  # 等待0.1秒，让临时消息id存储生效
                if temp_message_ids:
                    for msg_id in temp_message_ids:
                        await delete_msg(websocket, msg_id)
                    temp_message_ids.clear()
    except Exception as e:
        logging.error(f"处理LLM群消息失败: {e}")
        await send_group_msg(
            websocket,
            group_id,
            "处理LLM群消息失败，错误信息：" + str(e),
        )
        return


# 私聊消息处理函数
async def handle_private_message(websocket, msg):
    """处理私聊消息"""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        raw_message = str(msg.get("raw_message"))
        # 私聊消息处理逻辑
        pass
    except Exception as e:
        logging.error(f"处理LLM私聊消息失败: {e}")
        await send_private_msg(
            websocket,
            msg.get("user_id"),
            "处理LLM私聊消息失败，错误信息：" + str(e),
        )
        return


# 群通知处理函数
async def handle_group_notice(websocket, msg):
    """处理群通知"""
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        group_id = str(msg.get("group_id"))
        raw_message = str(msg.get("raw_message"))
        role = str(msg.get("sender", {}).get("role"))
        message_id = str(msg.get("message_id"))

    except Exception as e:
        logging.error(f"处理LLM群通知失败: {e}")
        await send_group_msg(
            websocket,
            group_id,
            "处理LLM群通知失败，错误信息：" + str(e),
        )
        return


# 回应事件处理函数
async def handle_response(websocket, msg):
    """处理回调事件"""
    echo = msg.get("echo")
    if echo and echo == "💬💬💬正在思考中...":
        # 将message_id存储到临时消息id列表
        temp_message_ids.append(msg.get("message_id"))


# 统一事件处理入口
async def handle_events(websocket, msg):
    """统一事件处理入口"""
    post_type = msg.get("post_type", "response")  # 添加默认值
    try:
        # 处理回调事件
        if msg.get("status") == "ok":
            await handle_response(websocket, msg)
            return

        post_type = msg.get("post_type")

        # 处理元事件
        if post_type == "meta_event":
            await handle_meta_event(websocket, msg)

        # 处理消息事件
        elif post_type == "message":
            message_type = msg.get("message_type")
            if message_type == "group":
                await handle_group_message(websocket, msg)
            elif message_type == "private":
                await handle_private_message(websocket, msg)

        # 处理通知事件
        elif post_type == "notice":
            if msg.get("notice_type") == "group":
                await handle_group_notice(websocket, msg)

    except Exception as e:
        error_type = {
            "message": "消息",
            "notice": "通知",
            "request": "请求",
            "meta_event": "元事件",
        }.get(post_type, "未知")

        logging.error(f"处理LLM{error_type}事件失败: {e}")

        # 发送错误提示
        if post_type == "message":
            message_type = msg.get("message_type")
            if message_type == "group":
                await send_group_msg(
                    websocket,
                    msg.get("group_id"),
                    f"处理LLM{error_type}事件失败，错误信息：{str(e)}",
                )
            elif message_type == "private":
                await send_private_msg(
                    websocket,
                    msg.get("user_id"),
                    f"处理LLM{error_type}事件失败，错误信息：{str(e)}",
                )
