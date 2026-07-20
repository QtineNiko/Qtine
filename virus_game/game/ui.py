import pygame
import math
import random
from game.config import *


class UIManager:
    def __init__(self, engine):
        self.engine = engine
        self.font = None
        self.font_small = None
        self.font_large = None
        self._init_fonts()
        
        self.matrix_chars = []
        self._init_matrix()
        
        self.particles = []
        self.glow_pulse = 0
        
        self.selected_panel = None
        self.buttons = []
    
    def _init_fonts(self):
        font_path = self.engine.font_path
        try:
            self.font = pygame.font.Font(font_path, 16) if font_path else pygame.font.SysFont("monospace", 16)
            self.font_small = pygame.font.Font(font_path, 12) if font_path else pygame.font.SysFont("monospace", 12)
            self.font_large = pygame.font.Font(font_path, 28) if font_path else pygame.font.SysFont("monospace", 28)
        except:
            self.font = pygame.font.SysFont("monospace", 16)
            self.font_small = pygame.font.SysFont("monospace", 12)
            self.font_large = pygame.font.SysFont("monospace", 28)
    
    def _init_matrix(self):
        for i in range(60):
            self.matrix_chars.append({
                "x": random.randint(0, SCREEN_WIDTH),
                "y": random.randint(-SCREEN_HEIGHT, 0),
                "speed": random.randint(1, 4),
                "char": random.choice("01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"),
                "length": random.randint(5, 20)
            })
    
    def handle_click(self, pos):
        for btn in self.buttons:
            if btn["rect"].collidepoint(pos):
                btn["action"]()
                return
    
    def draw(self, screen):
        screen.fill(COLOR_BG)
        self._draw_matrix(screen)
        
        if self.engine.game_state == "menu":
            self._draw_menu(screen)
        elif self.engine.game_state == "playing":
            self._draw_game(screen)
        elif self.engine.game_state == "gameover":
            self._draw_gameover(screen)
    
    def _draw_matrix(self, screen):
        for char in self.matrix_chars:
            char["y"] += char["speed"]
            if char["y"] > SCREEN_HEIGHT:
                char["y"] = -20
                char["x"] = random.randint(0, SCREEN_WIDTH)
                char["char"] = random.choice("01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン")
            
            alpha = 80 if char["y"] % 5 < 3 else 40
            surf = self.font_small.render(char["char"], True, COLOR_GREEN_DIM)
            surf.set_alpha(alpha)
            screen.blit(surf, (char["x"], char["y"]))
    
    def _draw_menu(self, screen):
        title = self.font_large.render("VIRUS PET", True, COLOR_GREEN)
        subtitle = self.font.render("=== 病毒宠物 ===", True, COLOR_GREEN_DARK)
        
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 120))
        screen.blit(subtitle, (SCREEN_WIDTH//2 - subtitle.get_width()//2, 180))
        
        menu_items = [
            "[1] 新游戏  -  NEW GAME",
            "[2] 继续游戏 - LOAD GAME" if self.engine.save_system.has_save() else "[2] 继续游戏 (无存档)",
            "[ESC] 退出   -  EXIT"
        ]
        
        for i, item in enumerate(menu_items):
            text = self.font.render(item, True, COLOR_GREEN if i < 2 else COLOR_GREEN_DIM)
            screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, 300 + i * 50))
        
        hint = self.font_small.render("按对应数字键开始", True, COLOR_GREEN_DIM)
        screen.blit(hint, (SCREEN_WIDTH//2 - hint.get_width()//2, 500))
    
    def _draw_game(self, screen):
        self.glow_pulse = (self.glow_pulse + 0.05) % (2 * math.pi)
        self._draw_virus_area(screen)
        self._draw_stats_panel(screen)
        self._draw_action_log(screen)
        self._draw_action_buttons(screen)
        self._draw_particles(screen)
        self._update_particles()
    
    def _draw_virus_area(self, screen):
        area_rect = pygame.Rect(220, 20, 440, 350)
        pygame.draw.rect(screen, COLOR_GREEN_DIM, area_rect, 1)
        
        title = self.font_small.render("[[ SYSTEM MEMORY ]]", True, COLOR_GREEN_DARK)
        screen.blit(title, (area_rect.x + 10, area_rect.y + 5))
        
        virus = self.engine.virus
        center_x = area_rect.centerx
        center_y = area_rect.centery + 20
        size = virus.size
        
        glow_intensity = 0.3 + 0.2 * math.sin(self.glow_pulse)
        for i in range(5, 0, -1):
            glow_size = size + i * 8
            glow_surf = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
            alpha = int(30 * glow_intensity * (6 - i) / 5)
            pygame.draw.circle(glow_surf, (*COLOR_GREEN, alpha), (glow_size, glow_size), glow_size)
            screen.blit(glow_surf, (center_x - glow_size, center_y - glow_size))
        
        body_color = self._get_virus_color()
        for i in range(8):
            angle = (i / 8) * 2 * math.pi + self.glow_pulse * 0.5
            tentacle_len = size * 0.6
            end_x = center_x + math.cos(angle) * (size + tentacle_len)
            end_y = center_y + math.sin(angle) * (size + tentacle_len)
            mid_x = center_x + math.cos(angle) * size * 0.8
            mid_y = center_y + math.sin(angle) * size * 0.8
            pygame.draw.line(screen, body_color, (mid_x, mid_y), (end_x, end_y), 3)
            pygame.draw.circle(screen, body_color, (int(end_x), int(end_y)), 4)
        
        pygame.draw.circle(screen, body_color, (center_x, center_y), size)
        pygame.draw.circle(screen, COLOR_BG, (center_x, center_y), int(size * 0.6))
        pygame.draw.circle(screen, body_color, (center_x, center_y), int(size * 0.3))
        
        eye_offset_x = size * 0.25
        eye_y = center_y - size * 0.1
        eye_size = size * 0.15
        pygame.draw.circle(screen, body_color, (int(center_x - eye_offset_x), int(eye_y)), int(eye_size))
        pygame.draw.circle(screen, body_color, (int(center_x + eye_offset_x), int(eye_y)), int(eye_size))
        
        name_text = self.font.render(f"{virus.name}  Lv.{virus.level}", True, COLOR_GREEN)
        screen.blit(name_text, (center_x - name_text.get_width()//2, area_rect.y + 30))
        
        mood_text = self.font_small.render(f"心情: {virus.mood}", True, COLOR_GREEN_DARK)
        screen.blit(mood_text, (center_x - mood_text.get_width()//2, area_rect.y + 55))
        
        exp_percent = virus.exp / (EXP_PER_LEVEL * virus.level) if virus.level < MAX_LEVEL else 1
        exp_bar_rect = pygame.Rect(area_rect.x + 20, area_rect.bottom - 30, area_rect.width - 40, 10)
        pygame.draw.rect(screen, COLOR_GREEN_DIM, exp_bar_rect, 1)
        fill_width = int(exp_bar_rect.width * exp_percent)
        if fill_width > 0:
            fill_rect = pygame.Rect(exp_bar_rect.x, exp_bar_rect.y, fill_width, exp_bar_rect.height)
            pygame.draw.rect(screen, COLOR_GREEN, fill_rect)
        
        exp_text = self.font_small.render(f"EXP: {virus.exp}/{EXP_PER_LEVEL * virus.level}", True, COLOR_GREEN_DARK)
        screen.blit(exp_text, (exp_bar_rect.x, exp_bar_rect.y - 15))
    
    def _get_virus_color(self):
        virus = self.engine.virus
        if virus.hp < 30:
            return COLOR_RED
        elif virus.happiness < 30:
            return (255, 150, 0)
        elif virus.mood == "happy":
            return COLOR_CYAN
        else:
            return COLOR_GREEN
    
    def _draw_stats_panel(self, screen):
        panel_rect = pygame.Rect(20, 20, 190, 430)
        pygame.draw.rect(screen, COLOR_GREEN_DIM, panel_rect, 1)
        
        title = self.font_small.render("[[ STATUS ]]", True, COLOR_GREEN)
        screen.blit(title, (panel_rect.x + 10, panel_rect.y + 8))
        
        virus = self.engine.virus
        y = panel_rect.y + 35
        
        stats = [
            ("HP", virus.hp, MAX_HP, COLOR_RED),
            ("能量", virus.energy, MAX_ENERGY, COLOR_YELLOW),
            ("饥饿", virus.hunger, MAX_HUNGER, (255, 150, 0)),
            ("心情", virus.happiness, MAX_HAPPINESS, COLOR_CYAN),
        ]
        
        for name, value, max_val, color in stats:
            label = self.font_small.render(f"{name}: {int(value)}/{max_val}", True, COLOR_GREEN_DARK)
            screen.blit(label, (panel_rect.x + 10, y))
            
            bar_rect = pygame.Rect(panel_rect.x + 10, y + 15, 170, 8)
            pygame.draw.rect(screen, COLOR_GREEN_DIM, bar_rect, 1)
            fill_width = int(170 * max(0, min(1, value / max_val)))
            if fill_width > 0:
                fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, fill_width, bar_rect.height)
                pygame.draw.rect(screen, color, fill_rect)
            
            y += 35
        
        y += 10
        sep_text = self.font_small.render("-" * 25, True, COLOR_GREEN_DIM)
        screen.blit(sep_text, (panel_rect.x + 5, y))
        y += 20
        
        attr_stats = [
            ("攻击力", virus.attack),
            ("防御力", virus.defense),
            ("速度", virus.speed),
            ("隐蔽性", virus.stealth),
            ("智力", virus.intelligence),
            ("繁殖力", virus.reproduction),
        ]
        
        for name, value in attr_stats:
            text = self.font_small.render(f"{name}: {value}", True, COLOR_GREEN)
            screen.blit(text, (panel_rect.x + 10, y))
            y += 20
        
        y += 10
        sep_text2 = self.font_small.render("-" * 25, True, COLOR_GREEN_DIM)
        screen.blit(sep_text2, (panel_rect.x + 5, y))
        y += 20
        
        screen.blit(self.font_small.render(f"技能点: {virus.skill_points}", True, COLOR_YELLOW), (panel_rect.x + 10, y))
        y += 20
        screen.blit(self.font_small.render(f"感染文件: {virus.infected_files}", True, COLOR_GREEN), (panel_rect.x + 10, y))
        y += 20
        screen.blit(self.font_small.render(f"控制系统: {virus.controlled_systems}", True, COLOR_GREEN), (panel_rect.x + 10, y))
        y += 20
        screen.blit(self.font_small.render(f"金币: {virus.coins}", True, COLOR_YELLOW), (panel_rect.x + 10, y))
        y += 20
        screen.blit(self.font_small.render(f"反叛值: {int(virus.rebellion)}%", True, COLOR_RED if virus.rebellion > 50 else COLOR_GREEN_DARK), (panel_rect.x + 10, y))
        y += 20
        screen.blit(self.font_small.render(f"好感度: {int(virus.affection)}%", True, COLOR_CYAN), (panel_rect.x + 10, y))
    
    def _draw_action_log(self, screen):
        panel_rect = pygame.Rect(670, 20, 210, 430)
        pygame.draw.rect(screen, COLOR_GREEN_DIM, panel_rect, 1)
        
        title = self.font_small.render("[[ SYSTEM LOG ]]", True, COLOR_GREEN)
        screen.blit(title, (panel_rect.x + 10, panel_rect.y + 8))
        
        y = panel_rect.y + 35
        for i, log in enumerate(self.engine.action_log[:18]):
            if y > panel_rect.bottom - 20:
                break
            color = COLOR_GREEN_DARK if i > 5 else COLOR_GREEN
            text = self.font_small.render(log[:30], True, color)
            screen.blit(text, (panel_rect.x + 8, y))
            y += 20
    
    def _draw_action_buttons(self, screen):
        panel_rect = pygame.Rect(20, 470, SCREEN_WIDTH - 40, 110)
        pygame.draw.rect(screen, COLOR_GREEN_DIM, panel_rect, 1)
        
        title = self.font_small.render("[[ ACTIONS ]]", True, COLOR_GREEN)
        screen.blit(title, (panel_rect.x + 10, panel_rect.y + 8))
        
        self.buttons = []
        actions = [
            ("[1] 喂食", "FEED", self.engine.action_feed, COLOR_GREEN),
            ("[2] 训练", "TRAIN", self.engine.action_train, COLOR_YELLOW),
            ("[3] 玩耍", "PLAY", self.engine.action_play, COLOR_CYAN),
            ("[4] 升级", "UPGRADE", (255, 0, 255)),
            ("[S] 保存", "SAVE", self.engine.save_game, COLOR_GREEN_DARK),
        ]
        
        btn_width = 150
        btn_height = 45
        start_x = panel_rect.x + (panel_rect.width - btn_width * len(actions)) // 2
        
        for i, (label, key, action, color) in enumerate(actions):
            btn_rect = pygame.Rect(start_x + i * btn_width, panel_rect.y + 40, btn_width - 10, btn_height)
            pygame.draw.rect(screen, color, btn_rect, 2)
            
            text = self.font.render(label, True, color)
            screen.blit(text, (btn_rect.centerx - text.get_width()//2, btn_rect.centery - text.get_height()//2))
            
            self.buttons.append({"rect": btn_rect, "action": action})
        
        day_text = self.font_small.render(f"DAY {int(self.engine.day_count)}", True, COLOR_GREEN_DARK)
        screen.blit(day_text, (panel_rect.right - day_text.get_width() - 15, panel_rect.y + 8))
    
    def _draw_gameover(self, screen):
        title = self.font_large.render("SYSTEM FAILURE", True, COLOR_RED)
        subtitle = self.font.render("病毒已被清除...", True, COLOR_RED)
        
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 200))
        screen.blit(subtitle, (SCREEN_WIDTH//2 - subtitle.get_width()//2, 260))
        
        virus = self.engine.virus
        stats = [
            f"最终等级: Lv.{virus.level}",
            f"感染文件: {virus.infected_files}",
            f"控制系统: {virus.controlled_systems}",
            f"存活天数: {int(self.engine.day_count)}",
        ]
        
        for i, stat in enumerate(stats):
            text = self.font.render(stat, True, COLOR_GREEN_DARK)
            screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, 330 + i * 35))
        
        hint = self.font_small.render("按 ESC 返回主菜单", True, COLOR_GREEN_DARK)
        screen.blit(hint, (SCREEN_WIDTH//2 - hint.get_width()//2, 520))
    
    def _update_particles(self):
        for p in self.particles[:]:
            p["life"] -= 1
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.1
            if p["life"] <= 0:
                self.particles.remove(p)
    
    def _draw_particles(self, screen):
        for p in self.particles:
            alpha = int(255 * (p["life"] / p["max_life"]))
            color = (*p["color"][:3], alpha)
            surf = pygame.Surface((p["size"] * 2, p["size"] * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (p["size"], p["size"]), p["size"])
            screen.blit(surf, (p["x"] - p["size"], p["y"] - p["size"]))
    
    def add_particles(self, x, y, count=10, color=COLOR_GREEN):
        for _ in range(count):
            self.particles.append({
                "x": x,
                "y": y,
                "vx": random.uniform(-3, 3),
                "vy": random.uniform(-5, -1),
                "size": random.randint(2, 6),
                "life": random.randint(20, 40),
                "max_life": 40,
                "color": color
            })
