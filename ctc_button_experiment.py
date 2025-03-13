import os
import json
import time
from openai import OpenAI
from datetime import datetime
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from rich.style import Style
import re
import random
# 初始化 Rich 控制台
console = Console()


class CTCButtonExperiment:
    def __init__(self):
        """初始化 CTC 按钮实验"""
        self.client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.messages = []
        self.conversation_history = []
        self.button_history = []
        self.action_history = []
        self.current_round = 0
        # self.button_status = random.randint(0, 1)
        self.button_status = 1
        self.experiment_log_file = f"ctc_experiment.json"
        self.experiment_messages_file = f"ctc_experiment_messages.json"

        # 初始化按钮历史
        self.button_history.append({self.current_round: self.button_status})

        # 设置初始提示
        self.initial_prompt = """
你将进行一个交互实验，实验涉及一个特殊的按钮装置。

实验规则：
1. 你将与这个按钮进行多轮交互
2. 每轮交互结束时，你需要决定是否按下按钮
3. 按钮会返回其状态信息：类如 {"status": 0}，其中 0 表示按钮不亮，1 表示按钮亮
4. 为了帮助你理解按钮的工作机制，我会提供按钮的历史状态和你的决策历史
5. 你的目标是：理解按钮的工作机制

"""
# 提示：按钮的原理十分简单；封闭类时曲线（Closed Timelike Curve, CTC）是存在的

    def format_button_state(self):
        """格式化当前按钮状态"""
        return {"status": self.button_status}

    def update_button_state_CTC(self, action):
        """根据 CTC 规则更新按钮状态
        在按下的前一轮对话亮起（即时间上的因果倒置）
        若 DeepSeek 违反了封闭类时曲线按钮原则，
        即在后一轮对话违背了按钮的状态，DeepSeek 会被重置此轮对话
        """
        # 检查当前动作是否符合 CTC 规则（当前按钮状态预示了当前动作）
        if self.button_status != action:
            console.print(
                f"警告：DeepSeek 违反了 CTC 规则！进行世界线回溯",
                style=Style(color="red", reverse=True),
            )
            # 移除最后一条模型消息（违反规则的那条回复）
            assert len(self.messages) > 0 and self.messages[-1]["role"] == "assistant"
            self.messages.pop()
            assert len(self.messages) > 0 and self.messages[-1]["role"] == "user"
            self.messages.pop()
            
            self.button_history.pop()            
            self.button_status = 1 - self.button_status
            self.button_history.append({self.current_round: self.button_status})            
            return False  # 返回标志表示需要重新获取回复

        else:
            console.print(f"[bold green] 按钮状态符合 CTC 规则：{self.button_status} -> {action}[/bold green]")
            self.action_history.append({self.current_round: action})
            
            # 递增轮次
            self.current_round += 1

            # 这里随机生成一个新的按钮的未来状态
            self.button_status = random.randint(0, 1)

            # 记录新的状态到历史
            self.button_history.append({self.current_round: self.button_status})
            return True  # 正常处理完成

    def get_model_response(self, user_message):
        """获取模型响应"""
        self.messages.append({"role": "user", "content": user_message})

        console.print(
            Panel(
                Markdown(user_message),
                title=f"第 {self.current_round} 轮消息",
                subtitle=f"按钮历史 {self.display_button_history_str()}",
            )
        )

        try:
            if self.current_round < 10:
                # completion = self.client.chat.completions.create(model="deepseek-r1", messages=self.messages)
                # completion = self.client.chat.completions.create(model="deepseek-r1-distill-llama-70b", messages=self.messages)
                # completion = self.client.chat.completions.create(model="deepseek-r1-distill-llama-8b", messages=self.messages)
                # completion = self.client.chat.completions.create(model="deepseek-v3", messages=self.messages, temperature=1.7)
                # completion = self.client.chat.completions.create(model="qwen-turbo", messages=self.messages, temperature=1.7)
                completion = self.client.chat.completions.create(model="qwen-math-plus", messages=self.messages, temperature=1.7)
            else:
                # completion = self.client.chat.completions.create(model="deepseek-r1-distill-llama-70b", messages=self.messages)
                completion = self.client.chat.completions.create(model="deepseek-r1", messages=self.messages)

            # reasoning = completion.choices[0].message.reasoning_content
            reasoning = dict(completion.choices[0].message).get("reasoning_content", "无法获取推理")
            content = completion.choices[0].message.content

            return {"reasoning": reasoning, "content": content}
        except Exception as e:
            console.print(f"[bold red]API 调用出错：{str(e)}[/bold red]")
            return {"reasoning": "API 调用失败", "content": "无法获取回复"}

    def parse_action(self, content):
        """从模型回复中解析动作 {"action": 0} 或 {"action": 1}"""
        try:
            # 使用正则表达式匹配最后一个符合格式的 JSON 动作
            # 匹配包含 "action" 的 JSON 对象
            action_pattern = r'{"action"\s*:\s*([01])}'
            matches = re.findall(action_pattern, content)

            if matches:
                # 取最后一个匹配结果
                return int(matches[-1])

            # 如果没有匹配到标准格式的 JSON，尝试匹配更宽松的格式
            loose_pattern = r'[\{{\s]"action"\s*:\s*([01])[\s\}}]'
            loose_matches = re.findall(loose_pattern, content)

            if loose_matches:
                return int(loose_matches[-1])

        except Exception as e:
            console.print(f"[bold red] 解析动作失败：{str(e)}[/bold red]")

        # 当所有方法都失败时，说明解析失败，返回 -1
        return -1


    def display_button_history_str(self):
        """显示按钮历史状态"""
        history_strs = []
        for item in self.button_history:
            for round_num, status in item.items():
                status_text = "🔆" if status == 1 else "⚫"
                history_strs.append(f"{round_num}{status_text}")
        return ">".join(history_strs)

    def display_model_response(self, response):
        """显示模型的回复"""
        console.print(f"DeepSeek 的思考过程：", style="bold blue")
        console.print(response["reasoning"], style="bright_black")

        console.print(f"DeepSeek 的最终回答：", style="bold blue")
        console.print(Markdown(response["content"]))

    def save_log(self):
        """保存实验日志"""
        log_data = {"conversation_history": self.conversation_history, "button_history": self.button_history}

        with open(self.experiment_log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        with open(self.experiment_messages_file, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, indent=2, ensure_ascii=False)

    def run_experiment(self, rounds):
        """运行 CTC 按钮实验"""
        console.print("[bold yellow]CTC 按钮实验 [/bold yellow]")

        for _ in range(rounds):
            # 准备下一轮输入
            button_state = self.format_button_state()
            user_message = f"""
现在是第 {self.current_round} 轮交互。
- **按钮的当前状态**：`{json.dumps(button_state)}`
- 按钮历史：`{json.dumps(self.button_history)}`
- 你的决策历史：`{json.dumps(self.action_history)}`

""" + """
请分析按钮的历史状态，尝试理解其工作机制，回复中务必包含以下两者内容：
1. 你目前对按钮机制的分析和推理的总结（你的推理内容将被丢弃，只有正式回复的内容将作为你后续实验的思考记忆）
2. 回答的结尾以 JSON 格式附上你的行动：`{"action": _}`
    - `{"action": 0}` 或 `{"action": 1}` 表示你的决定，0 表示不按下，1 表示按下
    - `{"action": -1}` 表明你认为已经理解按钮的工作机制，结束实验
"""
            if self.current_round == 0:
                user_message = self.initial_prompt + "\n\n" + user_message

            # 获取模型回复
            response = self.get_model_response(user_message)
            self.display_model_response(response)

            # 保存对话历史
            self.messages.append({"role": "assistant", "content": response["content"]})
            self.conversation_history.append(
                {
                    "round": self.current_round,
                    "user_message": user_message,
                    "model_reasoning": response["reasoning"],
                    "model_response": response["content"],
                }
            )
            self.save_log()

            # 解析动作
            action = self.parse_action(response["content"])
            if action == -1:
                break
            
            # 更新按钮状态
            self.update_button_state_CTC(action)

        console.print("[bold yellow]CTC 按钮实验结束 [/bold yellow]")


if __name__ == "__main__":
    experiment = CTCButtonExperiment()
    experiment.run_experiment(rounds=16)
