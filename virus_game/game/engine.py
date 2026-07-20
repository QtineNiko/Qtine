from game.config import *
from game.virus import Virus
from game.events import EventManager
from game.ui import UIManager
from game.save_system import SaveSystem

import pygame
import random
import sys
import os


class GameEngine:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("VIRUS PET - 病毒宠物")
        
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_path = self._get_font()
        
        self.virus = None
        self.event_manager = EventManager(self)
        self.ui = UIManager(self)
        self.save_system = SaveSystem()
        
        self.game_state = "menu"
        self.tick_timer = 0
        self.day_count = 1
        self.action_log = []
        self.max_log_entries = 20
        
        self.running = True
        
    def _get_font(self):
        font_paths = [
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/cour.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                return path
        return None
    
    def new_game(self, name=None):
        if name is None:
            name = random.choice(VIRUS_NAMES)
        self.virus = Virus(name)
        self.day_count = 1
        self.action_log = []
        self.add_log(f"[SYSTEM] 病毒 {self.virus.name} 已创建")
        self.add_log(f"[SYSTEM] 性格: {self.virus.personality}")
        self.game_state = "playing"
    
    def load_game(self):
        data = self.save_system.load()
        if data:
            self.virus = Virus.from_dict(data["virus"])
            self.day_count = data.get("day_count", 1)
            self.action_log = data.get("action_log", [])
            self.add_log("[SYSTEM] 存档已加载")
            self.game_state = "playing"
            return True
        return False
    
    def save_game(self):
        if self.virus:
            data = {
                "virus": self.virus.to_dict(),
                "day_count": self.day_count,
                "action_log": self.action_log
            }
            self.save_system.save(data)
            self.add_log("[SYSTEM] 游戏已保存")
    
    def add_log(self, message):
        self.action_log.insert(0, message)
        if len(self.action_log) > self.max_log_entries:
            self.action_log.pop()
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if event.type == pygame.KEYDOWN:
                self.handle_key_press(event.key)
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_mouse_click(event.pos)
    
    def handle_key_press(self, key):
        if self.game_state == "menu":
            if key == pygame.K_1:
                self.new_game()
            elif key == pygame.K_2:
                self.load_game()
            elif key == pygame.K_ESCAPE:
                self.running = False
        
        elif self.game_state == "playing":
            if key == pygame.K_1:
                self.action_feed()
            elif key == pygame.K_2:
                self.action_train()
            elif key == pygame.K_3:
                self.action_play()
            elif key == pygame.K_4:
                self.action_upgrade()
            elif key == pygame.K_s:
                self.save_game()
            elif key == pygame.K_ESCAPE:
                self.game_state = "menu"
    
    def handle_mouse_click(self, pos):
        if self.game_state == "playing":
            self.ui.handle_click(pos)
    
    def action_feed(self):
        if self.virus.energy >= MAX_ENERGY - 5:
            self.add_log(f"[{self.virus.name}] 我不饿...")
            return
        self.virus.feed()
        self.add_log(f"[PLAYER] 你给 {self.virus.name} 喂食了")
        if random.random() < 0.3:
            self.virus.gain_exp(5)
            self.add_log(f"[{self.virus.name}] 好吃~ (+5 EXP)")
    
    def action_train(self):
        if self.virus.energy < TRAIN_ENERGY_COST:
            self.add_log(f"[{self.virus.name}] 太累了，不想训练...")
            return
        self.virus.train()
        self.add_log(f"[PLAYER] 你训练了 {self.virus.name}")
        if random.random() < 0.4:
            self.add_log(f"[{self.virus.name}] 我变强了！")
    
    def action_play(self):
        if self.virus.energy < PLAY_ENERGY_COST:
            self.add_log(f"[{self.virus.name}] 没力气玩了...")
            return
        self.virus.play()
        self.add_log(f"[PLAYER] 你和 {self.virus.name} 玩耍")
        if random.random() < 0.5:
            self.add_log(f"[{self.virus.name}] 嘿嘿嘿~真开心！")
    
    def action_upgrade(self):
        if self.virus.skill_points <= 0:
            self.add_log("[SYSTEM] 没有可用的技能点")
            return
        self.virus.upgrade_random()
        self.add_log(f"[{self.virus.name}] 我进化了！")
    
    def update(self, dt):
        if self.game_state != "playing" or not self.virus:
            return
        
        self.tick_timer += dt
        if self.tick_timer >= TICK_INTERVAL:
            self.tick_timer = 0
            self.game_tick()
        
        self.event_manager.update(dt)
        self.virus.update(dt)
    
    def game_tick(self):
        self.virus.energy = max(0, self.virus.energy - ENERGY_DECAY)
        self.virus.hunger = min(MAX_HUNGER, self.virus.hunger + HUNGER_INCREASE)
        self.virus.happiness = max(0, self.virus.happiness - HAPPINESS_DECAY)
        
        if self.virus.hunger >= 80:
            damage = (self.virus.hunger - 70) // 10
            self.virus.hp = max(0, self.virus.hp - damage)
            if damage > 0:
                self.add_log(f"[{self.virus.name}] 好饿...生命值 -{damage}")
        
        if self.virus.happiness <= 20:
            if random.random() < 0.3:
                self.virus.autonomous_action()
                self.add_log(f"[{self.virus.name}] 无聊...我自己找点事做")
        
        if self.virus.hp <= 0:
            self.add_log(f"[SYSTEM] {self.virus.name} 已经消亡了...")
            self.game_state = "gameover"
        
        if random.random() < 0.15:
            self.event_manager.trigger_random_event()
        
        self.day_count += 0.1
        
        if random.random() < 0.2:
            self.virus.ai_action(self)
    
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            self.handle_events()
            self.update(dt)
            self.ui.draw(self.screen)
            pygame.display.flip()
        
        pygame.quit()
        sys.exit()
