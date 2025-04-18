import tkinter as tk
from tkinter import messagebox
import socket
from client_protocol import *
import pygame
import sys
import threading
import queue


client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect(('127.0.0.1', 5050))

username = None

# ---------- GUI Screens ----------

def login_screen():
    def doLogin():
        u = username_entry.get()
        p = password_entry.get()
        response = send_command(f"LOGIN username={u} password={p}",client_socket)
        if response.startswith("LOGIN_SUCCESS"):
            global username
            username = u
            #messagebox.showinfo("Login", "Login successful!")
            window.destroy()
            main_menu()
        else:
            messagebox.showerror("Login Failed", response)

    window = tk.Tk()
    window.title("Cyber Hunt - Login")
    window.geometry("400x300")
    tk.Label(window, text="Username").pack()
    username_entry = tk.Entry(window)
    username_entry.pack()
    tk.Label(window, text="Password").pack()
    password_entry = tk.Entry(window, show="*")
    password_entry.pack()
    tk.Button(window, text="Login", command=doLogin).pack()
    tk.Button(window, text="Register", command=lambda:[window.destroy(), register_screen()]).pack()
    window.mainloop()

def register_screen():
    def doRegister():
        u = username_entry.get()
        p = password_entry.get()
        response = send_command(f"REGISTER username={u} password={p}",client_socket)
        if response.startswith("REGISTER_SUCCESS"):
            global username
            username = u
            #messagebox.showinfo("Registration", "Registered successfully!")
            window.destroy()
            main_menu()
        else:
            messagebox.showerror("Registration Failed", response)

    window = tk.Tk()
    window.title("Cyber Hunt - Register")
    window.geometry("400x300")
    tk.Label(window, text="Username").pack()
    username_entry = tk.Entry(window)
    username_entry.pack()
    tk.Label(window, text="Password").pack()
    password_entry = tk.Entry(window, show="*")
    password_entry.pack()
    tk.Button(window, text="Register", command=doRegister).pack()
    tk.Button(window, text="Back to Login", command=lambda:[window.destroy(), login_screen()]).pack()
    window.mainloop()

def main_menu():
    def join_game():
        response = send_command("JOIN",client_socket)
        command = parse_command(response)
        if command['type'] == "ROOM_JOINED":
            #messagebox.showinfo("Join", response)
            menu.destroy()
            lobby_screen(room_info=command['args']['room_name'])
        else:
            messagebox.showerror("Join Failed", response)

    def create_game():
        response = send_command("CREATE",client_socket)
        command = parse_command(response)
        if command['type'] =="ROOM_CREATED":
            #messagebox.showinfo("Room", response)
            menu.destroy()
            lobby_screen(room_info=command['args']['room_name'],is_host=True)
        else:
            messagebox.showerror("Create Failed", response)

    def view_rooms():
        response = send_command("VIEW",client_socket)
        messagebox.showinfo("Available Rooms", response)

    menu = tk.Tk()
    menu.title("Cyber Hunt - Main Menu")
    menu.geometry("400x300")
    tk.Label(menu, text=f"Welcome, {username}").pack()
    tk.Button(menu, text="Join Room", command=join_game).pack()
    tk.Button(menu, text="Create Room", command=create_game).pack()
    tk.Button(menu, text="View Rooms", command=view_rooms).pack()
    menu.mainloop()

def lobby_screen(room_info="Room Info", players=None, is_host=False):
    if players is None:
        players = []

    lobby = tk.Tk()
    lobby.title("Cyber Hunt - Lobby")
    lobby.geometry("400x300")

    def on_close():
        global timer_running
        timer_running = False
        lobby.destroy()

    lobby.protocol("WM_DELETE_WINDOW", on_close)

    tk.Label(lobby, text=f"🕹️ {room_info}", font=("Arial", 14, "bold")).pack(pady=10)

    players_frame = tk.Frame(lobby)
    players_frame.pack(pady=10)

    players_label = tk.Label(players_frame, text=f"Players in Room: {len(players)} / 4")
    players_label.pack()

    player_list_frame = tk.Frame(players_frame)
    player_list_frame.pack()

    def update_players():
        try:
            if not players_label.winfo_exists():
                return  # Lobby closed
            
            sendWithSize("PLAYERS", client_socket)
            players_response = recvWithSize(client_socket)

            if players_response.startswith("PLAYERS"):
                players = players_response.split()[1:-1]
                starting = players_response.split()[-1]

                # Clear only the player list part
                for widget in player_list_frame.winfo_children():
                    widget.destroy()

                for player in players:
                    tk.Label(player_list_frame, text=f"• {player}").pack(anchor='w')

                players_label.config(text=f"Players in Room: {len(players)} / 4")

                if starting.startswith("True"):
                    lobby.destroy()
                    username = send_command(f"USERNAME",client_socket)
                    launch_game(client_socket,username.split()[1])
                    return
                
            players_label.after(1000, update_players)

        except tk.TclError:
            print("UI destroyed while updating players.")
            return

    def start_game_pressed():
        response = send_command("START",client_socket)

        if not response.startswith("STARTING"):
            messagebox.showerror("Start Failed", response)

    def leave_room():
        response = send_command("LEAVE",client_socket)
        if response.startswith("LEAVE_SUCCESS"):
            on_close()
            main_menu()
        else:
            messagebox.showerror("Leave Failed", response)

    if is_host:
        tk.Button(lobby, text="Start Game", command=start_game_pressed).pack(pady=10)
    tk.Button(lobby, text="Back to Menu", command=leave_room).pack()

    update_players()
    lobby.mainloop()

status_queue = queue.Queue()
your_turn = threading.Event()  # This will be cleared when it's NOT your turn


def launch_game(client_socket, username):
    pygame.init()
    game_running = True

    screen_width, screen_height = 800, 600
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Cyber Hunt - Game")

    font = pygame.font.SysFont(None, 32)
    small_font = pygame.font.SysFont(None, 24)

    grid_size = 6
    cell_size = 60
    grid_origin = (50, 50)

    click_display_pos = None
    click_grid_coords = None

    turn_text_surface = None
    players_text_surface = None

    pos = send_command("POSITION", client_socket).split()
    player_pos = [int(pos[1]), int(pos[2])]

    BG_COLOR = (30, 30, 30)
    GRID_COLOR = (200, 200, 200)
    PLAYER_COLOR = (0, 200, 255)
    BUTTON_COLOR = (50, 50, 200)
    BUTTON_HOVER = (70, 70, 255)
    TEXT_COLOR = (255, 255, 255)

    actions = ["SCAN", "HACK", "ENCRYPT", "EVADE"]
    buttons = [ (pygame.Rect(500, 60 + i * 70, 200, 50), action) for i, action in enumerate(actions) ]

    gx, gy = -1, -1
    is_alive = True
    won = False
    messages = []  # List of game log messages

    chat_input_box = pygame.Rect(500, 500, 200, 50)  # Chat input area
    chat_message_list = []  # To hold the chat messages

    def log(msg):
        messages.append(msg)
        if len(messages) > 4:
            messages.pop(0)

    def check_status():
        nonlocal turn_text_surface, players_text_surface, is_alive, won

        response = send_command("STATUS", client_socket)

        if response.startswith("STATUS"):
            parts = response.split("|")
            status_part = parts[0].strip()
            turn_part = parts[1].strip()
            winner_part = parts[2].strip()
            chat_part = parts[3].strip()

            # Parse player statuses
            player_statuses = status_part[len("STATUS "):].split()
            player_status_dict = {}
            for entry in player_statuses:
                name, state = entry.split("=")
                player_status_dict[name] = state

            # Check your own status
            is_alive = player_status_dict.get(username, "DEAD") == "ALIVE"

            # Update players_text_surface with all players
            player_lines = []
            for name, state in player_status_dict.items():
                status_text = f"{name}: {'✅ ALIVE' if state == 'ALIVE' else 'DEAD'}"
                player_lines.append(status_text)
            
            players_text_surface = [small_font.render(line, True, (0, 255, 0) if "ALIVE" in line else (255, 0, 0)) for line in player_lines]

            # Check turn info
            current_turn = ""
            if turn_part.startswith("TURN"):
                parts = turn_part.split()
                for p in parts:
                    if p.startswith("username="):
                        current_turn = p.split("=")[1]

            if not is_alive:
                turn_text_surface = font.render("You are DEAD", True, (255, 0, 0))
            elif won:
                turn_text_surface = font.render("You WON!", True, (0, 255, 0))
            else:
                turn_text_surface = font.render(f"Current Turn: {current_turn}", True, (255, 255, 255))


            # Win check
            if winner_part.startswith("WINNER"):
                try:
                    winner_name = winner_part.split("=")[1]
                    if winner_name == username:
                        won = True
                        log("You WON!")
                    else:
                        is_alive = False
                        log(f"{winner_name} won the game.")
                except Exception as e:
                    #no username
                    pass
            
            if chat_part.startswith("CHAT"):
                try:    
                    chat_msg_str = chat_part[len("CHAT "):]
                    m = chat_msg_str.split(" // ")
                    chat_message_list.clear()
                    chat_message_list.extend(m)
                except Exception as e:
                    #no messages
                    pass

                

    status_check_timer = 0

    chat_input_text = ""
    typing_in_chat = False  # Keep track of whether the user is typing in the chat box

    def send_chat_message(message):
        if message:  # Ensure the message is not empty
            response = send_command(f"CHAT msg={message}", client_socket)
            if response.startswith("CHAT_SUCCESS"):
                print(f"Message sent: {message}")
            else:
                print(f"Failed to send message: {response}")


    while game_running:
        screen.fill(BG_COLOR)

        # Draw Grid
        for row in range(grid_size):
            for col in range(grid_size):
                rect = pygame.Rect(
                    grid_origin[0] + col * cell_size,
                    grid_origin[1] + row * cell_size,
                    cell_size,
                    cell_size
                )
                pygame.draw.rect(screen, GRID_COLOR, rect, 1)

        # Player block
        player_rect = pygame.Rect(
            grid_origin[0] + player_pos[0] * cell_size,
            grid_origin[1] + player_pos[1] * cell_size,
            cell_size,
            cell_size
        )
        pygame.draw.rect(screen, PLAYER_COLOR, player_rect)

        # Buttons
        mouse_pos = pygame.mouse.get_pos()
        for rect, action in buttons:
            pygame.draw.rect(screen, BUTTON_HOVER if rect.collidepoint(mouse_pos) else BUTTON_COLOR, rect)
            screen.blit(font.render(action, True, TEXT_COLOR), (rect.x + 10, rect.y + 10))

        # Click info
        if click_display_pos and click_grid_coords:
            cx = min(click_display_pos[0], screen_width - 50)
            cy = min(click_display_pos[1], screen_height - 20)
            screen.blit(font.render(f"({click_grid_coords[0]}, {click_grid_coords[1]})", True, (255, 255, 0)), (cx, cy))

        # Game log messages
        for i, msg in enumerate(messages):
            screen.blit(small_font.render(msg, True, (200, 200, 100)), (20, 450 + i * 20))

        # Chat box
        pygame.draw.rect(screen, (200, 200, 200), chat_input_box)
        placeholder = chat_input_text if typing_in_chat or chat_input_text else "Chat here"
        rendered_input_text = pygame.font.SysFont(None, 20).render(placeholder, True, (0, 0, 0))

        screen.blit(rendered_input_text, (chat_input_box.x + 5, chat_input_box.y + 15))

        # Turn info surface
        if turn_text_surface:
            screen.blit(turn_text_surface, (10, 10))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not is_alive or won:
                    continue
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if chat_input_box.collidepoint(event.pos):
                        typing_in_chat = True
                    else:
                        typing_in_chat = False
                for rect, action in buttons:
                    if rect.collidepoint(event.pos):
                        match action:
                            case a if a in ("SCAN", "HACK"):
                                if gx >= 0 and gy >= 0:
                                    response = send_command(f"{a} x={gx} y={gy}", client_socket)
                                    parsed = parse_command(response)
                                    msg = response[response.find("msg=") + 4:]
                                    log(msg)
                            case "ENCRYPT" | "EVADE":
                                response = send_command(action, client_socket)
                                parsed = parse_command(response)
                                msg = response[response.find("msg=") + 4:]
                                log(msg)
                                if action == "EVADE" and parsed["args"]["success"].startswith("True"):
                                    x, y = msg.split()[-2], msg.split()[-1][:-1]
                                    player_pos[0], player_pos[1] = int(x), int(y)

                x, y = event.pos
                gx = (x - grid_origin[0]) // cell_size
                gy = (y - grid_origin[1]) // cell_size
                if 0 <= gx < 6 and 0 <= gy < 6:
                    click_display_pos = (x, y)
                    click_grid_coords = (gx, gy)

            elif event.type == pygame.KEYDOWN and typing_in_chat:
                if event.key == pygame.K_RETURN:
                    send_chat_message(chat_input_text)
                    chat_input_text = ""
                elif event.key == pygame.K_BACKSPACE:
                    chat_input_text = chat_input_text[:-1]
                else:
                    chat_input_text += event.unicode


        # Always show the last turn info
        if turn_text_surface:
            screen.blit(turn_text_surface, (10, 10))

        # Display username at top right
        username_text = small_font.render(f"Player: {username}", True, (255, 255, 255))
        screen.blit(username_text, (screen_width - username_text.get_width() - 10, 10))

        if players_text_surface:
            total_height = len(players_text_surface) * 25
            start_y = screen_height - total_height - 10
            for i, line_surf in enumerate(players_text_surface):
                x = screen_width - line_surf.get_width() - 10
                y = start_y + i * 25
                screen.blit(line_surf, (x, y))

        
        status_check_timer += 1
        if status_check_timer >= 30:  # every ~30 frames (~0.5 sec at 60 FPS)
            check_status()
            status_check_timer = 0
        
        for i, msg in enumerate(chat_message_list[-4:]):
            msg_surface = small_font.render(msg, True, (200, 200, 100))
            screen.blit(msg_surface, (500, 400 + i * 20))

        pygame.display.flip()
    
    response = send_command("LEAVE",client_socket)
    client_socket.close()
    pygame.quit()
    sys.exit()


# Start with login screen
login_screen()