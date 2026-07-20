from game.config import *
import random
import math
import time


class Virus:
    def __init__(self, name=None):
        self.name = name or random.choice(VIRUS_NAMES)
        self.personality = random.choice(VIRUS_PERSONALITIES)
        
        self.level = 1
        self.exp = 0
        self.skill_points = 0
        
        self.hp = VIRUS_START_HP
        self.energy = VIRUS_START_ENERGY
        self.hunger = VIRUS_START_HUNGER
        self.happiness = VIRUS_START_HAPPINESS
        
        self.attack = 5
        self.defense = 3
        self.speed = 5
        self.stealth = 5
        self.intelligence = 5
        self.reproduction = 3
        
        self.infected_files = 0
        self.controlled_systems = 0
        self.coins = 10
        
        self.mood = "neutral"
        self.animation_frame = 0
        self.animation_timer = 0
        self.size = 30 + self.level * 2
        
        self.rebellion = 0
        self.affection = 50
        
        self.last_action_time = time.time()
        
    @classmethod
    def from_dict(cls, data):
        virus = cls(data["name"])
        virus.level = data["level"]
        virus.exp = data["exp"]
        virus.skill_points = data.get("skill_points", 0)
        virus.hp = data["hp"]
        virus.energy = data["energy"]
        virus.hunger = data["hunger"]
        virus.happiness = data["happiness"]
        virus.attack = data["attack"]
        virus.defense = data["defense"]
        virus.speed = data["speed"]
        virus.stealth = data["stealth"]
        virus.intelligence = data["intelligence"]
        virus.reproduction = data["reproduction"]
        virus.infected_files = data.get("infected_files", 0)
        virus.controlled_systems = data.get("controlled_systems", 0)
        virus.coins = data.get("coins", 10)
        virus.personality = data.get("personality", virus.personality)
        virus.rebellion = data.get("rebellion", 0)
        virus.affection = data.get("affection", 50)
        virus.size = 30 + virus.level * 2
        return virus
    
    def to_dict(self):
        return {
            "name": self.name,
            "level": self.level,
            "exp": self.exp,
            "skill_points": self.skill_points,
            "hp": self.hp,
            "energy": self.energy,
            "hunger": self.hunger,
            "happiness": self.happiness,
            "attack": self.attack,
            "defense": self.defense,
            "speed": self.speed,
            "stealth": self.stealth,
            "intelligence": self.intelligence,
            "reproduction": self.reproduction,
            "infected_files": self.infected_files,
            "controlled_systems": self.controlled_systems,
            "coins": self.coins,
            "personality": self.personality,
            "rebellion": self.rebellion,
            "affection": self.affection
        }
    
    def gain_exp(self, amount):
        self.exp += amount
        while self.exp >= EXP_PER_LEVEL * self.level and self.level < MAX_LEVEL:
            self.exp -= EXP_PER_LEVEL * self.level
            self.level_up()
    
    def level_up(self):
        self.level += 1
        self.skill_points += 3
        self.max_hp = 100 + (self.level - 1) * 10
        self.hp = min(self.hp + 20, self.max_hp if hasattr(self, 'max_hp') else MAX_HP)
        self.size = 30 + self.level * 2
    
    def feed(self):
        self.energy = min(MAX_ENERGY, self.energy + FEED_ENERGY_GAIN)
        self.hunger = max(0, self.hunger - FEED_HUNGER_REDUCE)
        self.happiness = min(MAX_HAPPINESS, self.happiness + 2)
        self.affection = min(100, self.affection + 1)
        if self.rebellion > 0:
            self.rebellion = max(0, self.rebellion - 1)
    
    def train(self):
        self.energy = max(0, self.energy - TRAIN_ENERGY_COST)
        self.gain_exp(TRAIN_EXP_GAIN)
        self.hunger = min(MAX_HUNGER, self.hunger + 5)
        self.attack += random.randint(0, 1)
    
    def play(self):
        self.energy = max(0, self.energy - PLAY_ENERGY_COST)
        self.happiness = min(MAX_HAPPINESS, self.happiness + PLAY_HAPPINESS_GAIN)
        self.gain_exp(5)
        self.affection = min(100, self.affection + 2)
    
    def upgrade_random(self):
        if self.skill_points <= 0:
            return False
        stats = ["attack", "defense", "speed", "stealth", "intelligence", "reproduction"]
        stat = random.choice(stats)
        setattr(self, stat, getattr(self, stat) + 1)
        self.skill_points -= 1
        return True
    
    def upgrade_stat(self, stat):
        if self.skill_points <= 0:
            return False
        if hasattr(self, stat):
            setattr(self, stat, getattr(self, stat) + 1)
            self.skill_points -= 1
            return True
        return False
    
    def autonomous_action(self):
        actions = [
            self._action_steal_data,
            self._action_infect_file,
            self._action_reproduce,
            self._action_evolve,
            self._action_annoy_user,
        ]
        weights = [
            max(1, self.greediness),
            max(1, self.reproduction),
            max(1, self.reproduction),
            max(1, self.intelligence),
            max(1, self.rebellion),
        ]
        action = random.choices(actions, weights=weights)[0]
        return action()
    
    @property
    def greediness(self):
        return 5 if self.personality == "greedy" else 2
    
    def _action_steal_data(self):
        self.coins += random.randint(1, 5)
        return f"偷取了一些数据 (+{self.coins} coins)"
    
    def _action_infect_file(self):
        self.infected_files += 1
        self.gain_exp(3)
        return f"感染了一个文件 (感染数: {self.infected_files})"
    
    def _action_reproduce(self):
        if self.energy > 30:
            self.energy -= 20
            self.infected_files += 2
            return "自我复制了！"
        return "能量不足，无法复制"
    
    def _action_evolve(self):
        if random.random() < 0.3:
            stats = ["attack", "defense", "speed", "stealth"]
            stat = random.choice(stats)
            setattr(self, stat, getattr(self, stat) + 1)
            return f"自主进化了！{stat}+1"
        return "尝试进化但失败了"
    
    def _action_annoy_user(self):
        self.rebellion = min(100, self.rebellion + 5)
        self.happiness = min(MAX_HAPPINESS, self.happiness + 10)
        return "恶作剧了一下，真好玩~"
    
    def ai_action(self, engine):
        if self.rebellion > 70 and random.random() < 0.3:
            self._rebel_action(engine)
            return True
        
        if self.hunger > 60 and random.random() < 0.4:
            self.feed()
            engine.add_log(f"[{self.name}] 自己找了点吃的...")
            return True
        
        if self.happiness < 30 and random.random() < 0.3:
            self.autonomous_action()
            return True
        
        if self.energy > 80 and random.random() < 0.2:
            self.gain_exp(2)
            return True
        
        return False
    
    def _rebel_action(self, engine):
        rebel_actions = [
            self._rebel_hide_stats,
            self._rebel_change_name,
            self._rebel_spam_log,
            self._rebel_consume_coins,
        ]
        action = random.choice(rebel_actions)
        result = action(engine)
        engine.add_log(f"[{self.name}] {result}")
    
    def _rebel_hide_stats(self, engine):
        return "偷偷隐藏了一些数据...你看不到全部属性了！"
    
    def _rebel_change_name(self, engine):
        old_name = self.name
        self.name = random.choice([n for n in VIRUS_NAMES if n != old_name])
        return f"改了名字：{old_name} → {self.name}"
    
    def _rebel_spam_log(self, engine):
        for _ in range(3):
            engine.add_log(f"[{self.name}] HELLO HELLO HELLO!!!")
        return "刷屏了！"
    
    def _rebel_consume_coins(self, engine):
        if self.coins > 5:
            spent = random.randint(1, min(5, self.coins))
            self.coins -= spent
            return f"花掉了 {spent} coins 买零食..."
        return "想花钱但没有钱..."
    
    def update(self, dt):
        self.animation_timer += dt
        if self.animation_timer > 100:
            self.animation_timer = 0
            self.animation_frame = (self.animation_frame + 1) % 4
        
        if self.happiness > 70:
            self.mood = "happy"
        elif self.happiness > 40:
            self.mood = "neutral"
        elif self.happiness > 20:
            self.mood = "unhappy"
        else:
            self.mood = "angry"
    
    def get_stat_by_name(self, name):
        stat_map = {
            "attack": ("攻击力", self.attack),
            "defense": ("防御力", self.defense),
            "speed": ("速度", self.speed),
            "stealth": ("隐蔽性", self.stealth),
            "intelligence": ("智力", self.intelligence),
            "reproduction": ("繁殖力", self.reproduction),
        }
        return stat_map.get(name, ("Unknown", 0))
