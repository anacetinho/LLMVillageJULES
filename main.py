# Pygame Village Life Tech Demo
# Main application file for a top-down sprite-based game with AI-driven NPCs.
# Implements core game loop, character control, NPC AI integration via webhooks,
# and various game mechanics as per requirements.

import pygame
import datetime
import time
import uuid
import requests # For AI webhook calls
import json # For AI payload

# --- Core Configuration Constants ---
AI_THINKING_INTERVAL = 30000       # Milliseconds: Interval for NPC periodic AI thinking.
STARVATION_DAMAGE_INTERVAL = 1800000 # Milliseconds: Game time equivalent for 30 game minutes for starvation damage.
GAME_DAY_DURATION = 3600000         # Milliseconds: Real-world duration of one full game day (24 game hours).

# --- Display Settings ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
ASPECT_RATIO = 16 / 9.0 # Ensure float division
FPS = 60

# --- Colors ---
# Standard colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
GREY = (128, 128, 128)
BROWN = (165, 42, 42)
DARK_GREEN = (0, 100, 0)

DAY_COLOR = (100, 149, 237) # Cornflower Blue
NIGHT_COLOR = (25, 25, 112) # Midnight Blue
NIGHT_TINT_COLOR = (0, 0, 0, 100) # Semi-transparent black for night tint

BUILDING_LABEL_COLOR = BLACK
BUTTON_COLOR_OFF = RED
BUTTON_COLOR_ON = GREEN
LEVER_COLOR_OFF = GREY
LEVER_COLOR_ON = YELLOW


# --- Game Elements Sizes and Positions ---
BUILDING_WIDTH = 150
BUILDING_HEIGHT = 100
TREE_RADIUS = 20
CLUSTER_PADDING = 5 # Padding between trees in a cluster

# Map object definitions (x, y, width, height or radius)
# Coordinates are top-left
MAP_ELEMENTS = {
    "cantina": {"rect": pygame.Rect(SCREEN_WIDTH - BUILDING_WIDTH - 50, SCREEN_HEIGHT - BUILDING_HEIGHT - 50, BUILDING_WIDTH, BUILDING_HEIGHT), "color": BROWN, "label": "Cantina"},
    "hospital": {"rect": pygame.Rect(50, SCREEN_HEIGHT - BUILDING_HEIGHT - 50, BUILDING_WIDTH, BUILDING_HEIGHT), "color": WHITE, "label": "Hospital"},
    "tree_cluster": [ # Top-right section
        {"rect": pygame.Rect(SCREEN_WIDTH - 150, 100, TREE_RADIUS*2, TREE_RADIUS*2), "color": DARK_GREEN, "label": "Tree"},
        {"rect": pygame.Rect(SCREEN_WIDTH - 100, 80, TREE_RADIUS*2, TREE_RADIUS*2), "color": DARK_GREEN, "label": "Tree"},
        {"rect": pygame.Rect(SCREEN_WIDTH - 130, 150, TREE_RADIUS*2, TREE_RADIUS*2), "color": DARK_GREEN, "label": "Tree"},
        {"rect": pygame.Rect(SCREEN_WIDTH - 80, 140, TREE_RADIUS*2, TREE_RADIUS*2), "color": DARK_GREEN, "label": "Tree"},
        {"rect": pygame.Rect(SCREEN_WIDTH - 180, 120, TREE_RADIUS*2, TREE_RADIUS*2), "color": DARK_GREEN, "label": "Tree"},
    ],
    "game_end_button": {"rect": pygame.Rect(SCREEN_WIDTH // 2 - 50, 20, 100, 40), "color": BUTTON_COLOR_OFF, "label_on": "End Game (ON)", "label_off": "End Game (OFF)", "state": False, "type": "button"}, # State: False=Off, True=On
    "bob_spawn_lever": {"rect": pygame.Rect(SCREEN_WIDTH // 2 - 50, 70, 100, 40), "color": LEVER_COLOR_OFF, "label_on": "Spawn Bob (ON)", "label_off": "Spawn Bob (OFF)", "state": False, "type": "lever"}, # State: False=Off, True=On
}


# --- Game State ---
session_id = ""
game_time_seconds = 0  # Game time in seconds since start of day (0 to 86400)
real_time_start_ns = 0 # Real time when the game day started, in nanoseconds
game_should_end_at_real_time_ns = -1 # Real time in nanoseconds when the game should end, -1 if not set

# --- Font Initialization ---
pygame.font.init() # Explicitly initialize font module
UI_FONT_SIZE = 24
UI_FONT = pygame.font.Font(None, UI_FONT_SIZE)
BUILDING_FONT_SIZE = 20
BUILDING_FONT = pygame.font.Font(None, BUILDING_FONT_SIZE)

# --- Player Constants ---
PLAYER_SIZE = 30
PLAYER_COLOR = BLUE
PLAYER_SPEED = 5

# --- NPC Constants ---
NPC_SIZE = 30
NPC_SPEED = 2
NPC_COLOR_ALICE = (255, 105, 180) # Pink
NPC_COLOR_BOB = (0, 128, 128) # Teal
NPC_MAX_HP = 10
NPC_MAX_ENERGY = 10
NPC_ENERGY_DECREASE_RATE = 0.01
NPC_STARVATION_DAMAGE = 1
NPC_STARVATION_INTERVAL_GAME_SECONDS = 30 * 60
BOB_DESPAWN_TIME_REAL_SECONDS = 180
NPC_LOW_ENERGY_THRESHOLD = 2
NPC_LOW_HP_THRESHOLD = 5
HEAL_RATE_HP_PER_SECOND = 0.1
ENERGY_REGEN_RATE_PER_SECOND = 0.1
PLAYER_ATTACK_DAMAGE = 1
NPC_TARGET_REACH_THRESHOLD = 10

# UI Constants for Health/Energy Bars
BAR_WIDTH = NPC_SIZE
BAR_HEIGHT = 5
HP_BAR_COLOR = GREEN
ENERGY_BAR_COLOR = BLUE
BAR_BACKGROUND_COLOR = GREY
UI_BORDER_COLOR = BLACK

# --- Game Mechanics Constants ---
PLAYER_ATTACK_DAMAGE = 1
NPC_TARGET_REACH_THRESHOLD = 10 # Pixels: How close an NPC needs to be to a target to consider it "reached".


# --- Helper Functions ---
def generate_session_id():
    """Generates a unique session ID based on the current date and time of game start."""
    now = datetime.datetime.now()
    return f"session_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

def real_seconds_to_game_seconds(real_seconds):
    """Converts real-world seconds to game-world seconds."""
    # 24 game hours = 60 real minutes
    # 1 game hour = 2.5 real minutes
    # 1 game second = 2.5 / 60 real minutes = 2.5 * 60 / 60 real seconds = 2.5 real seconds
    # So, game_seconds = real_seconds / 2.5 is incorrect.
    # 1 real minute = 24/60 game hours = 0.4 game hours = 0.4 * 3600 game seconds = 1440 game seconds
    # 1 real second = 1440 / 60 = 24 game seconds
    return real_seconds * 24 # 1 real second = 24 game seconds

def get_formatted_game_time(total_game_seconds):
    """Formats total game seconds (0-86399) into HH:MM string."""
    hours = int(total_game_seconds // 3600) % 24
    minutes = int((total_game_seconds % 3600) // 60)
    return f"{hours:02d}:{minutes:02d}"

def is_night(total_game_seconds):
    """Determines if it's night time in the game (e.g., 8 PM to 6 AM)."""
    hour = (total_game_seconds // 3600) % 24
    return hour >= 20 or hour < 6 # Night is 8 PM (20:00) to 6 AM (06:00)

# --- Drawing Functions ---
def draw_map_elements(screen):
    """Draws all static map elements like buildings and trees."""
    # Draw buildings
    cantina = MAP_ELEMENTS["cantina"]
    pygame.draw.rect(screen, cantina["color"], cantina["rect"])
    label_surface = BUILDING_FONT.render(cantina["label"], True, BUILDING_LABEL_COLOR)
    screen.blit(label_surface, (cantina["rect"].x + 5, cantina["rect"].y + 5))

    hospital = MAP_ELEMENTS["hospital"]
    pygame.draw.rect(screen, hospital["color"], hospital["rect"])
    label_surface = BUILDING_FONT.render(hospital["label"], True, BUILDING_LABEL_COLOR)
    screen.blit(label_surface, (hospital["rect"].x + 5, hospital["rect"].y + 5))

    # Draw trees
    for tree in MAP_ELEMENTS["tree_cluster"]:
        pygame.draw.circle(screen, tree["color"], tree["rect"].center, TREE_RADIUS)
        # Basic trunk
        trunk_rect = pygame.Rect(tree["rect"].centerx - TREE_RADIUS // 4, tree["rect"].centery + TREE_RADIUS - 2, TREE_RADIUS // 2, TREE_RADIUS)
        pygame.draw.rect(screen, BROWN, trunk_rect)


    # Draw game end button
    button = MAP_ELEMENTS["game_end_button"]
    button_color = BUTTON_COLOR_ON if button["state"] else BUTTON_COLOR_OFF
    button_label_text = button["label_on"] if button["state"] else button["label_off"]
    pygame.draw.rect(screen, button_color, button["rect"])
    label_surface = UI_FONT.render(button_label_text, True, BLACK)
    label_rect = label_surface.get_rect(center=button["rect"].center)
    screen.blit(label_surface, label_rect)

    # Draw Bob spawn lever
    lever = MAP_ELEMENTS["bob_spawn_lever"]
    lever_color = LEVER_COLOR_ON if lever["state"] else LEVER_COLOR_OFF
    lever_label_text = lever["label_on"] if lever["state"] else lever["label_off"]
    pygame.draw.rect(screen, lever_color, lever["rect"])
    label_surface = UI_FONT.render(lever_label_text, True, BLACK)
    label_rect = label_surface.get_rect(center=lever["rect"].center)
    screen.blit(label_surface, label_rect)

# --- Player Class ---
class Player:
    """Represents the human-controlled player character."""
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, PLAYER_SIZE, PLAYER_SIZE)
        self.color = PLAYER_COLOR
        self.speed = PLAYER_SPEED

    def move(self, dx, dy, game_map_elements):
        """
        Moves the player by dx, dy considering collisions with map elements.
        Collision detection is done separately for X and Y axes to allow sliding.
        """
        new_x = self.rect.x + dx * self.speed
        new_y = self.rect.y + dy * self.speed

        # Create a temporary rect for collision detection
        temp_rect = self.rect.copy()
        temp_rect.x = new_x

        # Check X-axis collision
        can_move_x = True
        for key, element in game_map_elements.items():
            if key == "tree_cluster": # Trees are a list
                for tree_obj in element:
                    if temp_rect.colliderect(tree_obj["rect"]):
                        can_move_x = False
                        break
                if not can_move_x: break
            elif "rect" in element and temp_rect.colliderect(element["rect"]):
                 can_move_x = False
                 break

        if can_move_x:
            self.rect.x = new_x

        temp_rect.x = self.rect.x # Reset x to its current or newly updated position
        temp_rect.y = new_y

        # Check Y-axis collision
        can_move_y = True
        for key, element in game_map_elements.items():
            if key == "tree_cluster":
                for tree_obj in element:
                    if temp_rect.colliderect(tree_obj["rect"]):
                        can_move_y = False
                        break
                if not can_move_y: break
            elif "rect" in element and temp_rect.colliderect(element["rect"]):
                can_move_y = False
                break

        if can_move_y:
            self.rect.y = new_y


        # Boundary checks for screen
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH:
            self.rect.right = SCREEN_WIDTH
        if self.rect.top < 0:
            self.rect.top = 0
        if self.rect.bottom > SCREEN_HEIGHT:
            self.rect.bottom = SCREEN_HEIGHT


    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)

    def interact_or_attack(self, key_type, game):
        """Handles player interactions based on key presses ('U', 'P', 'E')."""
        # 'game' is the Game instance, providing access to map_elements and npcs
        print(f"Player action: {key_type}")
        if key_type == 'U': # Use an object (button, lever)
            interaction_rect = self.rect.inflate(20, 20) # Define interaction range

            button = game.map_elements["game_end_button"]
            if interaction_rect.colliderect(button["rect"]):
                button["state"] = not button["state"]
                print(f"Player toggled Game End Button to: {button['state']}")
                if button["state"]:
                    game.game_should_end_at_real_time_ns = time.monotonic_ns() + 60 * 1_000_000_000
                    print(f"Game will end in 60 seconds.")
                else:
                    game.game_should_end_at_real_time_ns = -1
                    print(f"Game end timer cancelled.")
                button["color"] = BUTTON_COLOR_ON if button["state"] else BUTTON_COLOR_OFF
                return # Prioritize one interaction per key press

            lever = game.map_elements["bob_spawn_lever"]
            if interaction_rect.colliderect(lever["rect"]):
                lever["state"] = not lever["state"]
                print(f"Player toggled Bob Spawn Lever to: {lever['state']}")
                # Bob spawning logic will be added later
                lever["color"] = LEVER_COLOR_ON if lever["state"] else LEVER_COLOR_OFF
                return

        elif key_type == 'P': # Attack
            # Define an attack range, e.g., a small rectangle in front of the player
            attack_range_rect = self.rect.copy()
            # Assuming player faces right for now, extend rect to the right
            # This will need directional facing later
            attack_range_rect.width += 20 # Attack 20 pixels in front

            # A more robust way would be to check direction player is facing
            # For now, simple overlap with player's slightly extended rect
            attack_interaction_rect = self.rect.inflate(40,40) # Larger area for attack check

            for npc in game.npcs:
                if npc.is_active and attack_interaction_rect.colliderect(npc.rect):
                    # Check if NPC is roughly in front - this is very basic
                    # A better way would be to use player's direction
                    if abs(self.rect.centery - npc.rect.centery) < self.rect.height: # roughly same horizontal plane
                        npc.hp -= PLAYER_ATTACK_DAMAGE
                        npc.last_damage_source = "player"
                        npc.hp = max(0, npc.hp)
                        damage_msg = f"Player attacked {npc.name}. HP: {npc.hp}"
                        print(damage_msg)
                        game.add_to_comm_log(damage_msg, PLAYER_COLOR) # Log player attack
                        if npc.hp <= 0:
                            death_msg = f"{npc.name} has been defeated by the player."
                            print(death_msg)
                            game.add_to_comm_log(death_msg, PLAYER_COLOR)
                            npc.is_active = False
                        npc.trigger_ai_call(event_type="attacked",
                                            event_data={"attacker_name": "Player",
                                                        "damage_taken": PLAYER_ATTACK_DAMAGE,
                                                        "new_hp": npc.hp})
                        return
            print("Player attack: No target in range or line of sight.")

        elif key_type == 'E': # Talk
            interaction_rect = self.rect.inflate(PLAYER_SIZE * 1.5, PLAYER_SIZE * 1.5)
            closest_npc = None
            min_dist_sq = float('inf')

            for npc in game.npcs:
                if npc.is_active and interaction_rect.colliderect(npc.rect):
                    dist_sq = (self.rect.centerx - npc.rect.centerx)**2 + (self.rect.centery - npc.rect.centery)**2
                    if dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        closest_npc = npc

            if closest_npc:
                talk_init_msg = f"Player attempts to talk to {closest_npc.name}"
                print(talk_init_msg)
                game.add_to_comm_log(talk_init_msg, PLAYER_COLOR) # Log player initiating talk

                # For now, player doesn't "say" a specific message via input.
                # The AI of the NPC is triggered that player wants to talk.
                # The AI can then respond with a speech bubble.
                closest_npc.trigger_ai_call(event_type="player_interaction",
                                            event_data={"interaction_type": "talk",
                                                        "initiator_name": "Player",
                                                        "message": ""}) # Empty message from player for now
            else:
                print("Player E press: No NPC in range to talk to.")
            return

# --- NPC Classes ---
class NPC:
    """Base class for Non-Player Characters (NPCs) like Alice and Bob."""
    def __init__(self, x, y, name, color, game_ref):
        self.rect = pygame.Rect(x, y, NPC_SIZE, NPC_SIZE) # NPC's position and size
        self.name = name        # NPC's unique name
        self.color = color      # Color for drawing the NPC
        self.speed = NPC_SPEED
        self.hp = NPC_MAX_HP
        self.energy = NPC_MAX_ENERGY
        self.last_damage_source = None
        self.current_goal = "Idle" # Examples: "Idle", "Seeking Food", "Seeking Healing", "MovingToTarget"
        self.action_queue = []
        self.game = game_ref

        self.last_energy_decrease_time_gs = 0
        self.last_starvation_damage_time_gs = 0
        self.is_active = True
        self.target_position = None # For movement, (x,y)
        self.last_regen_time_real_s = time.monotonic() # For HP/Energy regen
        self.last_ai_think_time_ms = pygame.time.get_ticks()
        self.webhook_url = None
        self.ai_error_message = None
        self.current_action_finish_time_ms = 0 # Real-time ms: When current blocking action (e.g. wait) finishes.

    def update(self, game_map_elements, current_game_seconds_total, delta_real_time_seconds):
        """
        Updates the NPC's state including AI thinking, status effects, goal management,
        movement, and action queue processing.
        'delta_real_time_seconds' is used for real-time based regeneration.
        """
        if not self.is_active:
            return

        current_real_time_ms = pygame.time.get_ticks() # Current real time in milliseconds

        # --- AI Thinking (Periodic) ---
        if self.webhook_url and (current_real_time_ms - self.last_ai_think_time_ms > AI_THINKING_INTERVAL):
            print(f"{self.name} is thinking... (periodic)")
            self.trigger_ai_call("periodic_update")
            self.last_ai_think_time_ms = current_real_time_ms

        # --- Status Effects and Needs ---
        # Energy decrease
        if current_game_seconds_total - self.last_energy_decrease_time_gs >= 1: # Update every game second passed
            elapsed_gs = current_game_seconds_total - self.last_energy_decrease_time_gs
            self.energy -= NPC_ENERGY_DECREASE_RATE * elapsed_gs
            self.energy = max(0, self.energy)
            self.last_energy_decrease_time_gs = current_game_seconds_total

        # Starvation damage
        if self.energy == 0:
            if current_game_seconds_total - self.last_starvation_damage_time_gs >= NPC_STARVATION_INTERVAL_GAME_SECONDS:
                self.hp -= NPC_STARVATION_DAMAGE
                self.last_damage_source = "starvation"
                self.hp = max(0, self.hp)
                self.last_starvation_damage_time_gs = current_game_seconds_total
                print(f"{self.name} took starvation damage. HP: {self.hp}")
                if self.hp <= 0:
                    print(f"{self.name} has perished from starvation.")
                    self.is_active = False # Handle death
                    return # Stop further updates if dead

        # --- Goal Management (Simple version, AI will override later) ---
        if not self.target_position: # Only set new goal if not already moving to a target
            if self.energy < NPC_LOW_ENERGY_THRESHOLD and self.current_goal != "Seeking Food":
                self.current_goal = "Seeking Food"
                self.target_position = MAP_ELEMENTS["cantina"]["rect"].center
                print(f"{self.name} is now seeking food at the Cantina.")
            elif self.hp < NPC_LOW_HP_THRESHOLD and self.current_goal != "Seeking Healing":
                self.current_goal = "Seeking Healing"
                self.target_position = MAP_ELEMENTS["hospital"]["rect"].center
                print(f"{self.name} is now seeking healing at the Hospital.")

        # --- Movement towards Target ---
        if self.target_position:
            dx, dy = 0, 0
            target_x, target_y = self.target_position
            if abs(self.rect.centerx - target_x) > NPC_TARGET_REACH_THRESHOLD:
                dx = 1 if target_x > self.rect.centerx else -1
            if abs(self.rect.centery - target_y) > NPC_TARGET_REACH_THRESHOLD:
                dy = 1 if target_y > self.rect.centery else -1

            if dx != 0 or dy != 0:
                self.move(dx, dy, game_map_elements)
            else: # Reached target
                print(f"{self.name} reached target: {self.current_goal} at {self.target_position}")
                self.target_position = None # Clear target
                # Current goal remains until condition met (e.g. full HP/Energy) or new goal from AI

        # --- Healing and Eating ---
        current_real_time_s = time.monotonic()
        delta_s_for_regen = current_real_time_s - self.last_regen_time_real_s

        if self.current_goal == "Seeking Healing" and self.rect.colliderect(MAP_ELEMENTS["hospital"]["rect"]):
            self.hp += HEAL_RATE_HP_PER_SECOND * delta_s_for_regen
            self.hp = min(self.hp, NPC_MAX_HP)
            # print(f"{self.name} is healing. HP: {self.hp:.1f}") # Debug
            if self.hp >= NPC_MAX_HP:
                self.current_goal = "Idle"
                print(f"{self.name} is fully healed.")

        if self.current_goal == "Seeking Food" and self.rect.colliderect(MAP_ELEMENTS["cantina"]["rect"]):
            self.energy += ENERGY_REGEN_RATE_PER_SECOND * delta_s_for_regen
            self.energy = min(self.energy, NPC_MAX_ENERGY)
            # print(f"{self.name} is eating. Energy: {self.energy:.1f}") # Debug
            if self.energy >= NPC_MAX_ENERGY:
                self.current_goal = "Idle"
                print(f"{self.name} is full of energy.")

        self.last_regen_time_real_s = current_real_time_s


        # --- Action Queue Processing ---
        current_time_ms = pygame.time.get_ticks()
        if current_time_ms >= self.current_action_finish_time_ms: # Ready for next action or continue current
            if not self.target_position and self.action_queue: # Not moving and queue has actions
                action_data = self.action_queue.pop(0)
                print(f"[{get_formatted_game_time(self.game.game_time_seconds)}] {self.name} processing action: {action_data}")
                self.execute_action(action_data)
            elif self.target_position:
                # If moving, current_goal should reflect that, or be "Idle" if AI interrupted with move
                pass # Movement is handled in the "Movement towards Target" section.

    def execute_action(self, action_data):
        """
        Executes a single action from the AI's action queue.
        Actions can include movement, interaction with objects, waiting, or speaking.
        """
        action_type = action_data.get("type")
        params = action_data.get("parameters", {})

        if action_type == "move_to_coordinates":
            x = params.get("x")
            y = params.get("y")
            if x is not None and y is not None:
                self.target_position = (int(x), int(y))
                self.current_goal = f"Moving to ({x},{y}) via AI" # Update goal
                print(f"{self.name} AI action: Move to ({x},{y})")
            else:
                print(f"{self.name} AI Error: move_to_coordinates missing x or y.")

        elif action_type == "toggle_game_end_button": # Simplified: just toggle
            button = self.game.map_elements["game_end_button"]
            current_state = button["state"]
            desired_state_str = params.get("state", "toggle") # "on", "off", or "toggle"

            if desired_state_str == "toggle":
                button["state"] = not button["state"]
            elif desired_state_str == "on":
                button["state"] = True
            elif desired_state_str == "off":
                button["state"] = False
            else: # default to toggle if invalid state string
                 button["state"] = not button["state"]

            print(f"{self.name} AI action: Game End Button toggled to {button['state']}.")
            if button["state"]:
                self.game.game_should_end_at_real_time_ns = time.monotonic_ns() + 60 * 1_000_000_000
                print(f"Game will end in 60 seconds due to {self.name}.")
            else:
                self.game.game_should_end_at_real_time_ns = -1
                print(f"Game end timer cancelled by {self.name}.")
            button["color"] = BUTTON_COLOR_ON if button["state"] else BUTTON_COLOR_OFF

        elif action_type == "toggle_bob_spawn_lever": # Simplified: just toggle
            lever = self.game.map_elements["bob_spawn_lever"]
            current_state = lever["state"]
            desired_state_str = params.get("state", "toggle") # "on", "off", or "toggle"

            if desired_state_str == "toggle":
                 lever["state"] = not lever["state"]
            elif desired_state_str == "on":
                lever["state"] = True
            elif desired_state_str == "off":
                lever["state"] = False
            else: # default to toggle
                lever["state"] = not lever["state"]

            print(f"{self.name} AI action: Bob Spawn Lever toggled to {lever['state']}.")
            lever["color"] = LEVER_COLOR_ON if lever["state"] else LEVER_COLOR_OFF
            # Bob spawn logic is handled in Game.handle_bob_spawn_logic() based on lever's state

        elif action_type == "wait":
            duration_ms = params.get("duration_ms", 1000) # Default 1 second
            self.current_action_finish_time_ms = pygame.time.get_ticks() + duration_ms
            print(f"{self.name} AI action: Wait for {duration_ms}ms.")

        elif action_type == "say":
            text = params.get("text", "")
            if text:
                print(f"{self.name} AI action (says): {text}")
                self.game.add_speech_bubble(self, text) # For visual bubble
                self.game.add_to_comm_log(f"{self.name}: {text}", self.color) # For log window

        elif action_type == "talk_to_npc":
            target_name = params.get("target_npc_name")
            message = params.get("message", "")
            if target_name and message:
                target_npc = self.game.get_npc_by_name(target_name)
                if target_npc and target_npc.is_active:
                    print(f"{self.name} AI sends message to {target_name}: '{message}'")
                    self.game.add_speech_bubble(self, f"@{target_name}: {message}") # Show speaker's bubble
                    self.game.add_to_comm_log(f"{self.name} to {target_name}: {message}", self.color)
                    # Trigger the target NPC's AI
                    target_npc.trigger_ai_call(
                        event_type="npc_interaction",
                        event_data={
                            "interaction_type": "talk",
                            "speaker_name": self.name,
                            "message": message
                        }
                    )
                else:
                    print(f"{self.name} AI Error: talk_to_npc failed, target '{target_name}' not found or inactive.")
                    self.game.add_to_comm_log(f"{self.name} tried to talk to {target_name} (failed).", self.color)
            else:
                print(f"{self.name} AI Error: talk_to_npc missing target_npc_name or message.")


        # TODO: Implement "follow_player" or "follow_npc"

        else:
            print(f"{self.name} received unknown AI action type: {action_type}")


    def get_ai_context_payload(self, event_type="unknown", event_data=None):
        """Prepares the JSON payload for the AI webhook."""
        player_state = {
            "x": self.game.player.rect.centerx,
            "y": self.game.player.rect.centery,
            # "hp": self.game.player.hp, # If player has HP
            # "energy": self.game.player.energy # If player has energy
        }

        other_npcs_state = []
        for npc in self.game.npcs:
            if npc is not self and npc.is_active:
                other_npcs_state.append({
                    "name": npc.name,
                    "x": npc.rect.centerx,
                    "y": npc.rect.centery,
                    "hp": npc.hp,
                    "energy": int(npc.energy),
                    "current_goal": npc.current_goal
                })

        # Fixed map elements locations (could be part of system prompt in N8N)
        # For now, sending them as part of context.
        fixed_elements_info = {
            "cantina_pos": MAP_ELEMENTS["cantina"]["rect"].center,
            "hospital_pos": MAP_ELEMENTS["hospital"]["rect"].center,
            "tree_cluster_coords": [tree["rect"].center for tree in MAP_ELEMENTS["tree_cluster"]],
            "game_end_button_pos": MAP_ELEMENTS["game_end_button"]["rect"].center,
            "bob_spawn_lever_pos": MAP_ELEMENTS["bob_spawn_lever"]["rect"].center
        }

        payload = {
            "session_id": self.game.session_id,
            "npc_name": self.name,
            "current_game_time": get_formatted_game_time(self.game.game_time_seconds),
            "is_night": is_night(self.game.game_time_seconds),
            "self_state": {
                "x": self.rect.centerx,
                "y": self.rect.centery,
                "hp": self.hp,
                "energy": int(self.energy),
                "current_goal": self.current_goal,
                "last_damage_source": self.last_damage_source,
                "action_queue_size": len(self.action_queue)
            },
            "player_state": player_state,
            "other_npcs_state": other_npcs_state,
            "game_world_state": {
                "game_end_button_on": self.game.map_elements["game_end_button"]["state"],
                "bob_spawn_lever_on": self.game.map_elements["bob_spawn_lever"]["state"],
                # "fixed_elements": fixed_elements_info # Can be large, consider if needed every time
            },
            "event_trigger": {
                "type": event_type, # e.g., "periodic_update", "player_talk", "attacked"
                "data": event_data # e.g., {"attacker": "player", "damage": 1} or {"speaker": "player", "message": "hello"}
            }
        }
        return payload

    def trigger_ai_call(self, event_type, event_data=None, retry_count=3):
        """
        Sends the current game context to the NPC's N8N webhook AI.
        Handles basic retry logic and error display for AI communication issues.
        'event_type' (e.g., "periodic_update", "attacked") and 'event_data' provide
        specifics about what triggered this AI call.
        """
        if not self.webhook_url:
            print(f"{self.name} has no webhook URL configured.")
            self.ai_error_message = "Webhook not configured."
            return

        payload = self.get_ai_context_payload(event_type, event_data)

        try:
            print(f"Sending payload to {self.name}'s AI ({self.webhook_url}): {json.dumps(payload, indent=2)}")
            # In a real threaded scenario, this should not block the main game loop.
            # For now, it's synchronous.
            response = requests.post(self.webhook_url, json=payload, timeout=10) # 10s timeout
            response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)

            ai_response_data = response.json()
            print(f"AI response for {self.name}: {ai_response_data}")
            self.ai_error_message = None # Clear previous error

            # Process AI response - e.g., add actions to queue
            if "actions" in ai_response_data and isinstance(ai_response_data["actions"], list):
                self.action_queue.extend(ai_response_data["actions"])
                # Extending allows AI to send multiple actions
            if "speech" in ai_response_data:
                # TODO: Implement speech bubble display
                print(f"{self.name} says: {ai_response_data['speech']}")
                self.game.add_speech_bubble(self, ai_response_data['speech'])


        except requests.exceptions.Timeout:
            print(f"Error: Timeout connecting to {self.name}'s AI webhook ({self.webhook_url}).")
            self.ai_error_message = "AI Timeout"
            if retry_count > 0:
                print(f"Retrying... ({retry_count} left)")
                time.sleep(1) # Simple delay before retry
                self.trigger_ai_call(event_type, event_data, retry_count - 1)
        except requests.exceptions.RequestException as e:
            print(f"Error: Failed to connect to {self.name}'s AI webhook ({self.webhook_url}): {e}")
            self.ai_error_message = f"AI Conn. Error"
            if retry_count > 0 and not (isinstance(e, requests.exceptions.HTTPError) and 400 <= e.response.status_code < 500): # Don't retry client errors
                print(f"Retrying... ({retry_count} left)")
                time.sleep(1)
                self.trigger_ai_call(event_type, event_data, retry_count - 1)
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON response from {self.name}'s AI.")
            self.ai_error_message = "AI Invalid JSON"


    def move(self, dx, dy, game_map_elements):
        if not self.is_active: return

        # Avoid collision with other NPCs (simple check, could be improved)
        # This part is tricky without a central collision manager or passing all other NPCs
        # For now, NPCs will only collide with map elements.

        new_x = self.rect.x + dx * self.speed
        new_y = self.rect.y + dy * self.speed

        temp_rect = self.rect.copy()
        temp_rect.x = new_x

        can_move_x = True
        for key, element in game_map_elements.items():
            if key == "tree_cluster":
                for tree_obj in element:
                    if temp_rect.colliderect(tree_obj["rect"]):
                        can_move_x = False; break
                if not can_move_x: break
            elif "rect" in element and temp_rect.colliderect(element["rect"]):
                 can_move_x = False; break

        if can_move_x: self.rect.x = new_x

        temp_rect.x = self.rect.x
        temp_rect.y = new_y

        can_move_y = True
        for key, element in game_map_elements.items():
            if key == "tree_cluster":
                for tree_obj in element:
                    if temp_rect.colliderect(tree_obj["rect"]):
                        can_move_y = False; break
                if not can_move_y: break
            elif "rect" in element and temp_rect.colliderect(element["rect"]):
                can_move_y = False; break

        if can_move_y: self.rect.y = new_y

        # Boundary checks
        self.rect.clamp_ip(self.game.screen.get_rect())


    def draw(self, screen):
        if not self.is_active:
            return
        pygame.draw.rect(screen, self.color, self.rect)

        # --- Draw Name ---
        name_text_surface = BUILDING_FONT.render(self.name, True, WHITE)
        name_pos_x = self.rect.centerx - name_text_surface.get_width() // 2
        name_pos_y = self.rect.top - name_text_surface.get_height() - BAR_HEIGHT * 2 - 5 # Position above bars
        screen.blit(name_text_surface, (name_pos_x, name_pos_y))

        # --- Draw HP Bar ---
        hp_bar_outer_rect = pygame.Rect(self.rect.left, self.rect.top - BAR_HEIGHT * 2 - 2, BAR_WIDTH, BAR_HEIGHT)
        pygame.draw.rect(screen, BAR_BACKGROUND_COLOR, hp_bar_outer_rect)
        current_hp_width = (self.hp / NPC_MAX_HP) * BAR_WIDTH
        hp_bar_inner_rect = pygame.Rect(self.rect.left, self.rect.top - BAR_HEIGHT*2 - 2, current_hp_width, BAR_HEIGHT)
        pygame.draw.rect(screen, HP_BAR_COLOR, hp_bar_inner_rect)
        pygame.draw.rect(screen, UI_BORDER_COLOR, hp_bar_outer_rect, 1) # Border

        # --- Draw Energy Bar ---
        energy_bar_outer_rect = pygame.Rect(self.rect.left, self.rect.top - BAR_HEIGHT - 1, BAR_WIDTH, BAR_HEIGHT)
        pygame.draw.rect(screen, BAR_BACKGROUND_COLOR, energy_bar_outer_rect)
        current_energy_width = (self.energy / NPC_MAX_ENERGY) * BAR_WIDTH
        energy_bar_inner_rect = pygame.Rect(self.rect.left, self.rect.top - BAR_HEIGHT -1, current_energy_width, BAR_HEIGHT)
        pygame.draw.rect(screen, ENERGY_BAR_COLOR, energy_bar_inner_rect)
        pygame.draw.rect(screen, UI_BORDER_COLOR, energy_bar_outer_rect, 1) # Border

        # Display AI error message if any
        if self.ai_error_message:
            error_surface = self.game.speech_font.render(self.ai_error_message, True, RED)
            error_pos_x = self.rect.centerx - error_surface.get_width() // 2
            error_pos_y = name_pos_y - error_surface.get_height() - 2 # Above name
            screen.blit(error_surface, (error_pos_x, error_pos_y))


class Alice(NPC):
    def __init__(self, x, y, game_ref):
        super().__init__(x, y, "Alice", NPC_COLOR_ALICE, game_ref)
        self.webhook_url = "http://localhost:5678/webhook/abc" # Alice's unique N8N webhook

class Bob(NPC):
    """Bob NPC: His existence is tied to a lever and a despawn timer."""
    def __init__(self, x, y, game_ref):
        super().__init__(x, y, "Bob", NPC_COLOR_BOB, game_ref)
        self.webhook_url = "http://localhost:5678/webhook/def" # Bob's unique N8N webhook
        self.despawn_timer_start_ns = -1 # Real time in nanoseconds when despawn timer began

    def start_despawn_timer(self):
        """Initiates Bob's despawn timer."""
        self.despawn_timer_start_ns = time.monotonic_ns()
        print(f"Bob's despawn timer started. He will disappear in {BOB_DESPAWN_TIME_REAL_SECONDS} seconds.")

    def update(self, game_map_elements, current_game_seconds_total, delta_real_time_seconds):
        """Updates Bob, including checking his despawn timer."""
        if not self.is_active:
            return
        super().update(game_map_elements, current_game_seconds_total, delta_real_time_seconds)

        # Check despawn timer if it's running
        if self.despawn_timer_start_ns != -1:
            elapsed_ns = time.monotonic_ns() - self.despawn_timer_start_ns
            if elapsed_ns >= BOB_DESPAWN_TIME_REAL_SECONDS * 1_000_000_000:
                print("Bob has despawned.")
                self.is_active = False
                self.despawn_timer_start_ns = -1 # Reset timer


# --- Main Game Class ---
class Game:
    """
    Manages the overall game state, game loop, entities (player, NPCs),
    map elements, UI, and time systems.
    """
    def __init__(self):
        self.session_id = generate_session_id() # Unique ID for this game session
        print(f"Session ID: {self.session_id}")

        # Timekeeping
        self.game_time_seconds = 0 # In-game seconds passed since start of current game day
        self.real_time_start_ns = time.monotonic_ns() # Real-world time when the game started (nanoseconds)
        self.last_real_time_ns = self.real_time_start_ns # Last frame's real-world time (nanoseconds)
        self.game_should_end_at_real_time_ns = -1 # Real-world timestamp (ns) to auto-end game, if set by button

        # Game elements state
        self.map_elements = MAP_ELEMENTS

        # Player
        self.player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2) # Start player in center

        # NPCs
        self.npcs = []
        self.alice = Alice(100, 100, self) # Pass game reference
        self.npcs.append(self.alice)

        self.bob = None # Bob may not exist initially
        self.bob_instance = None
        self.speech_bubbles = [] # List to store active speech bubbles: (npc_ref, text, creation_time_ms, surface)

        # Pygame setup
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(f"Tech Demo Game - {self.session_id}")
        self.clock = pygame.time.Clock()
        self.night_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.night_surface.fill(NIGHT_TINT_COLOR)

        self.font = UI_FONT
        self.speech_font = pygame.font.Font(None, 18)
        self.SPEECH_BUBBLE_DURATION_MS = 10000
        self.SPEECH_BUBBLE_COLOR = YELLOW
        self.SPEECH_TEXT_COLOR = BLACK

        # Communication Log
        self.comm_log = [] # List of (timestamp_str, message_str, color)
        self.show_comm_log = False
        self.COMM_LOG_MAX_LINES = 10
        self.COMM_LOG_FONT_SIZE = 16
        self.comm_log_font = pygame.font.Font(None, self.COMM_LOG_FONT_SIZE)
        self.COMM_LOG_POS = (10, SCREEN_HEIGHT - 200) # Bottom-leftish
        self.COMM_LOG_SIZE = (400, 150)
        self.COMM_LOG_BG_COLOR = (50, 50, 50, 200) # Semi-transparent dark grey
        self.COMM_LOG_TEXT_COLOR = WHITE


    def run(self):
        """Main game loop. Handles events, updates game state, and renders the screen."""
        running = True
        while running:
            # --- Event Handling ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                # MOUSEBUTTONDOWN is removed as player uses 'U' key now for interactions
                # if event.type == pygame.MOUSEBUTTONDOWN:
                #     if event.button == 1:
                #         self.handle_click(event.pos) # This was for direct click on button/lever
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_e:
                        self.player.interact_or_attack('E', self)
                    elif event.key == pygame.K_p:
                        self.player.interact_or_attack('P', self)
                    elif event.key == pygame.K_u:
                        self.player.interact_or_attack('U', self)
                    elif event.key == pygame.K_l: # Toggle Log
                        self.show_comm_log = not self.show_comm_log
                        print(f"Communication Log toggled: {'ON' if self.show_comm_log else 'OFF'}")

            # Player movement from key presses
            keys = pygame.key.get_pressed()
            dx, dy = 0, 0
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                dx = -1
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                dx = 1
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                dy = -1
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                dy = 1

            if dx != 0 or dy != 0:
                 # Pass self.map_elements for collision detection
                self.player.move(dx, dy, self.map_elements)

            # --- Game Logic ---
            # --- Game Logic ---
            current_real_time_ns = time.monotonic_ns() # Get it once for the frame
            delta_real_time_seconds_for_frame = (current_real_time_ns - self.last_real_time_ns) / 1_000_000_000.0

            self.update_time() # Updates game_time_seconds using self.last_real_time_ns
            self.handle_bob_spawn_logic()

            for npc in self.npcs:
                if npc.is_active:
                    npc.update(self.map_elements, self.game_time_seconds, delta_real_time_seconds_for_frame)

            if self.game_should_end_at_real_time_ns != -1 and current_real_time_ns >= self.game_should_end_at_real_time_ns:
                print("Game ending due to button timer.")
                running = False


            # --- Drawing ---
            self.screen.fill(DAY_COLOR)
            draw_map_elements(self.screen)
            self.player.draw(self.screen)
            for npc in self.npcs:
                if npc.is_active:
                    npc.draw(self.screen)

            # Draw speech bubbles
            current_time_ms = pygame.time.get_ticks()
            active_bubbles = []
            for i, bubble_data in enumerate(self.speech_bubbles):
                npc_ref, text_surface, creation_time, text_rect_pos = bubble_data
                if current_time_ms - creation_time < self.SPEECH_BUBBLE_DURATION_MS:
                    if npc_ref.is_active: # Only draw if NPC is still active
                        # Position above NPC
                        bubble_x = npc_ref.rect.centerx - text_surface.get_width() // 2
                        bubble_y = npc_ref.rect.top - text_surface.get_height() - 5 # 5px padding

                        # Basic bubble background
                        bubble_bg_rect = text_surface.get_rect(topleft=(bubble_x - 5, bubble_y - 5))
                        bubble_bg_rect.width += 10
                        bubble_bg_rect.height += 10
                        pygame.draw.rect(self.screen, self.SPEECH_BUBBLE_COLOR, bubble_bg_rect, border_radius=5)

                        self.screen.blit(text_surface, (bubble_x, bubble_y))
                    active_bubbles.append(bubble_data)
            self.speech_bubbles = active_bubbles


            if is_night(self.game_time_seconds):
                self.screen.blit(self.night_surface, (0, 0))

            # UI Text (Time, SID)
            time_text_surface = self.font.render(f"Time: {get_formatted_game_time(self.game_time_seconds)}", True, WHITE)
            self.screen.blit(time_text_surface, (10, 10))

            session_text_surface = self.font.render(f"SID: {self.session_id}", True, WHITE)
            # self.screen.blit(session_text_surface, (10, SCREEN_HEIGHT - 30))

            # Draw Communication Log if active
            if self.show_comm_log:
                self.draw_comm_log()

            # Draw Player Status UI (placeholder)
            self.draw_player_status()

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

    def update_time(self):
        current_real_time_ns = time.monotonic_ns()
        delta_real_time_seconds = (current_real_time_ns - self.last_real_time_ns) / 1_000_000_000.0
        self.last_real_time_ns = current_real_time_ns

        self.game_time_seconds += real_seconds_to_game_seconds(delta_real_time_seconds)
        self.game_time_seconds %= (24 * 3600) # Wrap around 24 game hours

    def add_speech_bubble(self, npc_ref, text):
        """Adds a speech bubble for an NPC to be displayed on screen."""
        if not text: return
        text_surface = self.speech_font.render(text, True, self.SPEECH_TEXT_COLOR)
        # Position will be calculated during drawing relative to NPC's current position.
        # Stores (NPC_reference, text_surface, creation_time_ms, placeholder_for_rect_pos)
        self.speech_bubbles.append((npc_ref, text_surface, pygame.time.get_ticks(), None))

    def add_to_comm_log(self, message, color=WHITE):
        """Adds a message to the communication log."""
        timestamp = get_formatted_game_time(self.game_time_seconds)
        self.comm_log.append((timestamp, message, color))
        if len(self.comm_log) > self.COMM_LOG_MAX_LINES:
            self.comm_log.pop(0) # Keep log scrollable and manageable

    def draw_comm_log(self):
        """Draws the communication log UI panel if it's active."""
        log_surface = pygame.Surface(self.COMM_LOG_SIZE, pygame.SRCALPHA) # Create a transparent surface
        log_surface.fill(self.COMM_LOG_BG_COLOR) # Fill with semi-transparent background

        current_y = 5
        for timestamp, message, color in reversed(self.comm_log): # Show newest first
            log_line = f"[{timestamp}] {message}"
            # Truncate long messages to fit width (approx)
            max_chars = self.COMM_LOG_SIZE[0] // (self.COMM_LOG_FONT_SIZE // 2) # Rough estimate
            if len(log_line) > max_chars:
                log_line = log_line[:max_chars-3] + "..."

            text_surface = self.comm_log_font.render(log_line, True, color) # Use provided color or default
            log_surface.blit(text_surface, (5, current_y))
            current_y += self.COMM_LOG_FONT_SIZE + 2 # Line spacing
            if current_y + self.COMM_LOG_FONT_SIZE > self.COMM_LOG_SIZE[1]: # Stop if no more space
                break

        self.screen.blit(log_surface, self.COMM_LOG_POS)

    def get_npc_by_name(self, name):
        for npc in self.npcs:
            if npc.name == name:
                return npc
        if self.bob_instance and self.bob_instance.name == name:
             return self.bob_instance
        return None

    def draw_player_status(self):
        """Draws a UI panel for player status (currently a placeholder)."""
        status_area_rect = pygame.Rect(SCREEN_WIDTH - 210, SCREEN_HEIGHT - 60, 200, 50)
        # Draw a semi-transparent background for the status panel
        s = pygame.Surface((200,50), pygame.SRCALPHA)
        s.fill((30,30,30, 180)) # Dark grey, mostly transparent
        self.screen.blit(s, (status_area_rect.x, status_area_rect.y))
        pygame.draw.rect(self.screen, UI_BORDER_COLOR, status_area_rect, 1) # Border

        player_text = "Player"
        # This area could be expanded to show player HP, energy, inventory hints, etc.
        text_surface = self.font.render(player_text, True, WHITE)
        self.screen.blit(text_surface, (status_area_rect.x + 10, status_area_rect.y + 15))


    def handle_bob_spawn_logic(self):
        """Manages Bob's existence based on the Bob Spawn Lever's state."""
        lever_state = self.map_elements["bob_spawn_lever"]["state"]

        if lever_state and self.bob_instance is None:
            # Lever is ON, and Bob object doesn't exist (or was despawned): Create Bob.
            print("Lever is ON. Spawning Bob.")
            # Remove any previous inactive Bob instance from the main npcs list to avoid duplicates if any.
            self.npcs = [npc for npc in self.npcs if npc.name != "Bob"]

            self.bob_instance = Bob(SCREEN_WIDTH - 100, SCREEN_HEIGHT // 2, self) # Create new Bob
            self.npcs.append(self.bob_instance) # Add to active NPCs list
            self.bob_instance.is_active = True
            if self.bob_instance.despawn_timer_start_ns != -1: # If timer was somehow running, cancel it.
                self.bob_instance.despawn_timer_start_ns = -1
                print("Bob's previous despawn timer cancelled due to respawn.")

        elif not lever_state and self.bob_instance is not None and self.bob_instance.is_active:
            # Lever is OFF, Bob exists and is currently active: Start his despawn timer if not already running.
            if self.bob_instance.despawn_timer_start_ns == -1:
                print("Lever is OFF. Starting Bob's despawn timer.")
                self.bob_instance.start_despawn_timer()

        if self.bob_instance is not None and not self.bob_instance.is_active:
            # If Bob has become inactive (e.g., despawn timer finished),
            # set self.bob_instance to None. This allows him to be "re-created" fresh
            # if the lever is turned on again. His entry in self.npcs list will persist but he's inactive.
            print(f"Bob ({self.bob_instance.name}) is now inactive. Resetting self.bob_instance to allow re-spawn.")
            self.bob_instance = None


# --- Main Execution ---
def main():
    """Initializes and runs the game."""
    game = Game()
    game.run()

if __name__ == "__main__":
    # This ensures main() is called only when the script is executed directly.
    main()
