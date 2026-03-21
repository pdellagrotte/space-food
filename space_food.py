"""Space Food — Python/pygame port of the browser Space Invaders clone."""
import math
import random
import sys

import pygame
from PIL import Image, ImageDraw, ImageFont

# ── Display ────────────────────────────────────────────────────────────────
W, H = 800, 600
FPS  = 60

# ── Grid ───────────────────────────────────────────────────────────────────
ROWS, COLS   = 3, 10
GAP_X, GAP_Y = 65, 52
START_X      = 75
START_Y      = 72
MAX_WAVES    = 5

# ── Entities ───────────────────────────────────────────────────────────────
ENEMY_EMOJIS = ['🍦', '🧆', '🥪']
ENEMY_POINTS = [30, 20, 10]           # per row, multiplied by wave

PLAYER_EMOJI       = '🍔'
STARTING_LIVES     = 3
PLAYER_SPEED       = 5
SHOOT_COOLDOWN     = 13
INVINCIBILITY_TIME = 160

BULLET_SPEED    = 12
BULLET_W        = 6
BULLET_H        = 20

ENEMY_BULLET_R       = 7
ENEMY_BULLET_BASE    = 3.5
ENEMY_BULLET_WAVE    = 0.45

PARTICLE_COUNT   = 6
PARTICLE_MAXLIFE = 40
PARTICLE_GRAVITY = 0.1

NUM_STARS = 130

# ── Colors ─────────────────────────────────────────────────────────────────
BG        = (  5,   5,  16)
WHITE     = (255, 255, 255)
YELLOW    = (255, 221,  87)
RED       = (220,  50,  50)
ORANGE    = (255,  69,   0)
GOLD_LO   = (224, 120,   0)
GOLD_HI   = (255, 224, 102)
DARK_GREY = ( 80,  80,  80)

# ── Emoji font (Windows — Segoe UI Emoji ships with Win10+) ────────────────
EMOJI_FONT_PATH = "C:/Windows/Fonts/seguiemj.ttf"
_emoji_cache: dict[tuple[str, int], pygame.Surface] = {}


def get_emoji_surf(char: str, size: int) -> pygame.Surface:
    """Return a cached pygame.Surface with the emoji rendered via Pillow."""
    key = (char, size)
    if key in _emoji_cache:
        return _emoji_cache[key]

    canvas = size * 2
    img  = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(EMOJI_FONT_PATH, size)
    except OSError:
        # Fallback: use default PIL font (monochrome, small)
        font = ImageFont.load_default()

    try:
        bbox = draw.textbbox((0, 0), char, font=font, embedded_color=True)
        glyph_w = bbox[2] - bbox[0]
        glyph_h = bbox[3] - bbox[1]
        x_off = (canvas - glyph_w) // 2 - bbox[0]
        y_off = (canvas - glyph_h) // 2 - bbox[1]
        draw.text((x_off, y_off), char, font=font, embedded_color=True)
    except TypeError:
        # Older Pillow without embedded_color
        bbox = draw.textbbox((0, 0), char, font=font)
        glyph_w = bbox[2] - bbox[0]
        glyph_h = bbox[3] - bbox[1]
        x_off = (canvas - glyph_w) // 2 - bbox[0]
        y_off = (canvas - glyph_h) // 2 - bbox[1]
        draw.text((x_off, y_off), char, font=font, fill=(255, 255, 255, 255))

    # Crop to actual pixels
    content = img.getbbox()
    if content:
        img = img.crop(content)

    surf = pygame.image.frombuffer(img.tobytes(), img.size, "RGBA").convert_alpha()
    _emoji_cache[key] = surf
    return surf


def blit_emoji(screen: pygame.Surface, char: str, size: int, cx: int, cy: int,
               alpha: int = 255) -> None:
    """Blit an emoji centered at (cx, cy) with optional alpha."""
    surf = get_emoji_surf(char, size)
    if alpha < 255:
        surf = surf.copy()
        surf.set_alpha(alpha)
    rect = surf.get_rect(center=(cx, cy))
    screen.blit(surf, rect)


# ── Stars ──────────────────────────────────────────────────────────────────

def build_star_surface() -> pygame.Surface:
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    for _ in range(NUM_STARS):
        x = random.randint(0, W - 1)
        y = random.randint(0, H - 1)
        r = random.uniform(0.3, 1.7)
        a = random.randint(80, 220)
        pygame.draw.circle(surf, (255, 255, 255, a), (x, y), max(1, int(r)))
    return surf


# ── Helpers ────────────────────────────────────────────────────────────────

def circle_rect_overlap(cx, cy, cr, rx, ry, rw, rh) -> bool:
    """Exact circle-AABB overlap (mirrors JS circleBox)."""
    near_x = max(rx, min(cx, rx + rw))
    near_y = max(ry, min(cy, ry + rh))
    dx = cx - near_x
    dy = cy - near_y
    return dx * dx + dy * dy < cr * cr


def draw_text(screen, text, x, y, size, color, bold=False, align='left'):
    font_name = "couriernew" if pygame.font.match_font("couriernew") else None
    key = (font_name, size, bold)
    if not hasattr(draw_text, '_cache'):
        draw_text._cache = {}
    if key not in draw_text._cache:
        draw_text._cache[key] = pygame.font.SysFont(
            font_name or "monospace", size, bold=bold)
    font = draw_text._cache[key]
    surf = font.render(text, True, color)
    if align == 'center':
        x -= surf.get_width() // 2
    elif align == 'right':
        x -= surf.get_width()
    screen.blit(surf, (x, y))
    return surf.get_width()


def glow_text(screen, text, cx, y, size, color, glow_color):
    """Draw text with a simple glow by blitting slightly offset copies."""
    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        draw_text(screen, text, cx + dx, y + dy, size, glow_color, bold=True, align='center')
    draw_text(screen, text, cx, y, size, color, bold=True, align='center')


# ── Game entities ──────────────────────────────────────────────────────────

class Player:
    W, H = 48, 48

    def __init__(self):
        self.x   = W // 2
        self.y   = H - 55
        self.cool = 0
        self.inv  = 0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.x - self.W // 2, self.y - self.H // 2, self.W, self.H)

    def update(self, keys):
        dx = (1 if (keys[pygame.K_RIGHT] or keys[pygame.K_d]) else 0) \
           - (1 if (keys[pygame.K_LEFT]  or keys[pygame.K_a]) else 0)
        self.x = max(self.W // 2, min(W - self.W // 2, self.x + dx * PLAYER_SPEED))
        if self.cool > 0:
            self.cool -= 1
        if self.inv > 0:
            self.inv -= 1

    def draw(self, screen, frame):
        if self.inv > 0 and (self.inv // 5) % 2 == 0:
            return
        blit_emoji(screen, PLAYER_EMOJI, 42, self.x, self.y)


class Enemy:
    W, H = 40, 40

    def __init__(self, row, col):
        self.row   = row
        self.col   = col
        self.emoji = ENEMY_EMOJIS[row]
        self.pts   = 0          # set when wave starts
        self.x     = START_X + col * GAP_X
        self.y     = START_Y + row * GAP_Y
        self.alive = True

    def draw(self, screen):
        blit_emoji(screen, self.emoji, 34, self.x, self.y)


class Bullet:
    def __init__(self, x, y, dy, owner):
        self.x     = x
        self.y     = y
        self.dy    = dy
        self.owner = owner   # 'player' | 'enemy'
        self.alive = True
        self.spd   = abs(dy)

    def update(self):
        self.y += self.dy
        if self.owner == 'player' and self.y + BULLET_H < 0:
            self.alive = False
        if self.owner == 'enemy' and self.y - ENEMY_BULLET_R > H:
            self.alive = False

    def draw(self, screen):
        if self.owner == 'player':
            pygame.draw.rect(screen, GOLD_HI,
                             (self.x - BULLET_W // 2, self.y - BULLET_H, BULLET_W, BULLET_H),
                             border_radius=3)
        else:
            pygame.draw.circle(screen, (220, 17, 17), (int(self.x), int(self.y)), ENEMY_BULLET_R)
            # Teardrop tip
            pts = [
                (self.x - ENEMY_BULLET_R * 0.45, self.y),
                (self.x,                          self.y - ENEMY_BULLET_R * 1.8),
                (self.x + ENEMY_BULLET_R * 0.45, self.y),
            ]
            pygame.draw.polygon(screen, (200, 20, 20),
                                [(int(p[0]), int(p[1])) for p in pts])


class Particle:
    def __init__(self, x, y, emoji):
        angle = random.uniform(0, math.tau)
        spd   = random.uniform(1.0, 4.0)
        self.x       = float(x)
        self.y       = float(y)
        self.vx      = math.cos(angle) * spd
        self.vy      = math.sin(angle) * spd
        self.life    = PARTICLE_MAXLIFE
        self.emoji   = emoji
        self.base_sz = random.randint(18, 28)

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vy += PARTICLE_GRAVITY
        self.life -= 1

    def draw(self, screen):
        t     = self.life / PARTICLE_MAXLIFE
        alpha = int(255 * t)
        size  = max(4, int(self.base_sz * t))
        blit_emoji(screen, self.emoji, size, int(self.x), int(self.y), alpha=alpha)


# ── Game ───────────────────────────────────────────────────────────────────

class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen    = screen
        self.clock     = pygame.time.Clock()
        self.star_surf = build_star_surface()
        self.frame     = 0
        self.state     = 'start'
        self._prewarm_cache()

    def _prewarm_cache(self):
        for e in ENEMY_EMOJIS + [PLAYER_EMOJI, '🏆', '💀', '🎉']:
            for sz in (22, 34, 42, 52, 60, 76):
                get_emoji_surf(e, sz)

    # ── Init ──────────────────────────────────────────────────────────────

    def _new_game(self):
        self.score = 0
        self.lives = STARTING_LIVES
        self.wave  = 1
        self._init_wave()

    def _init_wave(self):
        self.player    = Player()
        self.bullets   = []
        self.particles = []
        self._spawn_enemies()

        f = 1 + (self.wave - 1) * 0.45
        self.enemy_dir           = 1
        self.enemy_speed         = 7 * f
        self.enemy_drop          = 14
        self.move_interval       = max(6, int(40 / f))
        self.shoot_interval      = max(22, 80 - self.wave * 9)
        self.enemy_bullet_speed  = ENEMY_BULLET_BASE + self.wave * ENEMY_BULLET_WAVE
        self.move_timer          = 0
        self.shoot_timer         = 0

    def _spawn_enemies(self):
        self.enemies = []
        for r in range(ROWS):
            for c in range(COLS):
                e = Enemy(r, c)
                e.pts = ENEMY_POINTS[r] * self.wave
                self.enemies.append(e)

    # ── Input ─────────────────────────────────────────────────────────────

    def handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                    if self.state != 'playing':
                        self._new_game()
                        self.state = 'playing'
                    elif ev.key == pygame.K_SPACE:
                        self._try_shoot()

    def _try_shoot(self):
        if self.player.cool > 0:
            return
        self.bullets.append(Bullet(self.player.x, self.player.y - 26, -BULLET_SPEED, 'player'))
        self.player.cool = SHOOT_COOLDOWN

    # ── Update ────────────────────────────────────────────────────────────

    def update(self):
        self.frame += 1
        keys = pygame.key.get_pressed()
        self.player.update(keys)
        if keys[pygame.K_SPACE]:
            self._try_shoot()

        self._move_bullets()
        self._move_enemies()
        self._enemy_shoot()
        self._check_collisions()
        self._update_particles()

    def _move_bullets(self):
        for b in self.bullets:
            b.update()
        self.bullets = [b for b in self.bullets if b.alive]

    def _move_enemies(self):
        self.move_timer += 1
        if self.move_timer < self.move_interval:
            return
        self.move_timer = 0

        alive = [e for e in self.enemies if e.alive]
        if not alive:
            return

        step = self.enemy_dir * self.enemy_speed
        for e in alive:
            e.x += step

        min_x = min(e.x - e.W // 2 for e in alive)
        max_x = max(e.x + e.W // 2 for e in alive)

        if max_x >= W - 8 or min_x <= 8:
            self.enemy_dir *= -1
            for e in alive:
                e.x += self.enemy_dir * self.enemy_speed * 1.8
                e.y += self.enemy_drop

    def _enemy_shoot(self):
        self.shoot_timer += 1
        if self.shoot_timer < self.shoot_interval:
            return
        self.shoot_timer = 0

        # Bottommost alive enemy per column
        cols: dict[int, Enemy] = {}
        for e in self.enemies:
            if not e.alive:
                continue
            if e.col not in cols or e.row > cols[e.col].row:
                cols[e.col] = e
        if not cols:
            return
        shooter = random.choice(list(cols.values()))
        self.bullets.append(
            Bullet(shooter.x, shooter.y + 22, self.enemy_bullet_speed, 'enemy'))

    def _check_collisions(self):
        p = self.player

        for b in self.bullets:
            if not b.alive:
                continue

            if b.owner == 'player':
                # Box-box: bullet top-left origin vs enemy center origin
                bx = b.x - BULLET_W // 2
                by = b.y - BULLET_H
                for e in self.enemies:
                    if not e.alive:
                        continue
                    ex = e.x - e.W // 2
                    ey = e.y - e.H // 2
                    if bx < ex + e.W and bx + BULLET_W > ex \
                            and by < ey + e.H and by + BULLET_H > ey:
                        b.alive    = False
                        e.alive    = False
                        self.score += e.pts
                        self._spawn_burst(e.x, e.y, e.emoji)
                        break

            else:  # enemy bullet
                if p.inv > 0:
                    continue
                px = p.x - p.W // 2
                py = p.y - p.H // 2
                if circle_rect_overlap(b.x, b.y, ENEMY_BULLET_R, px, py, p.W, p.H):
                    b.alive  = False
                    self.lives -= 1
                    p.inv    = INVINCIBILITY_TIME
                    if self.lives <= 0:
                        self.state = 'dead'

        # Enemy reaches ground
        for e in self.enemies:
            if e.alive and e.y + e.H // 2 > p.y - 8:
                self.state = 'dead'
                return

        # Wave cleared
        if all(not e.alive for e in self.enemies):
            if self.wave >= MAX_WAVES:
                self.state = 'win'
            else:
                self.wave += 1
                self._init_wave()

    def _spawn_burst(self, x, y, emoji):
        for _ in range(PARTICLE_COUNT):
            self.particles.append(Particle(x, y, emoji))

    def _update_particles(self):
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]

    # ── Draw ──────────────────────────────────────────────────────────────

    def draw(self):
        screen = self.screen

        screen.fill(BG)
        screen.blit(self.star_surf, (0, 0))

        if self.state == 'start':
            self._draw_start()
            pygame.display.flip()
            return

        # Enemies
        for e in self.enemies:
            if e.alive:
                e.draw(screen)

        # Particles
        for p in self.particles:
            p.draw(screen)

        # Bullets
        for b in self.bullets:
            b.draw(screen)

        # Player
        self.player.draw(screen, self.frame)

        self._draw_hud()

        if self.state == 'dead':
            self._draw_overlay_dead()
        elif self.state == 'win':
            self._draw_overlay_win()

        pygame.display.flip()

    def _draw_hud(self):
        screen = self.screen
        # Score
        draw_text(screen, f'SCORE: {self.score}', 14, 8, 18, YELLOW, bold=True)
        # Wave
        draw_text(screen, f'WAVE {self.wave}/{MAX_WAVES}', W // 2, 8, 18, (255, 107, 107),
                  bold=True, align='center')
        # Lives as burger emoji
        for i in range(3):
            alpha = 255 if i < self.lives else 38
            blit_emoji(screen, PLAYER_EMOJI, 22, W - 18 - i * 28, 22, alpha=alpha)

        # Divider
        pygame.draw.line(screen, (255, 69, 0, 48), (0, 38), (W, 38), 1)
        # Ground line
        pygame.draw.line(screen, (255, 69, 0, 80), (0, H - 28), (W, H - 28), 2)

    def _draw_overlay(self):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((3, 3, 18, 220))
        self.screen.blit(overlay, (0, 0))

    def _draw_start(self):
        screen = self.screen
        glow_text(screen, 'SPACE FOOD', W // 2, 66, 64, ORANGE, (200, 40, 0))
        draw_text(screen, 'A Delicious Invasion', W // 2, 145, 20, YELLOW, align='center')
        blit_emoji(screen, PLAYER_EMOJI, 56, W // 2, 215)

        draw_text(screen, 'DEFEND AGAINST:', W // 2, 272, 15, DARK_GREY, align='center')
        for i, (off, em) in enumerate(zip([-100, 0, 100], ENEMY_EMOJIS)):
            blit_emoji(screen, em, 34, W // 2 + off, 315)
            draw_text(screen, f'{ENEMY_POINTS[i]}×wave', W // 2 + off, 340, 12,
                      (136, 136, 136), align='center')

        draw_text(screen, '\u2190 \u2192  or  A D    Move', W // 2, 385, 15,
                  (190, 190, 190), align='center')
        draw_text(screen, 'SPACE              Shoot', W // 2, 407, 15,
                  (190, 190, 190), align='center')

        if (self.frame // 28) % 2 == 0:
            draw_text(screen, 'PRESS SPACE OR ENTER', W // 2, 462, 20,
                      (255, 107, 107), bold=True, align='center')

        draw_text(screen, f'{MAX_WAVES} waves of increasingly hangry enemies await\u2026',
                  W // 2, 524, 13, (60, 60, 60), align='center')

    def _draw_overlay_dead(self):
        self._draw_overlay()
        screen = self.screen
        blit_emoji(screen, '💀', 76, W // 2, 165)
        glow_text(screen, 'GAME OVER', W // 2, 255, 56, (255, 68, 68), (200, 0, 0))
        draw_text(screen, f'SCORE: {self.score}', W // 2, 305, 26, YELLOW,
                  bold=True, align='center')
        draw_text(screen, f'Reached wave {self.wave} of {MAX_WAVES}', W // 2, 343, 17,
                  (136, 136, 136), align='center')
        if (self.frame // 28) % 2 == 0:
            draw_text(screen, 'PRESS SPACE OR ENTER TO RETRY', W // 2, 418, 18,
                      (255, 107, 107), bold=True, align='center')

    def _draw_overlay_win(self):
        self._draw_overlay()
        screen = self.screen
        blit_emoji(screen, '🏆', 76, W // 2, 155)
        glow_text(screen, 'YOU WIN!', W // 2, 250, 60, YELLOW, (200, 130, 0))
        draw_text(screen, 'The food invasion has been defeated!', W // 2, 295, 17,
                  (170, 170, 170), align='center')
        draw_text(screen, f'FINAL SCORE: {self.score}', W // 2, 335, 26, YELLOW,
                  bold=True, align='center')
        blit_emoji(screen, '🎉', 36, W // 2 - 60, 390)
        blit_emoji(screen, PLAYER_EMOJI, 36, W // 2,      390)
        blit_emoji(screen, '🎉', 36, W // 2 + 60, 390)
        if (self.frame // 28) % 2 == 0:
            draw_text(screen, 'PRESS SPACE OR ENTER TO PLAY AGAIN', W // 2, 455, 17,
                      (255, 107, 107), bold=True, align='center')

    # ── Main loop ──────────────────────────────────────────────────────────

    def run(self):
        while True:
            self.clock.tick(FPS)
            self.handle_events()
            if self.state == 'playing':
                self.update()
            self.draw()


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption('Space Food')
    game = Game(screen)
    game.run()
    pygame.quit()
