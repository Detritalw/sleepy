import requests
import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import time

from win_device import SERVER, SECRET, DEVICE_ID, DEVICE_SHOW_NAME
# from win_device import send_status as wd_send_status

VERSION = "v1.0.1"



def main():
    """主函数"""
    global log_text  # 全局变量，用于在函数中访问日志文本框
    # 初始化窗口
    root = tk.Tk()
    root.title("Sleepy Settings")
    root.geometry("800x600")
    menu = tk.Menu(root)
    root.config(menu=menu)
    root.protocol("WM_DELETE_WINDOW", exit_)  # 关闭窗口时调用exit_函数
    root.protocol("WM_QUERYENDSESSION", shutdown)  # 注销时调用shutdown函数
    
    # 初始化菜单
    # 创建菜单
    # 接口
    api_menu = tk.Menu(menu, tearoff=0)
    menu.add_cascade(label="接口", menu=api_menu)
    api_menu.add_command(label="获取站点元数据(meta)", command=get_meta)
    api_menu.add_command(label="获取状态", command=get_status)
    api_menu.add_command(label="获取可用状态列表", command=get_status_list)
    api_menu.add_command(label="获取统计信息", command=get_metrics)
    api_menu.add_command(label="设置状态(活着/似了)", command=set_status)
    api_menu.add_command(label="设置单个设备状态", command=send_status)
    api_menu.add_command(label="删除设备", command=delete_device)
    api_menu.add_command(label="清除所有设备", command=clear_devices)
    api_menu.add_command(label="隐私模式", command=private_mode)
    
    file_menu = tk.Menu(menu, tearoff=0)
    menu.add_cascade(label="程序", menu=file_menu)
    file_menu.add_command(label="关于", command=about)
    file_menu.add_command(label="退出", command=exit_)
    
    # 创建标题
    title = tk.Label(root, text=f"Sleepy Settings {VERSION}", font=("Arial", 20))

    title.pack(pady=20)
    
    # 创建日志窗口(整个窗口)
    log_frame = tk.Frame(root)
    log_frame.pack(fill=tk.BOTH, expand=True)
    
    # 创建日志文本框
    # Create log_text as before
    log_text = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 12))
    log_text.pack(fill=tk.BOTH, expand=True)
    
    # 创建日志滚动条
    log_scroll = tk.Scrollbar(log_frame, command=log_text.yview)
    log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.config(yscrollcommand=log_scroll.set)
    
    # 初始化日志
    log_message("INFO", f'''
    Welcome to Sleepy Windows Settings
    owner: CR400AFC2214, wyf9
    email: tianyu@siiway.top
    website: https://siiway.top 
    contact us: https://siiway.top/about/contact.html
    version: {VERSION}
    Please first edit your device id, show name, your server url and secret in win_device.py and run win_device.py
    Then you can use this settings to set your status.
    ''')


    # 进入主循环
    root.mainloop()


def better_json(json_data):
    return "\n" + json.dumps(json_data, indent=4, ensure_ascii=False)


def log_message(level, message):
    """统一的日志记录函数"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, log_entry)
    log_text.config(state=tk.DISABLED)
    log_text.see(tk.END)
def private_mode(mode = None):
    """隐私模式请求"""
    if mode == None:
        mode = messagebox.askyesno("隐私模式", "是否开启隐私模式？")
    headers = {"Authorization": f"Bearer {SECRET}"}
    params = {"isprivate": mode}
    response = requests.get(f"{SERVER}/api/device/private", headers=headers, params=params)
    if response.status_code == 200:
        log_message("INFO", "隐私模式设置成功")
        return {"success": True}
    else:
        error_msg = f"主人好好反省一下自己干了什么喵：{response.status_code}"
        log_message("ERROR", error_msg)
        return {"success": False}
    
    
    
def clear_devices():
    """清除所有设备"""
    # 发送清除请求
    headers = {"Authorization": f"Bearer {SECRET}"}
    response = requests.get(f"{SERVER}/api/device/clear", headers=headers)
    
    if response.status_code == 200:
        log_message("INFO", "清除所有设备成功")
        return {"success": True}
    else:
        error_msg = f"主人好好反省一下自己干了什么喵：{response.status_code}"
        log_message("ERROR", error_msg)
        return {"success": False, "error": error_msg}



    
def delete_device(device_id = None):
    """删除设备"""
    if device_id is None:
        device_id = simpledialog.askstring("输入设备ID", "请输入设备ID")
        if not device_id:
            messagebox.showerror("错误", "设备ID不能为空")
            return
    # 发送删除请求
    headers = {"Authorization": f"Bearer {SECRET}"}
    params = {"id": f"{device_id}"}
    response = requests.get(f"{SERVER}/api/device/remove", headers=headers, params=params)
    
    if response.status_code == 200:
        log_message("INFO", f"删除设备成功: {device_id}")
        return {"success": True, "device_id": device_id}
    else:
        error_msg = f"主人好好反省一下自己干了什么喵：{response.status_code}"
        log_message("ERROR", error_msg)
        return {"success": False, "error": error_msg}

def set_status(status_code = None):
    """设置状态"""
    # 获取状态列表
    status_list_response = get_status_list()
    if isinstance(status_list_response, dict) and "主人好好反省一下自己干了什么喵" in status_list_response:
        return

    # 获取状态码并确保是整数
    if status_code is None:
        try:
            raw_status = simpledialog.askinteger("输入状态码", "请输入状态码（数字）")
            if not raw_status:
                raise ValueError
            status_code = int()
        except (ValueError, TypeError):
            messagebox.showerror("错误", "请输入有效的状态码（数字）")
            return

    # 使用 GET 方法带参数
    headers = {"Authorization": f"Bearer {SECRET}"}
    params = {"status": status_code}
    response = requests.get(f"{SERVER}/api/status/set", headers=headers, params=params)

    if response.status_code == 200:
        log_message("INFO", f"设置状态成功: {better_json(response.json())}")
        return response.json()
    else:
        error_msg = f"主人好好反省一下自己干了什么喵：{response.status_code}"
        log_message("ERROR", error_msg)
        return {"主人好好反省一下自己干了什么喵": error_msg}


def get_status_list():
    """获取可用状态列表"""
    response = requests.get(f"{SERVER}/api/status/list")
    
    if response.status_code == 200:
        log_message("INFO", f"获取可用状态列表成功: {better_json(response.json())}")
        return better_json(response.json())
    else:
        error_msg = f"主人好好反省一下自己干了什么喵：{response.status_code}"
        log_message("ERROR", error_msg)
        return {"主人好好反省一下自己干了什么喵": error_msg}


def get_metrics():
    """获取统计信息"""
    response = requests.get(f"{SERVER}/api/metrics")
    
    if response.status_code == 200:
        log_message("INFO", f"获取统计信息成功: {better_json(response.json())}")
        return better_json(response.json())
    else:
        error_msg = f"主人好好反省一下自己干了什么喵：{response.status_code}"
        log_message("ERROR", error_msg)
        return {"主人好好反省一下自己干了什么喵": error_msg}


def get_meta():
    """获取元数据"""
    response = requests.get(f"{SERVER}/api/meta")

    if response.status_code == 200:
        log_message("INFO", f"获取元数据成功: {better_json(response.json())}")
        return response.json()
    else:
        error_msg = f"主人好好反省一下自己干了什么喵：{response.status_code}"
        log_message("ERROR", error_msg)
        return {"主人好好反省一下自己干了什么喵": error_msg}


def get_status(meta=False, metrics=False):
    """获取状态"""
    params = {"meta": meta, "metrics": metrics}
    response = requests.get(f"{SERVER}/api/status/query", params=params)
    
    if response.status_code == 200:
        log_message("INFO", f"获取状态成功: {better_json(response.json())}")
        return response.json()
    else:
        error_msg = f"主人好好反省一下自己干了什么喵：{response.status_code}"
        log_message("ERROR", error_msg)
        return {"主人好好反省一下自己干了什么喵": error_msg}


def send_status(using = None, status = None, device_id = None, show_name = None):

    """发送状态"""

    
    if using == None:
        using = messagebox.askyesno("是否正在使用？")
    if status == None:
        status = simpledialog.askstring("输入应用", "请输入应用名称")
    if device_id == None:
        device_id = simpledialog.askstring("输入设备ID", "请输入设备ID")
    # if show_name == None:
    #     show_name = simpledialog.askstring("输入显示名称", "请输入显示名称")
    # 因为我不确定用户会不会在这里创建设备，但是w9说
    # wyf9: 08-29 14:16:59
    # 第一次创建必须带 show_name
    # wyf9: 08-29 14:17:10
    # 第二次就只需要带更改的数据了
    # 所以为了节省用户时间我就不添加showname输入了
    # qwq
    if show_name == None:
        data = {
        "id": device_id,
        "using": using,
        "status": status
    }
    else:
        data = {
        "id": device_id,
        "show_name": show_name,
        "using": using,
        "status": status
    }
    
    headers = {"Authorization": f"Bearer {SECRET}"}
    response = requests.post(f"{SERVER}/api/device/set", json=data, headers=headers)
    
    if response.status_code == 200:
        log_message("INFO", f"发送状态成功: using={using}, status={status}")
        return response.json()
    else:
        error_msg = f"主人好好反省一下自己干了什么喵：{response.status_code}"
        log_message("ERROR", error_msg)
        return {"主人好好反省一下自己干了什么喵": error_msg}


def about():
    """显示关于窗口"""
    messagebox.showinfo(
        "关于", 
        "Sleepy Windows Settings\n作者：CR400AFC2214\n邮箱：tianyu@siiway.top"
    )


def exit_():
    """退出程序"""
    if messagebox.askokcancel("退出", "主人确定要退出喵？"):
        if messagebox.askokcancel("退出", "主人退出时是否设置状态为离线喵？"):
            # 发送请求
            send_status(using=False, status="未在使用", device_id=DEVICE_ID, show_name=DEVICE_SHOW_NAME)

            exit()
        else:
            exit()


def shutdown():
    """注销时调用"""
    send_status(using=False, status="未在使用", device_id=DEVICE_ID, show_name=DEVICE_SHOW_NAME)


if __name__ == "__main__":
    # 鉴权
    if simpledialog.askstring("输入密钥", "请输入密钥") != SECRET:
        error_msg = "主人好好反省一下自己干了什么喵：密钥错误"
        messagebox.showerror("错误", error_msg)
        exit()
    
    main()
