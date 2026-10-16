# /// script
# dependencies = [
#   "pytmx",
# ]
# ///
import math
import random
import asyncio
import pygame
import pytmx
_cut = max(__file__.rfind("/"), __file__.rfind("\\"))
BASE = __file__[:_cut + 1]


def asset(name):
    return BASE + name


TILE = 16
ZOOM = 3
VIEW_W, VIEW_H = 320, 200
SCREEN_W, SCREEN_H = VIEW_W * ZOOM, VIEW_H * ZOOM
FPS = 60
ACCEL, DRAG, BOX = 0.30, 0.86, 10
ZOMBIE_BOX = 14
V2 = pygame.math.Vector2

TILESET_PNG = asset("Dungeon_Tileset.png")
COIN_ID = 86
TRAPDOOR_ID = 38
DOOR_IDS = (66, 67)
MAZE_SPAWN = (35, 26)
ROOM_SPAWN = (22, 22)
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]
RARITY_WEIGHT = {"common": 50, "uncommon": 25, "rare": 15, "epic": 7, "legendary": 3}
RARITY_COLOR = {"common": (200, 200, 200), "uncommon": (120, 230, 130), "rare": (110, 170, 255),
                "epic": (255, 110, 120), "legendary": (255, 220, 70)}
CARD_BACK_X = {"rare": 14, "epic": 133, "common": 250, "uncommon": 366, "legendary": 481}

STAGE_MAPS = {"room": "aracaderunmap1.tmx", "maze": "map_maze.tmx", "boss": "boss.tmx"}
STAGE_NAMES = {"room": "Mob room", "maze": "Maze", "boss": "Samurai boss"}


class Assets:
    """Loads every image once (needs the display to exist)."""

    def __init__(self):
        self.tileset = pygame.image.load(TILESET_PNG).convert_alpha()
        self.run = self._sheet(asset("1Zombie-Run.png"), 8, 4)
        self.hurt = self._sheet(asset("1Zombie-Hurt.png"), 2, 4)
        self.death = self._sheet(asset("1Zombie-Death1.png"), 8, 4)
        self.hero_run = [[self._recolor(f) for f in row] for row in self.run]
        self.hero_flash = [[self._flash(f) for f in row] for row in self.run]
        sheet = pygame.image.load(asset("card_sheet.png")).convert_alpha()
        self.card_back = {r: pygame.transform.scale(sheet.subsurface((x, 4, 100, 128)), (170, 218))
                          for r, x in CARD_BACK_X.items()}
        self.slot = pygame.transform.scale(pygame.image.load(asset("ability_slot.png")).convert_alpha(), (54, 54))
        self.font_s = pygame.font.Font(None, 22)
        self.font_m = pygame.font.Font(None, 30)
        self.font_l = pygame.font.Font(None, 56)

    def tileset_loader(self, filename, colorkey, **kwargs):
        sheet = self.tileset

        def load_image(rect=None, flags=None):
            tile = sheet.subsurface(rect).copy() if rect else sheet.copy()
            if flags:
                if flags.flipped_diagonally:
                    tile = pygame.transform.flip(pygame.transform.rotate(tile, 270), True, False)
                if flags.flipped_horizontally or flags.flipped_vertically:
                    tile = pygame.transform.flip(tile, flags.flipped_horizontally, flags.flipped_vertically)
            return tile

        return load_image

    def tile(self, tid):
        return self.tileset.subsurface((tid % 10 * TILE, tid // 10 * TILE, TILE, TILE))

    @staticmethod
    def _sheet(path, cols, rows, fw=32, fh=32):
        img = pygame.image.load(path).convert_alpha()
        return [[img.subsurface((c * fw, r * fh, fw, fh)).copy() for c in range(cols)] for r in range(rows)]

    @staticmethod
    def _recolor(surf):
        out = surf.copy()
        for x in range(out.get_width()):
            for y in range(out.get_height()):
                r, g, b, a = out.get_at((x, y))
                if a:
                    out.set_at((x, y), (r, b, g, a))
        return out

    @staticmethod
    def _flash(surf):
        out = surf.copy()
        out.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return out

    @staticmethod
    def facing(vec):
        if abs(vec.x) >= abs(vec.y):
            return 1, vec.x < 0
        return (0, False) if vec.y > 0 else (2, False)


class Card:
    def __init__(self, key, name, rarity, price, stackable, requires, desc):
        self.key, self.name, self.rarity, self.price = key, name, rarity, price
        self.stackable, self.requires, self.desc = stackable, requires, desc


CARDS = {c.key: c for c in [
    Card("dash", "Dash", "uncommon", 90, False, None, "Q: burst of speed with brief invulnerability."),
    Card("multidash", "Multi Dash", "legendary", 500, True, "dash", "+1 dash charge (stacks up to 3)."),
    Card("parry", "Parry", "rare", 160, False, None, "Right click: a short window that blocks and staggers."),
    Card("parry2", "Parry+", "epic", 280, False, "parry", "Longer parry window; parried foes take damage."),
    Card("beam", "Sword Beam", "epic", 280, False, None, "While at full health, every swing also fires a piercing beam."),
    Card("coin", "Greed", "rare", 140, True, None, "+50% gold, but enemies get tougher and faster."),
    Card("speed", "Speed", "common", 40, True, None, "+10% movement speed."),
    Card("speed2", "Speed II", "rare", 160, True, "speed", "+25% movement speed."),
    Card("attack", "Attack", "common", 40, True, None, "+25% damage."),
    Card("attack2", "Attack II", "rare", 160, True, "attack", "+60% damage."),
    Card("atkspd", "Attack Speed", "common", 40, True, None, "Swing 15% faster."),
    Card("atkspd2", "Attack Speed II", "rare", 160, True, "atkspd", "Swing 30% faster."),
    Card("potion", "Healing Potion", "uncommon", 90, True, None, "F: heal 40 HP. One more potion every run."),
    Card("slow", "Frost Edge", "rare", 150, False, None, "Hits slow enemies by 45% for 2s."),
    Card("fire", "Fire Edge", "epic", 260, False, None, "Hits set enemies on fire."),
]}


class Stats:

    def __init__(self):
        self.owned = {}
        self.gold = 0
        self.deaths = 0
        self.difficulty = 0
        self.boss_phase = 0        
        self.boss_seen = False     
    def n(self, key):
        return self.owned.get(key, 0)

    def can_offer(self, key):
        c = CARDS[key]
        if not c.stackable and self.n(key):
            return False
        if c.requires and not self.n(c.requires):
            return False
        return not (key == "multidash" and self.n(key) >= 2)

    def roll_offers(self, count=3):
        pool = [k for k in CARDS if self.can_offer(k)]
        offers = []
        while pool and len(offers) < count:
            pick = random.choices(pool, [RARITY_WEIGHT[CARDS[k].rarity] for k in pool])[0]
            offers.append(pick)
            pool.remove(pick)
        return offers

    move = property(lambda s: 1 + 0.10 * s.n("speed") + 0.25 * s.n("speed2"))
    damage = property(lambda s: 10 * (1 + 0.25 * s.n("attack") + 0.60 * s.n("attack2")))
    swing_cd = property(lambda s: max(0.5, .9 * (1 - 0.15 * s.n("atkspd") - 0.30 * s.n("atkspd2"))))
    gold_mult = property(lambda s: 1 + 0.5 * s.n("coin"))
    enemy_mult = property(lambda s: 1 + 0.15 * s.n("coin") + 0.25 * s.difficulty)
    dash_charges = property(lambda s: (1 + s.n("multidash")) if s.n("dash") else 0)
    parry_window = property(lambda s: 0.45 if s.n("parry2") else 0.25)


class Physics:
    @staticmethod
    def move_box(level, pos, vel, size):
        half = size / 2
        for axis in (0, 1):
            pos[axis] += vel[axis]
            hit = False
            x0, x1 = int((pos.x - half) // TILE), int((pos.x + half - 0.01) // TILE)
            y0, y1 = int((pos.y - half) // TILE), int((pos.y + half - 0.01) // TILE)
            for ty in range(y0, y1 + 1):
                for tx in range(x0, x1 + 1):
                    if level.is_solid(tx, ty):
                        hit = True
                        edge = tx if axis == 0 else ty
                        if vel[axis] > 0:
                            pos[axis] = edge * TILE - half
                        elif vel[axis] < 0:
                            pos[axis] = (edge + 1) * TILE + half
                        x0, x1 = int((pos.x - half) // TILE), int((pos.x + half - 0.01) // TILE)
                        y0, y1 = int((pos.y - half) // TILE), int((pos.y + half - 0.01) // TILE)
            if hit:
                vel[axis] = 0

    @staticmethod
    def tile_center(t):
        return V2(t[0] * TILE + TILE / 2, t[1] * TILE + TILE / 2)

    @staticmethod
    def tile_of(pos):
        return int(pos.x // TILE), int(pos.y // TILE)


class Level:

    def __init__(self, game, path, allow_breakable):
        self.tmx = pytmx.TiledMap(path, image_loader=game.assets.tileset_loader)
        self.w, self.h = self.tmx.width, self.tmx.height
        self.floor = pygame.Surface((self.w * TILE, self.h * TILE))
        self.top = pygame.Surface((self.w * TILE, self.h * TILE), pygame.SRCALPHA)
        self.solid = [[False] * self.w for _ in range(self.h)]
        self.breakable, self.coins, self.doors = set(), set(), set()
        self.trapdoor = None
        self._flow_from, self._flow = None, {}
        for x, y, img in self.tmx.layers[0].tiles():
            self.floor.blit(img, (x * TILE, y * TILE))
        top_data = self.tmx.layers[1].iter_data() if len(self.tmx.layers) > 1 else []
        for x, y, gid in top_data:
            if not gid:
                continue
            tid = self.tmx.tiledgidmap.get(gid, 0) - 1
            if tid == TRAPDOOR_ID:
                self.trapdoor = (x, y)
                continue
            props = self.tmx.get_tile_properties_by_gid(gid) or {}
            img = self.tmx.get_tile_image_by_gid(gid)
            if img:
                self.top.blit(img, (x * TILE, y * TILE))
            if tid == COIN_ID or props.get("coin"):
                self.coins.add((x, y))
            if tid in DOOR_IDS:
                self.doors.add((x, y))
                self.solid[y][x] = True
            elif props.get("collidable"):
                self.solid[y][x] = True
                if allow_breakable and props.get("breakable"):
                    self.breakable.add((x, y))

    def is_solid(self, tx, ty):
        if tx < 0 or ty < 0 or tx >= self.w or ty >= self.h:
            return True
        return self.solid[ty][tx]

    def remove_tile(self, tx, ty):
        self.solid[ty][tx] = False
        for group in (self.breakable, self.coins, self.doors):
            group.discard((tx, ty))
        self.top.fill((0, 0, 0, 0), (tx * TILE, ty * TILE, TILE, TILE))

    def open_doors(self):
        for d in list(self.doors):
            self.remove_tile(*d)

    def free_near(self, tx, ty):
        for r in range(20):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    c = (tx + dx, ty + dy)
                    if not self.is_solid(*c) and c not in self.coins:
                        return c
        return tx, ty

    def bfs(self, start, through_breakables=False):
        dist = {start: 0}
        queue, head = [start], 0
        while head < len(queue):
            cx, cy = queue[head]
            head += 1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cx + dx, cy + dy)
                if n in dist:
                    continue
                if self.is_solid(*n) and not (through_breakables and n in self.breakable):
                    continue
                dist[n] = dist[(cx, cy)] + 1
                queue.append(n)
        return dist

    def flow_to(self, tile):
        if self._flow_from != tile:
            self._flow_from, self._flow = tile, self.bfs(tile)
        return self._flow

    def draw(self, surf, cam):
        surf.blit(self.floor, (-cam.x, -cam.y))
        surf.blit(self.top, (-cam.x, -cam.y))


class Entity:
    def __init__(self, game, pos):
        self.game = game
        self.pos = V2(pos)
        self.vel = V2()
        self.face = V2(0, 1)
        self.anim = 0.0

    @property
    def rect(self):
        return pygame.Rect(self.pos.x - BOX / 2, self.pos.y - BOX / 2, BOX, BOX)

    def blit_sprite(self, surf, img, cam, mirror):
        if mirror:
            img = pygame.transform.flip(img, True, False)
        surf.blit(img, (self.pos.x - 16 - cam.x, self.pos.y - 16 - cam.y))


class Player(Entity):
    def __init__(self, game, pos):
        super().__init__(game, pos)
        s = game.stats
        self.max_hp = self.hp = 100
        self.swing_t = self.parry_t = self.parry_cd = self.iframes = 0.0
        self.slash_t = self.hurt_flash = 0.0
        self.dash_charges, self.dash_cd = s.dash_charges, 0.0
        self.potions = s.n("potion")
        self.aim = V2(1, 0)
        self.slash_dir = V2(1, 0)

    def update(self, level, keys):
        dt = 1 / FPS
        inp = V2(keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w])
        if inp.length_squared():
            inp = inp.normalize()
            self.face = V2(inp)
        self.vel = (self.vel + inp * ACCEL * self.game.stats.move) * DRAG
        Physics.move_box(level, self.pos, self.vel, BOX)
        self.anim += self.vel.length() * 0.12
        for a in ("swing_t", "parry_t", "parry_cd", "iframes", "slash_t", "hurt_flash"):
            setattr(self, a, max(0.0, getattr(self, a) - dt))
        if self.dash_charges < self.game.stats.dash_charges:
            self.dash_cd -= dt
            if self.dash_cd <= 0:
                self.dash_charges += 1
                self.dash_cd = 1.3

    def dash(self):
        if self.dash_charges <= 0:
            return
        d = V2(self.vel) if self.vel.length_squared() > 0.1 else V2(self.aim)
        self.vel += d.normalize() * 6.5
        self.iframes = 0.28
        if self.dash_charges == self.game.stats.dash_charges:
            self.dash_cd = 1.3
        self.dash_charges -= 1

    def swing(self, world):
        if self.swing_t > 0:
            return
        s = self.game.stats
        self.swing_t, self.slash_t, self.slash_dir = s.swing_cd, 0.12, V2(self.aim)
        box = pygame.Rect(0, 0, 26, 26)
        box.center = self.pos + self.aim * 15
        world.melee_hit(box, s.damage, self.aim)
        if s.n("beam")and self.hp >= self.max_hp:
            world.beams.append(Beam(self.pos + self.aim * 8, self.aim, s.damage * 0.5))

    def parry(self):
        if self.game.stats.n("parry") and self.parry_cd <= 0:
            self.parry_t, self.parry_cd = self.game.stats.parry_window, 0.9

    def use_potion(self):
        if self.potions > 0 and self.hp < self.max_hp:
            self.potions -= 1
            self.hp = min(self.max_hp, self.hp + 40)

    def hurt(self, amount):
        if self.iframes > 0:
            return False
        self.hp -= amount
        self.iframes, self.hurt_flash = 0.6, 0.15
        return True

    def draw(self, surf, cam):
        a = self.game.assets
        row, mirror = a.facing(self.face)
        frame = int(self.anim) % 8 if self.vel.length() > 0.2 else 0
        img = (a.hero_flash if self.hurt_flash > 0 else a.hero_run)[row][frame]
        self.blit_sprite(surf, img, cam, mirror)
        c = self.pos - cam
        if self.slash_t > 0:
            base = math.atan2(self.slash_dir.y, self.slash_dir.x)
            pts = [(c.x + math.cos(base + t) * 17, c.y + math.sin(base + t) * 17) for t in (-0.9, -0.45, 0, 0.45, 0.9)]
            pygame.draw.lines(surf, (255, 255, 255), False, pts, 2)
        if self.parry_t > 0:
            pygame.draw.circle(surf, (120, 200, 255), (int(c.x), int(c.y)), 12, 1)


class Beam:
    def __init__(self, pos, direction, dmg):
        self.pos, self.vel = V2(pos), V2(direction) * 4.2
        self.dmg, self.life, self.hit, self.dead = dmg, 70, set(), False

    @property
    def rect(self):
        return pygame.Rect(self.pos.x - 5, self.pos.y - 5, 10, 10)

    def update(self, world):
        self.life -= 1
        self.pos += self.vel
        t = Physics.tile_of(self.pos)
        if self.life <= 0 or world.level.is_solid(*t):
            if t in world.level.breakable:
                world.level.remove_tile(*t)
            self.dead = True
            return
        for e in world.enemies:
            if not e.dying and id(e) not in self.hit and self.rect.colliderect(e.rect):
                self.hit.add(id(e))
                e.take_damage(self.dmg, self.vel.normalize(), world)

    def draw(self, surf, cam):
        c = (int(self.pos.x - cam.x), int(self.pos.y - cam.y))
        pygame.draw.circle(surf, (170, 230, 255), c, 4)
        pygame.draw.circle(surf, (255, 255, 255), c, 2)


class Zombie(Entity):
    def __init__(self, game, pos):
        super().__init__(game, pos)
        m = game.stats.enemy_mult
        self.hp = 30 * m
        self.accel = 0.24 * (1 + (m - 1) * 0.5)
        self.contact = 10 * (1 + (m - 1) * 0.3)
        self.cd = self.stun = self.slow_t = self.burn_t = self.burn_tick = self.flash = self.death_t = 0.0
        self.dying = self.aggro = self.dead = False
        self.anim = random.random() * 8

    @property
    def rect(self):
        return pygame.Rect(self.pos.x - ZOMBIE_BOX / 2,self.pos.y - ZOMBIE_BOX / 2,ZOMBIE_BOX,ZOMBIE_BOX)

    def take_damage(self, amount, knock, world):
        self.hp -= amount
        self.flash = 0.12
        self.vel += knock * 3.2
        self.aggro = True
        s = self.game.stats
        if s.n("slow"):
            self.slow_t = 2.0
        if s.n("fire"):
            self.burn_t = 3.0
        self._check_death(world)

    def _check_death(self, world):
        if self.hp <= 0 and not self.dying:
            self.dying, self.death_t = True, 0.0
            world.on_kill(self)

    def update(self, world):
        dt = 1 / FPS
        if self.dying:
            self.death_t += dt * 9
            self.dead = self.death_t >= 8
            return
        for a in ("cd", "stun", "slow_t", "flash"):
            setattr(self, a, max(0.0, getattr(self, a) - dt))
        if self.burn_t > 0:
            self.burn_t -= dt
            self.burn_tick += dt
            if self.burn_tick >= 0.5:
                self.burn_tick = 0
                self.hp -= 4
                self.flash = 0.06
                self._check_death(world)
        p = world.player
        to_p = p.pos - self.pos
        dist = math.hypot(to_p.x, to_p.y)
        if dist < world.aggro_range:
            self.aggro = True
        direction = V2()
        if self.aggro and self.stun <= 0 and dist > 0:
            if dist < 36 or world.line_clear(self.pos, p.pos):
                direction = to_p / dist
            else:
                direction = world.flow_dir(self.pos)
        speed = self.accel * (0.55 if self.slow_t > 0 else 1.0)
        self.vel = (self.vel + direction * speed) * DRAG
        Physics.move_box(world.level, self.pos, self.vel, BOX)
        if direction.length_squared():
            self.face = direction
        self.anim += self.vel.length() * 0.14
        if self.cd <= 0 and self.stun <= 0 and dist > 0 and self.rect.colliderect(p.rect):
            away = (self.pos - p.pos) / dist
            if p.parry_t > 0:
                self.stun, self.cd = 1.0, 1.0
                self.vel += away * 4.5
                if self.game.stats.n("parry2"):
                    self.take_damage(18, away, world)
                world.parried += 1
            elif p.hurt(self.contact):
                self.cd = 0.8
                p.vel -= away * 2.0

    def draw(self, surf, cam):
        a = self.game.assets
        row, mirror = a.facing(self.face)
        if self.dying:
            img = a.death[row][min(7, int(self.death_t))]
        elif self.flash > 0:
            img = a.hurt[row][int(self.flash * 40) % 2]
        else:
            img = a.run[row][int(self.anim) % 8 if self.vel.length() > 0.15 else 0]
        if self.slow_t > 0 or self.burn_t > 0:
            img = img.copy()
            img.fill((255, 120, 40) if self.burn_t > 0 else (120, 170, 255), special_flags=pygame.BLEND_RGB_ADD)
        self.blit_sprite(surf, img, cam, mirror)


class World:
    def __init__(self, game, stage):
        self.game, self.stage = game, stage
        self.level = Level(game, asset(STAGE_MAPS[stage]), allow_breakable=(stage == "maze"))
        L = self.level
        self.enemies, self.beams, self.popups = [], [], []
        self.kills = self.coins_got = self.gold_run = self.parried = self.wave = 0
        self.cleared = self.won = False
        self.time = 0.0
        self.cam = V2()
        self.aggro_range = 90
        self.bounds = pygame.Rect(0, 0, L.w * TILE, L.h * TILE)    #camera limits
        self.boss = None
        self.exit_tile = L.trapdoor
        if stage == "room":
            spawn = L.free_near(*ROOM_SPAWN)
            self.wave_sizes = [100, 200, 300]
            self.aggro_range = 400
            self.next_wave_t = 1.2
            self.exit_tile = self.exit_tile or L.free_near(14, 31)
        elif stage == "maze":
            spawn = MAZE_SPAWN
            self.exit_dist = L.bfs(self.exit_tile, through_breakables=True)
            self.total = max(1, self.exit_dist.get(spawn, 180))
            path = L.bfs(spawn)
            cells = [c for c, d in path.items() if 22 < d < 150]
            random.shuffle(cells)
            placed = []
            for c in cells:
                if all(abs(c[0] - o[0]) + abs(c[1] - o[1]) > 7 for o in placed):
                    placed.append(c)
                if len(placed) >= 11:
                    break
            self.enemies = [Zombie(game, Physics.tile_center(c)) for c in placed]
        else:                                           
            if not hasattr(game.assets, "boss"):
                game.assets.boss = BossFrames()         
            x0, y0, x1, y1 = BOSS_ARENA
            for ty in range(L.h):                       
                for tx in range(L.w):
                    if not (x0 <= tx < x1 and y0 <= ty < y1):
                        L.solid[ty][tx] = True
            self.bounds = pygame.Rect(x0 * TILE, y0 * TILE, (x1 - x0) * TILE, (y1 - y0) * TILE)
            cx = (x0 + x1) // 2
            spawn = (cx, y1 - 5)
            self.boss = Boss(game, Physics.tile_center((cx, y0 + 8)))
            self.enemies = [self.boss]
        self.player = Player(game, Physics.tile_center(spawn))

    @property
    def exit_open(self):
        return self.stage == "maze" or self.cleared


    def line_clear(self, a, b):
        d = b - a
        n = int(d.length() // 6)
        return not any(self.level.is_solid(*Physics.tile_of(a + d * (i / n))) for i in range(1, n))

    def flow_dir(self, pos):
        dist = self.level.flow_to(Physics.tile_of(self.player.pos))
        t = Physics.tile_of(pos)
        best, bd = None, dist.get(t, 10 ** 9)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (t[0] + dx, t[1] + dy)
            if dist.get(n, 10 ** 9) < bd:
                best, bd = n, dist[n]
        if best is None:
            return V2()
        d = Physics.tile_center(best) - pos
        return d.normalize() if d.length_squared() else V2()

    def melee_hit(self, box, dmg, aim):
        for e in self.enemies:
            if not e.dying and box.colliderect(e.rect):
                e.take_damage(dmg, V2(aim), self)
        for tx in range(box.left // TILE, box.right // TILE + 1):
            for ty in range(box.top // TILE, box.bottom // TILE + 1):
                if (tx, ty) in self.level.breakable:
                    self.level.remove_tile(tx, ty)

    def separate_enemies(self, sep=ZOMBIE_BOX):
        zs = [e for e in self.enemies if isinstance(e, Zombie) and not e.dying]
        grid = {}
        for z in zs:
            grid.setdefault((int(z.pos.x // sep), int(z.pos.y // sep)), []).append(z)
        push = {}
        for (cx, cy), cell in grid.items():
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    other = grid.get((cx + dx, cy + dy))
                    if not other:
                        continue
                    for a in cell:
                        for b in other:
                            if id(a) >= id(b):
                                continue
                            d = a.pos - b.pos
                            dist = d.length()
                            if dist >= sep:
                                continue
                            if dist < 0.01:
                                d = V2(random.uniform(-1, 1), random.uniform(-1, 1))
                                dist = max(d.length(), 0.01)
                            n = d / dist
                            amt = (sep - dist) * 0.25
                            push[a] = push.get(a, V2()) + n * amt
                            push[b] = push.get(b, V2()) - n * amt
        for z, p in push.items():
            Physics.move_box(self.level, z.pos, V2(p), BOX)

    def gain(self, amount, at):
        g = int(round(amount * self.game.stats.gold_mult))
        self.game.stats.gold += g
        self.gold_run += g
        self.popups.append([V2(at), f"+{g}", 0.8])

    def on_kill(self, zombie):
        self.kills += 1
        self.gain(8, zombie.pos)

    def spawn_wave(self):
        n = self.wave_sizes[self.wave]
        self.wave += 1
        self.next_wave_t = 1.5
        spawned = tries = 0
        while spawned < n and tries < 500:
            tries += 1
            t = (random.randint(9, 37), random.randint(10, 33))
            c = Physics.tile_center(t)
            if self.level.is_solid(*t) or c.distance_to(self.player.pos) < 90:
                continue
            self.enemies.append(Zombie(self.game, c))
            spawned += 1

    def update(self, keys):
        self.time += 1 / FPS
        p = self.player
        p.update(self.level, keys)
        aim = (V2(pygame.mouse.get_pos()) / ZOOM + self.cam) - p.pos
        p.aim = aim.normalize() if aim.length_squared() else V2(1, 0)
        if pygame.mouse.get_pressed()[0]:
            p.swing(self)
        for e in self.enemies:
            e.update(self)
        self.separate_enemies()          
        self.enemies = [e for e in self.enemies if not e.dead]
        
        self.enemies = [e for e in self.enemies if not e.dead]
        if self.boss is not None and self.boss.dead:
            self.won = True
        for b in self.beams:
            b.update(self)
        self.beams = [b for b in self.beams if not b.dead]
        for pop in self.popups:
            pop[0].y -= 0.3
            pop[2] -= 1 / FPS
        self.popups = [pp for pp in self.popups if pp[2] > 0]
        pr = p.rect.inflate(6, 6)
        for c in list(self.level.coins):
            if pr.colliderect((c[0] * TILE, c[1] * TILE, TILE, TILE)):
                self.level.remove_tile(*c)
                self.coins_got += 1
                self.gain(1, Physics.tile_center(c))
        if self.stage == "room" and not self.cleared and not self.enemies:
            if self.wave >= len(self.wave_sizes):
                self.cleared = True
                self.level.open_doors()
            else:
                self.next_wave_t -= 1 / FPS
                if self.next_wave_t <= 0:
                    self.spawn_wave()
        if self.exit_open and self.exit_tile:
            ex = pygame.Rect(self.exit_tile[0] * TILE + 3, self.exit_tile[1] * TILE + 3, 10, 10)
            self.won = self.won or p.rect.colliderect(ex)
        target = p.pos - V2(VIEW_W, VIEW_H) / 2
        self.cam += (target - self.cam) * 0.15
        b = self.bounds
        self.cam.x = max(b.left, min(self.cam.x, b.right - VIEW_W))
        self.cam.y = max(b.top, min(self.cam.y, b.bottom - VIEW_H))

    def draw(self, surf, show_boxes):
        cam = V2(int(self.cam.x), int(self.cam.y))
        surf.fill((16, 12, 20))
        self.level.draw(surf, cam)
        if self.exit_tile:
            img = self.game.assets.tile(TRAPDOOR_ID)
            if not self.exit_open:
                img = img.copy()
                img.set_alpha(60)
            surf.blit(img, (self.exit_tile[0] * TILE - cam.x, self.exit_tile[1] * TILE - cam.y))
        ents = [self.player] + self.enemies
        for e in sorted(ents, key=lambda e: e.pos.y):
            e.draw(surf, cam)
        for b in self.beams:
            b.draw(surf, cam)
        if show_boxes:
            for e in ents:
                pygame.draw.rect(surf, (0, 255, 0), e.rect.move(-cam.x, -cam.y), 1)
            for y in range(int(cam.y // TILE), int((cam.y + VIEW_H) // TILE) + 1):
                for x in range(int(cam.x // TILE), int((cam.x + VIEW_W) // TILE) + 1):
                    if self.level.is_solid(x, y):
                        pygame.draw.rect(surf, (255, 60, 60), (x * TILE - cam.x, y * TILE - cam.y, TILE, TILE), 1)


BOSS_HP = 18000                 
BOSS_SCALE = 0.5               
BOSS_ANCHOR = (126, 140)       
BOSS_BOX = 22                  
BOSS_ARENA = (8, 6, 56, 58)    

BOSS_ROW_DEG = {0: 0, 5: 45, 4: 90, 6: 135, 7: 180, 3: 225, 1: 270, 2: 315}
MELEE_HIT = (6, 13)            
RANGED_FIRE = 16               
MELEE_REACH = 52
LAST_PHASE_RESETS = True       
BOSS_PHASES = [
    dict(accel=0.30, melee=22, wave=12, waves=20, spread=0.1, ring=12, think=(0.5, 1.0), rate=0.40, arc=-0.2),
    dict(accel=0.40, melee=26, wave=16, waves=30, spread=0.2, ring=24, think=(0.35, 0.8), rate=0.48, arc=-0.9),
    dict(accel=0.50, melee=49, wave=24, waves=40, spread=0.1, ring=36, think=(0.2, 0.55), rate=0.58, arc=-1),
]


class BossFrames:

    def __init__(self):
        n = int(256 * BOSS_SCALE)
        self.ax, self.ay = int(BOSS_ANCHOR[0] * BOSS_SCALE), int(BOSS_ANCHOR[1] * BOSS_SCALE)
        self.walk = self._sheet("Boss_Samurai_Walk.png", 8, n)
        self.melee = self._sheet("Boss_Samurai_MeleeAttack.png", 8, n)
        self.ranged = self._sheet("Boss_Samurai_RangedAttack.png", 8, n)
        self.intro = self._sheet("Boss_Samurai_Intro.png", 1, n)[0]
        death = self._sheet("Boss_Samurai_Death.png", 2, n)
        self.death = death[0] + death[1]         

    @staticmethod
    def _sheet(name, rows, n):
        img = pygame.image.load(asset(name)).convert_alpha()
        return [[pygame.transform.smoothscale(img.subsurface((c * 256, r * 256, 256, 256)), (n, n))
                 for c in range(24)] for r in range(rows)]


class SwordWave:
    def __init__(self, pos, direction, dmg, speed=2.4):
        self.pos, self.vel = V2(pos), V2(direction) * speed
        self.dmg, self.life, self.dead, self.reflected = dmg, 160, False, False

    @property
    def rect(self):
        return pygame.Rect(self.pos.x - 5, self.pos.y - 5, 10, 10)

    def update(self, world, boss):
        self.life -= 1
        self.pos += self.vel
        if self.life <= 0 or world.level.is_solid(*Physics.tile_of(self.pos)):
            self.dead = True
            return
        p = world.player
        if self.reflected:                                  
            if self.rect.colliderect(boss.rect):
                boss.take_damage(self.dmg * 3, self.vel.normalize(), world)
                self.dead = True
        elif self.rect.colliderect(p.rect):
            if p.parry_t > 0:
                self.vel, self.reflected = -self.vel * 1.3, True
                world.parried += 1
            elif p.hurt(self.dmg):
                self.dead = True

    def draw(self, surf, cam):
        c = self.pos - cam
        n = self.vel.normalize()
        side = V2(-n.y, n.x) * 7
        tail = c - n * 8
        col = (255, 150, 150) if self.reflected else (235, 240, 255)
        pygame.draw.line(surf, (120, 120, 160), tail - side * 0.6, tail + side * 0.6, 1)
        pygame.draw.line(surf, col, c - side, c + side, 3)
        pygame.draw.circle(surf, (255, 255, 255), (int(c.x), int(c.y)), 2)


class Boss(Entity):

    def __init__(self, game, pos):
        super().__init__(game, pos)
        st = game.stats
        self.mult = st.enemy_mult
        self.max_hp = BOSS_HP * self.mult
        self.phase = st.boss_phase                      
        self.hp = self.max_hp * (3 - self.phase) / 3
        self.state, self.t = ("chase", 0.0) if st.boss_seen else ("intro", 0.0)
        st.boss_seen = True
        self.flash = self.stun = self.since_hit = 0.0
        self.think = 1.0
        self.hit_done = self.fired = self.dying = self.dead = False
        self.atk_dir = V2(0, 1)
        self.waves = []

    @property
    def rect(self):
        return pygame.Rect(self.pos.x - 15, self.pos.y - 26, 30, 44)

    def _move(self, world, push):
        self.vel = (self.vel + push) * DRAG
        Physics.move_box(world.level, self.pos, self.vel, BOSS_BOX)

    def _row(self):
        ang = math.degrees(math.atan2(self.face.y, self.face.x)) % 360
        return min(BOSS_ROW_DEG, key=lambda r: abs((BOSS_ROW_DEG[r] - ang + 180) % 360 - 180))

    def take_damage(self, amount, knock, world):
        if self.state in ("intro", "transition", "dying"):
            return
        if self.state == "stagger":
            amount *= 1.5                                 
        self.hp -= amount
        self.flash, self.since_hit = 0.08, 0.0
        self.vel += knock * 0.4
        floor = self.max_hp * (2 - self.phase) / 3       
        if self.hp > floor:
            return
        if self.phase < 2:
            self.hp, self.phase = floor, self.phase + 1
            self.state, self.t, self.waves = "transition", 0.0, []
        else:
            self.hp, self.state, self.t = 0, "dying", 0.0
            self.dying, self.waves = True, []
            world.kills += 1
            world.gain(500, self.pos)

    def _stagger(self, world):
        self.state, self.stun, self.flash = "stagger", 1.6, 0.2
        self.vel -= self.atk_dir * 3
        world.parried += 1
        if self.game.stats.n("parry2"):
            self.take_damage(self.max_hp * 0.02, self.atk_dir, world)

    def _start_attack(self, kind):
        self.state, self.t = kind, 0.0
        self.hit_done = self.fired = False
        self.atk_dir = V2(self.face)

    def _melee_check(self, world, cfg, to_p, dist):
        p = world.player
        if dist >= MELEE_REACH:
            return
        if dist > 14 and self.atk_dir.dot(to_p / dist) < cfg["arc"]:
            return
        self.hit_done = True
        if p.parry_t > 0:
            self._stagger(world)
        elif p.hurt(cfg["melee"] * (1 + (self.mult - 1) * 0.3)):
            p.vel += self.atk_dir * 3

    def _fire(self, cfg):
        dmg = cfg["wave"] * (1 + (self.mult - 1) * 0.3)
        base = math.atan2(self.atk_dir.y, self.atk_dir.x)
        n = cfg["waves"]
        for i in range(n):
            a = base + (i - (n - 1) / 2) * cfg["spread"]
            self.waves.append(SwordWave(self.pos + self.atk_dir * 14, V2(math.cos(a), math.sin(a)), dmg))
        for i in range(cfg["ring"]):
            a = 2 * math.pi * i / cfg["ring"] + 0.1
            self.waves.append(SwordWave(self.pos, V2(math.cos(a), math.sin(a)), dmg, speed=1.6))

    def update(self, world):
        dt = 1 / FPS
        p = world.player
        to_p = p.pos - self.pos
        dist = to_p.length()
        self.flash = max(0.0, self.flash - dt)
        self.since_hit += dt
        for w in self.waves:
            w.update(world, self)
        self.waves = [w for w in self.waves if not w.dead]
        cfg = BOSS_PHASES[self.phase]

        if self.state == "dying":
            self.t += 0.4
            self.dead = self.t >= 47
            return
        if self.state in ("intro", "transition"):
            self._move(world, V2())
            self.t += 0.35
            if self.t >= 23:
                self.state, self.t, self.think = "chase", 0.0, 0.6
            return
        if self.state == "stagger":
            self._move(world, V2())
            self.stun -= dt
            if self.stun <= 0:
                self.state, self.think = "chase", 0.4
            return

        if self.state == "chase":
            direction = to_p / dist if dist else V2()
            if dist:
                self.face = V2(direction)
            self._move(world, direction * cfg["accel"])
            self.anim += 0.35
            self.think -= dt
            if self.think <= 0 and dist:
                self._start_attack("melee" if dist < MELEE_REACH + 14 else "ranged")
        else:                                              
            melee = self.state == "melee"
            if self.t < (6 if melee else 12) and dist:     
                self.atk_dir = to_p / dist
                self.face = V2(self.atk_dir)
            self.t += cfg["rate"]
            frame = int(self.t)
            self._move(world, self.atk_dir * 0.5 if melee and 4 <= frame <= 8 else V2())   
            if melee and not self.hit_done and MELEE_HIT[0] <= frame <= MELEE_HIT[1]:
                self._melee_check(world, cfg, to_p, dist)
            if not melee and not self.fired and frame >= RANGED_FIRE:
                self.fired = True
                self._fire(cfg)
            if self.t >= 23:
                self.state, self.think = "chase", random.uniform(*cfg["think"])

        if self.phase < 2 and self.since_hit > 5:          
            self.hp = min(self.max_hp * (3 - self.phase) / 3, self.hp + 12 * dt)

    def draw(self, surf, cam):
        f = self.game.assets.boss
        row = self._row()
        if self.state == "dying":
            img = f.death[min(47, int(self.t))]
        elif self.state in ("intro", "transition"):
            img = f.intro[min(23, int(self.t))]
        elif self.state == "melee":
            img = f.melee[row][min(23, int(self.t))]
        elif self.state == "ranged":
            img = f.ranged[row][min(23, int(self.t))]
        else:
            img = f.walk[row][int(self.anim) % 24 if self.state == "chase" else 0]
        if self.flash > 0 or self.state == "stagger":
            img = img.copy()
            img.fill((120, 120, 40) if self.state == "stagger" and self.flash <= 0 else (150, 150, 150),
                     special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(img, (self.pos.x - f.ax - cam.x, self.pos.y - f.ay - cam.y))
        for w in self.waves:
            w.draw(surf, cam)


class UI:
    def __init__(self, game):
        self.game = game
        self.a = game.assets

    def text(self, s, font, color, pos, center=False, shadow=True):
        img = font.render(s, True, color)
        r = img.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        if shadow:
            self.game.screen.blit(font.render(s, True, (0, 0, 0)), r.move(2, 2))
        self.game.screen.blit(img, r)

    @staticmethod
    def wrap(s, font, width):
        lines, cur = [], ""
        for w in s.split():
            t = (cur + " " + w).strip()
            if font.size(t)[0] <= width:
                cur = t
            else:
                lines.append(cur)
                cur = w
        return lines + ([cur] if cur else [])

    def hud(self, world):
        g, a, p, st = self.game, self.a, world.player, self.game.stats
        scr = g.screen
        pygame.draw.rect(scr, (0, 0, 0), (14, 14, 236, 26))
        pygame.draw.rect(scr, (70, 20, 30), (18, 18, 228, 18))
        pygame.draw.rect(scr, (220, 50, 60), (18, 18, int(228 * max(0, p.hp) / p.max_hp), 18))
        self.text(f"{max(0, int(p.hp))}/{p.max_hp}", a.font_s, (255, 255, 255), (132, 27), center=True)
        self.text(f"Gold {st.gold}", a.font_m, (255, 215, 80), (16, 46))
        self.text(f"Run {st.deaths + 1}   Difficulty {st.difficulty + 1}", a.font_s, (210, 210, 210), (16, 74))
        if world.stage == "room":
            if world.cleared:
                msg = "Room cleared! Gates are open - grab the coin vault, then take the trapdoor."
            else:
                msg = f"Mob room - wave {max(1, world.wave)}/{len(world.wave_sizes)} - enemies left {len(world.enemies)}"
        elif world.stage == "maze":
            msg = f"Maze - good luck!"
        else:
            msg = f"Samurai boss - phase {world.boss.phase + 1}/3"
            b, bw = world.boss, 500
            bx = (SCREEN_W - bw) // 2
            pygame.draw.rect(scr, (0, 0, 0), (bx - 4, 22, bw + 8, 22))
            pygame.draw.rect(scr, (70, 20, 30), (bx, 26, bw, 14))
            pygame.draw.rect(scr, (200, 60, 60), (bx, 26, int(bw * max(0, b.hp) / b.max_hp), 14))
            for i in (1, 2):
                pygame.draw.line(scr, (255, 255, 255), (bx + bw * i // 3, 22), (bx + bw * i // 3, 44), 2)
        self.text(msg, a.font_s, (255, 255, 255), (SCREEN_W // 2, SCREEN_H - 20), center=True)
        slots = []
        if st.n("dash"):
            slots.append(("Q", "Dash", f"{p.dash_charges}/{st.dash_charges}", p.dash_charges == 0))
        if st.n("parry"):
            slots.append(("RMB", "Parry", "", p.parry_cd > 0))
        if st.n("potion") or p.potions:
            slots.append(("F", "Potion", str(p.potions), p.potions == 0))
        x = SCREEN_W - 70
        for key, name, extra, grey in slots:
            scr.blit(a.slot, (x, SCREEN_H - 130))
            self.text(name, a.font_s, (180, 180, 180) if grey else (255, 255, 255), (x + 27, SCREEN_H - 112), center=True)
            self.text(key, a.font_s, (255, 220, 120), (x + 27, SCREEN_H - 140), center=True)
            if extra:
                self.text(extra, a.font_s, (255, 255, 255), (x + 27, SCREEN_H - 88), center=True)
            x -= 64
        for pos, s, _ in world.popups:
            c = (pos - world.cam) * ZOOM
            self.text(s, a.font_s, (255, 220, 80), (c.x, c.y), center=True)

    def card(self, key, x, y, hover=False, afford=True):
        c, a, scr = CARDS[key], self.a, self.game.screen
        scr.blit(a.card_back[c.rarity], (x, y))
        if hover:
            pygame.draw.rect(scr, (255, 255, 255), (x - 3, y - 3, 176, 224), 3, border_radius=8)
        self.text(c.name, a.font_m, (255, 255, 255), (x + 85, y + 34), center=True)
        self.text(c.rarity.upper(), a.font_s, (20, 20, 20), (x + 85, y + 58), center=True, shadow=False)
        for i, line in enumerate(self.wrap(c.desc, a.font_s, 140)):
            self.text(line, a.font_s, (255, 255, 255), (x + 85, y + 88 + i * 18), center=True)
        self.text(f"{c.price} gold", a.font_m, (255, 235, 120) if afford else (255, 110, 110), (x + 85, y + 192), center=True)

    def victory(self):
        a, st = self.a, self.game.stats
        self.game.screen.fill((10, 20, 16))
        self.text("YOU ESCAPED", a.font_l, (120, 255, 150), (SCREEN_W // 2, 160), center=True)
        self.text(f"Deaths: {st.deaths}", a.font_m, (255, 255, 255), (SCREEN_W // 2, 240), center=True)
        self.text("The way out was never locked.", a.font_m, (200, 230, 210), (SCREEN_W // 2, 290), center=True)
        self.text(f"Press Enter for difficulty {st.difficulty + 2} (you keep your cards and gold).",
                  a.font_m, (255, 255, 255), (SCREEN_W // 2, 380), center=True)


class Shop:
    def __init__(self, game, world):
        self.game, self.world, self.ui = game, world, game.ui
        self.offers = game.stats.roll_offers()
        self.sold = set()
        self.refresh_cost = 20
        self.msg = ""
        self.card_rects = [pygame.Rect(300 + i * 190, 200, 170, 218) for i in range(3)]
        self.refresh_rect = pygame.Rect(300, 450, 220, 46)
        self.retry_rect = pygame.Rect(560, 450, 290, 46)

    def buy(self, i):
        st = self.game.stats
        if i >= len(self.offers) or i in self.sold:
            return
        card = CARDS[self.offers[i]]
        if st.gold < card.price:
            self.msg = "Not enough gold."
            return
        st.gold -= card.price
        st.owned[card.key] = st.n(card.key) + 1
        self.sold.add(i)
        self.msg = f"Bought {card.name}."

    def refresh(self):
        st = self.game.stats
        if st.gold < self.refresh_cost:
            self.msg = "Not enough gold to refresh."
            return
        st.gold -= self.refresh_cost
        self.refresh_cost += 10
        self.offers, self.sold = st.roll_offers(), set()

    def event(self, e):
        """True when the player wants to try again."""
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.card_rects):
                if r.collidepoint(e.pos):
                    self.buy(i)
            if self.refresh_rect.collidepoint(e.pos):
                self.refresh()
            return self.retry_rect.collidepoint(e.pos)
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.buy(e.key - pygame.K_1)
            elif e.key == pygame.K_r:
                self.refresh()
            return e.key in (pygame.K_RETURN, pygame.K_SPACE)
        return False

    def draw(self):
        a, ui, st, w, scr = self.game.assets, self.ui, self.game.stats, self.world, self.game.screen
        scr.fill((18, 14, 26))
        ui.text("YOU DIED", a.font_l, (230, 70, 80), (SCREEN_W // 2, 40), center=True)
        lines = [f"Stage: {STAGE_NAMES[w.stage]}", f"Kills: {w.kills}",
                 f"Coins picked up: {w.coins_got}", f"Gold earned this run: {w.gold_run}",
                 f"Parries: {w.parried}", f"Time: {int(w.time)}s", f"Deaths: {st.deaths}"]
        ui.text("This run", a.font_m, (255, 255, 255), (40, 130))
        for i, s in enumerate(lines):
            ui.text(s, a.font_s, (220, 220, 220), (40, 165 + i * 24))
        ui.text("Your cards", a.font_m, (255, 255, 255), (40, 350))
        for i, (k, n) in enumerate(st.owned.items()):
            ui.text(f"{CARDS[k].name} x{n}", a.font_s, RARITY_COLOR[CARDS[k].rarity], (40, 380 + i * 20))
        if not st.owned:
            ui.text("none yet", a.font_s, (150, 150, 150), (40, 380))
        ui.text(f"Gold: {st.gold}", a.font_m, (255, 215, 80), (300, 140))
        mp = pygame.mouse.get_pos()
        for i, k in enumerate(self.offers):
            r = self.card_rects[i]
            if i in self.sold:
                pygame.draw.rect(scr, (40, 34, 52), r, border_radius=8)
                ui.text("SOLD", a.font_m, (150, 150, 150), r.center, center=True)
            else:
                ui.card(k, r.x, r.y, hover=r.collidepoint(mp), afford=st.gold >= CARDS[k].price)
                ui.text(f"[{i + 1}]", a.font_s, (255, 255, 255), (r.x + 10, r.y + 184))
        for r, label, ok in ((self.refresh_rect, f"Refresh shop ({self.refresh_cost})  [R]", st.gold >= self.refresh_cost),
                             (self.retry_rect, "Try again  [Enter]", True)):
            pygame.draw.rect(scr, (70, 60, 100) if r.collidepoint(mp) else (46, 38, 70), r, border_radius=8)
            pygame.draw.rect(scr, (255, 255, 255) if ok else (110, 110, 110), r, 2, border_radius=8)
            ui.text(label, a.font_m, (255, 255, 255) if ok else (140, 140, 140), r.center, center=True)
        if self.msg:
            ui.text(self.msg, a.font_s, (255, 230, 150), (300, 515))


class Game:
    def __init__(self):
        print("A: pygame.init", flush=True)
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Dungeon Crawler")
        self.clock = pygame.time.Clock()
        self.view = pygame.Surface((VIEW_W, VIEW_H))
        print("B: loading assets", flush=True)
        self.assets = Assets()
        print("C: assets done", flush=True)
        self.stats = Stats()
        self.ui = UI(self)
        self.stage = "room"
        print("D: building world", flush=True)
        self.world = World(self, self.stage)
        print("E: world done", flush=True)
        self.mode = "play"
        self.shop = None
        self.show_boxes = False
        self.running = True

    def handle_play_event(self, e):
        p = self.world.player
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_q:
                p.dash()
            elif e.key == pygame.K_f:
                p.use_potion()
            elif e.key == pygame.K_h:
                self.show_boxes = not self.show_boxes
            elif e.key == pygame.K_k:
                p.hp = 0
            elif e.key == pygame.K_b:          
                self.stage = "boss"
                self.restart_stage()
            elif e.key == pygame.K_EQUALS:
                p.max_hp = 99999999
                p.hp = 99999999
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
            p.parry()

    def restart_stage(self):
        self.world = World(self, self.stage)
        self.mode = "play"

    def on_death(self):
        w = self.world
        self.stats.deaths += 1
        if self.stage == "boss":
            ph = w.boss.phase                  
            self.stats.boss_phase = ph if (ph < 2 or not LAST_PHASE_RESETS) else 0
        self.shop = Shop(self, w)
        self.mode = "shop"

    def update_play(self):
        w = self.world
        w.update(pygame.key.get_pressed())
        w.draw(self.view, self.show_boxes)
        pygame.transform.scale(self.view, (SCREEN_W, SCREEN_H), self.screen)
        self.ui.hud(w)
        if w.won:
            if self.stage == "room":
                self.stage = "maze"
                self.restart_stage()
            elif self.stage == "maze":
                self.stage = "boss"
                self.restart_stage()
            else:
                self.mode = "win"
        elif w.player.hp <= 0:
            self.on_death()

    async def run(self):
        while self.running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    self.running = False
                elif self.mode == "play":
                    self.handle_play_event(e)
                elif self.mode == "shop":
                    if self.shop.event(e):
                        self.restart_stage()
                elif self.mode == "win" and e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.stats.difficulty += 1
                    self.stats.boss_phase = 0
                    self.stats.boss_seen = False
                    self.stage = "room"
                    self.restart_stage()
            if self.mode == "play":
                self.update_play()
            elif self.mode == "shop":
                self.shop.draw()
            else:
                self.ui.victory()
            pygame.display.flip()
            self.clock.tick(FPS)
            await asyncio.sleep(0)
        pygame.quit()


async def main():
    print("STEP 1: creating game", flush=True)
    try:
        game = Game()
        print("STEP 2: game created, entering loop", flush=True)
        await game.run()
    except Exception:
        err = traceback.format_exc()
        print(err, flush=True)
        # show the error on the canvas too
        pygame.init()
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        font = pygame.font.Font(None, 22)
        lines = err.splitlines()[-18:]
        while True:
            for e in pygame.event.get():
                pass
            screen.fill((30, 0, 0))
            for i, line in enumerate(lines):
                screen.blit(font.render(line[:110], True, (255, 255, 255)), (10, 10 + i * 24))
            pygame.display.flip()
            await asyncio.sleep(0)

asyncio.run(main())