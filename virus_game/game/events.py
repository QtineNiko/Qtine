from game.config import *
import random


class EventManager:
    def __init__(self, engine):
        self.engine = engine
        self.active_events = []
        self.event_cooldown = 0
        
        self.event_pool = [
            {
                "id": "antivirus_scan",
                "name": "杀毒软件扫描",
                "description": "系统正在进行全盘扫描...",
                "probability": 0.15,
                "effect": self._event_antivirus_scan,
                "type": "negative"
            },
            {
                "id": "system_update",
                "name": "系统更新",
                "description": "系统正在安装更新...",
                "probability": 0.1,
                "effect": self._event_system_update,
                "type": "negative"
            },
            {
                "id": "new_vulnerability",
                "name": "发现新漏洞",
                "description": "发现了一个系统漏洞！",
                "probability": 0.12,
                "effect": self._event_new_vulnerability,
                "type": "positive"
            },
            {
                "id": "user_afk",
                "name": "用户离开",
                "description": "用户暂时离开了电脑...",
                "probability": 0.2,
                "effect": self._event_user_afk,
                "type": "positive"
            },
            {
                "id": "file_download",
                "name": "文件下载",
                "description": "用户下载了一个可疑文件",
                "probability": 0.15,
                "effect": self._event_file_download,
                "type": "positive"
            },
            {
                "id": "system_error",
                "name": "系统错误",
                "description": "系统发生了未知错误！",
                "probability": 0.1,
                "effect": self._event_system_error,
                "type": "neutral"
            },
            {
                "id": "usb_inserted",
                "name": "USB设备插入",
                "description": "检测到新的USB设备...",
                "probability": 0.08,
                "effect": self._event_usb_inserted,
                "type": "positive"
            },
            {
                "id": "firewall_alert",
                "name": "防火墙警报",
                "description": "防火墙检测到异常流量！",
                "probability": 0.12,
                "effect": self._event_firewall_alert,
                "type": "negative"
            },
        ]
    
    def trigger_random_event(self):
        if self.event_cooldown > 0:
            return
        
        available_events = [e for e in self.event_pool if random.random() < e["probability"]]
        if available_events:
            event = random.choice(available_events)
            self.trigger_event(event)
    
    def trigger_event(self, event):
        self.engine.add_log(f"[EVENT] {event['name']}: {event['description']}")
        result = event["effect"]()
        if result:
            self.engine.add_log(f"[EVENT] {result}")
        self.event_cooldown = 3
    
    def update(self, dt):
        if self.event_cooldown > 0:
            self.event_cooldown -= dt / 1000
    
    def _event_antivirus_scan(self):
        virus = self.engine.virus
        damage = max(5, 20 - virus.stealth)
        virus.hp = max(0, virus.hp - damage)
        if virus.stealth > 10 and random.random() < 0.5:
            return f"病毒成功隐藏！仅受到 {damage} 点伤害"
        return f"病毒受到 {damage} 点伤害！"
    
    def _event_system_update(self):
        virus = self.engine.virus
        if virus.intelligence > 8 and random.random() < 0.6:
            virus.gain_exp(20)
            return f"病毒适应了新系统！+20 EXP"
        virus.hp = max(0, virus.hp - 15)
        return "系统更新削弱了病毒！-15 HP"
    
    def _event_new_vulnerability(self):
        virus = self.engine.virus
        virus.gain_exp(15)
        virus.coins += 5
        if virus.reproduction > 5:
            virus.infected_files += 2
            return f"利用漏洞传播！+15 EXP, +5 coins, +2 感染文件"
        return f"发现漏洞！+15 EXP, +5 coins"
    
    def _event_user_afk(self):
        virus = self.engine.virus
        if virus.energy > 30:
            actions = 0
            while virus.energy > 20 and actions < 3:
                virus.autonomous_action()
                virus.energy -= 10
                actions += 1
            return f"趁用户不在，病毒进行了 {actions} 个行动"
        return "病毒能量不足，什么也没做"
    
    def _event_file_download(self):
        virus = self.engine.virus
        if virus.stealth > 5:
            virus.infected_files += 3
            virus.gain_exp(10)
            virus.coins += 3
            return f"成功附着在下载文件中！+3 感染, +10 EXP, +3 coins"
        return "病毒未能成功附着"
    
    def _event_system_error(self):
        virus = self.engine.virus
        if random.random() < 0.5:
            virus.hp = min(MAX_HP, virus.hp + 10)
            return "系统错误反而帮助了病毒！+10 HP"
        else:
            virus.hp = max(0, virus.hp - 10)
            return "系统错误意外损伤了病毒！-10 HP"
    
    def _event_usb_inserted(self):
        virus = self.engine.virus
        if virus.reproduction > 4:
            virus.infected_files += 5
            virus.controlled_systems += 1
            virus.gain_exp(25)
            return f"通过USB传播成功！+5 感染, +1 系统, +25 EXP"
        return "传播能力不足，未能通过USB传播"
    
    def _event_firewall_alert(self):
        virus = self.engine.virus
        if virus.stealth > 7:
            return "病毒成功躲避了防火墙追踪！"
        else:
            virus.hp = max(0, virus.hp - 12)
            virus.energy = max(0, virus.energy - 15)
            return f"被防火墙追踪到！-12 HP, -15 能量"
