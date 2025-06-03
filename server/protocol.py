import json
import os
import random
import threading
import time
import hashlib
import base64
import secrets

# Constants
PEPPER = "my_secret_pepper_123!"
USERS_FILE = "server/users.json"
# USERS_FILE = "users.json"  # Optional override for local development

DEBUG = False

def debug_print(*args):
    if DEBUG:
        print("[DEBUG]", *args)

class Player:
    def __init__(self, socket, address, username=None):
        self.socket = socket                # Player's socket connection
        self.address = address              # IP address and port
        self.username = username            # Username after login/register
        self.room_id = None                 # ID of the room player is in
        self.position = None                # (x, y) position on the board
        self.is_alive = True                # Player is alive or dead
        self.last_action = None             # Last performed action
        self.encrypted = False              # Whether location is hidden
        self.turn_ready = False             # Flag for turn-based logic
        self.is_bot = False                 # True if player is a bot

class FakeSocket:
    def __init__(self, bot_name):
        self.bot_name = bot_name
        self.buffer = []

    def sendall(self, data):
        print(f"[{self.bot_name}] BOT RECEIVED:", data.decode(errors='ignore'))

    def recv(self, buffer_size):
        return b''

class DummySecure:
    def encrypt(self, data):
        return data

    def decrypt(self, data):
        return data

def gameScan(args, player, GRID_SIZE, players):
    x, y = int(args['x']), int(args['y'])

    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                for p in players:
                    if (
                        p != player and p.is_alive and not p.encrypted and
                        p.position[0] == nx and p.position[1] == ny
                    ):
                        debug_print("Scan found suspicious activity nearby.")
                        return "Scan found suspicious activity nearby.", True

    debug_print("Scan revealed no threats nearby.")
    return "Scan revealed no threats nearby.", True


def gameHack(args, player, players):
    x, y = int(args['x']), int(args['y'])
    msg = "Hack failed. No player at this location."

    for p in players:
        if p != player and p.position == (x, y) and p.is_alive:
            p.is_alive = False
            msg = f"Hack successful. Player {p.username} eliminated!"
            break

    debug_print(msg)
    return msg, True


def gameEvade(player, board):
    board[player.position[1]][player.position[0]] = None  # Clear current position

    while True:
        x, y = random.randint(0, 5), random.randint(0, 5)
        if not board[y][x]:
            board[y][x] = player
            player.position = (x, y)
            break

    msg = f"Evade successful. You moved to a new location. {x} {y}"
    debug_print(msg)
    return msg, True


def gameEncrypt(player):
    player.encrypted = True
    msg = "Your location is encrypted for the next turn."
    debug_print(msg)
    return msg, True


def bot_decide_action(bot, room):
    if not bot.is_alive:
        return None

    grid_size = room.GRID_SIZE
    x, y = bot.position

    # Pick a nearby tile (not the current one)
    scan_x, scan_y = x, y
    while scan_x == x and scan_y == y:
        scan_x = max(0, min(grid_size - 1, x + random.choice([-1, 0, 1])))
        scan_y = max(0, min(grid_size - 1, y + random.choice([-1, 0, 1])))

    if random.random() < 0.3:
        action = {'type': 'HACK', 'args': {'x': scan_x, 'y': scan_y}}
    elif random.random() < 0.5:
        action = {'type': 'SCAN', 'args': {'x': scan_x, 'y': scan_y}}
    elif random.random() < 0.2:
        action = {'type': 'ENCRYPT'}
    else:
        action = {'type': 'EVADE'}

    debug_print(action)
    return action

class GameRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self.players = []
        self.board = create_empty_board()
        self.turn_index = 0
        self.started = False
        self.actions_log = []
        self.lock = threading.Lock()
        self.GRID_SIZE = 6
        self.chat_messages = []
        self.chat_lock = threading.Lock()
        self.game_over = False

    def broadcast_game_state(self, client_socket, secure):
        status_msg = "STATUS " + " ".join(
            [f"{p.username}={'ALIVE' if p.is_alive else 'DEAD'}" for p in self.players]
        )
        current_turn_msg = f"|TURN username={self.players[self.turn_index].username}"

        winner_msg = "|WINNER "
        alive_players = [p for p in self.players if p.is_alive]
        if len(alive_players) == 1:
            winner = alive_players[0]
            winner_msg += f"username={winner.username}"
            if not winner.is_bot and not self.game_over:
                increment_win_count(winner.username)
            self.game_over = True

        chat_msg = "|CHAT " + " // ".join(self.chat_messages)

        debug_print(f"{status_msg}{current_turn_msg}{winner_msg}{chat_msg}")
        sendWithSize(f"{status_msg}{current_turn_msg}{winner_msg}{chat_msg}", client_socket, secure)

    def add_chat_message(self, player, message):
        with self.chat_lock:
            if len(self.chat_messages) >= 4:
                self.chat_messages.pop(0)
            self.chat_messages.append(f"{player.username}: {message}")
            debug_print(f"{player.username}: {message}")

    def add_player(self, player):
        with self.lock:
            self.players.append(player)
            if len(self.players) == 4:
                self.started = True
                self.start_turn()
                self.init_game()
            debug_print(f"{player.username} added!")

    def init_game(self):
        for player in self.players:
            while True:
                x, y = random.randint(0, 5), random.randint(0, 5)
                if not self.board[y][x]:
                    self.board[y][x] = player
                    player.position = (x, y)
                    break

    def bot_take_turn(self, bot_player):
        time.sleep(1)
        command = bot_decide_action(bot_player, self)
        if command:
            self.handle_command(bot_player, command, DummySecure())
        debug_print(command)

    def start_turn(self):
        while not self.players[self.turn_index].is_alive:
            self.turn_index = (self.turn_index + 1) % len(self.players)

        current_player = self.players[self.turn_index]
        current_player.turn_ready = True
        debug_print(f"{current_player.username}'s turn!")

        if current_player.is_bot:
            threading.Thread(target=self.bot_take_turn, args=(current_player,), daemon=True).start()

    def end_turn(self):
        current_player = self.players[self.turn_index]
        current_player.turn_ready = False

        self.turn_index = (self.turn_index + 1) % len(self.players)
        debug_print("Turn ended")
        self.start_turn()

    def handle_command(self, player, command, secure):
        with self.lock:
            if not player.turn_ready:
                debug_print('ACTION_RESULT success=false msg="It\'s not your turn!"')
                sendWithSize('ACTION_RESULT success=false msg="It\'s not your turn!"', player.socket, secure)
                return

            if not player.is_alive:
                debug_print('ACTION_RESULT success=false msg="You are eliminated."')
                sendWithSize('ACTION_RESULT success=false msg="You are eliminated."', player.socket, secure)
                return

            cmd_type = command['type']
            args = command.get('args', {})
            msg = ""
            success = False

            player.encrypted = False  # Reset encryption at start of turn

            match cmd_type:
                case 'SCAN':
                    msg, success = gameScan(args, player, self.GRID_SIZE, self.players)
                case 'HACK':
                    msg, success = gameHack(args, player, self.players)
                case 'EVADE':
                    msg, success = gameEvade(player, self.board)
                case 'ENCRYPT':
                    msg, success = gameEncrypt(player)

            debug_print(f'ACTION_RESULT success={success} msg="{msg}"')
            sendWithSize(f'ACTION_RESULT success={success} msg="{msg}"', player.socket, secure)

            if success:
                self.end_turn()

    def handle_bot_turn(self, player):
        if not player.is_alive:
            return

        action = random.choice(["SCAN", "HACK", "EVADE", "ENCRYPT"])
        args = {}

        if action in ["SCAN", "HACK"]:
            args['x'] = str(random.randint(0, self.GRID_SIZE - 1))
            args['y'] = str(random.randint(0, self.GRID_SIZE - 1))

        msg = ""
        success = False
        player.encrypted = False

        if action == "SCAN":
            msg, success = gameScan(args, player, self.GRID_SIZE, self.players)
        elif action == "HACK":
            msg, success = gameHack(args, player, self.players)
        elif action == "EVADE":
            msg, success = gameEvade(player, self.board)
        elif action == "ENCRYPT":
            msg, success = gameEncrypt(player)

        debug_print(f"Bot {player.username} performed {action}: {msg}")
        print(f"Bot {player.username} performed {action}: {msg}")
        self.actions_log.append(f"Bot {player.username} performed {action}: {msg}")

        if success:
            self.end_turn()

def sendWithSize(message, conn, secure):
    if isinstance(message, str):
        message = message.encode()
    elif not isinstance(message, bytes):
        raise TypeError("Message must be str or bytes")

    encrypted = secure.encrypt(message)
    length = str(len(encrypted)).zfill(8).encode()
    conn.sendall(length + encrypted)


def recvWithSize(conn, secure):
    length_data = conn.recv(8)
    if not length_data:
        return None

    try:
        length = int(length_data.decode().strip())
    except ValueError:
        return None

    encrypted_data = b""
    while len(encrypted_data) < length:
        chunk = conn.recv(length - len(encrypted_data))
        if not chunk:
            return None
        encrypted_data += chunk

    decrypted = secure.decrypt(encrypted_data)
    return decrypted if isinstance(decrypted, str) else decrypted.decode()


def increment_win_count(username):
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = json.load(f)

        if username in users:
            users[username]["wins"] = users[username].get("wins", 0) + 1

        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            data = json.load(f)
            debug_print(data)
            return data
    debug_print({})
    return {}


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)
    debug_print("saved!")


def hash_password(password, salt):
    debug_print("hashed!")
    return hashlib.sha256((password + PEPPER + salt).encode()).hexdigest()


def checkPlayer(username, password, clients):
    users = load_users()

    if username not in users:
        debug_print("False")
        return False

    stored_salt = users[username]["salt"]
    stored_hash = users[username]["password"]
    provided_hash = hash_password(password, stored_salt)

    if stored_hash != provided_hash:
        debug_print("False")
        return False

    for player in clients.values():
        if player.username == username:
            debug_print("False")
            return False

    debug_print("True")
    return True


def savePlayer(username, password):
    users = load_users()

    if username in users:
        debug_print("False")
        return False

    salt = secrets.token_hex(16)
    hashed_password = hash_password(password, salt)

    users[username] = {
        "password": hashed_password,
        "salt": salt,
        "wins": 0
    }

    save_users(users)
    debug_print("True")
    return True


def parse_command(msg):
    parts = msg.strip().split()
    cmd_type = parts[0]
    args = {}

    for part in parts[1:]:
        if '=' in part:
            key, value = part.split('=', 1)
            args[key] = value

    debug_print({'type': cmd_type, 'args': args})
    return {'type': cmd_type, 'args': args}

def create_empty_board():
    size = 6
    debug_print("board created!")
    return [[None for _ in range(size)] for _ in range(size)]


def cleanup_player(client_socket, player, rooms_lock, rooms, clients, clients_lock, secure):
    if player.username:
        if player.room_id is not None:
            with rooms_lock:
                room = rooms.get(player.room_id)
                if room:
                    room.players.remove(player)
                    room_id_to_delete = player.room_id
                    player.room_id = None
                    player.is_alive = True
                    player = None
                    if len(room.players) == 0:
                        del rooms[room_id_to_delete]
        with clients_lock:
            clients.pop(client_socket)


def cmdLogin(player, command, client_socket, clients, secure):
    username = command['args']['username']
    password = command['args']['password']

    if checkPlayer(username, password, clients):
        player.username = username
        debug_print(f"LOGIN_SUCCESS username={username}")
        sendWithSize(f"LOGIN_SUCCESS username={username}", client_socket, secure)
    else:
        debug_print('LOGIN_FAIL reason="Invalid password or username"')
        sendWithSize('LOGIN_FAIL reason="Invalid password or username"', client_socket, secure)


def cmdRegister(player, command, client_socket, secure):
    username = command['args']['username']
    password = command['args']['password']

    if savePlayer(username, password):
        player.username = username
        debug_print(f"REGISTER_SUCCESS username={username}")
        sendWithSize(f"REGISTER_SUCCESS username={username}", client_socket, secure)
    else:
        debug_print('REGISTER_FAIL reason="Username already exists"')
        sendWithSize('REGISTER_FAIL reason="Username already exists"', client_socket, secure)


def cmdJoin(player, client_socket, rooms_lock, rooms, secure):
    with rooms_lock:
        for room in rooms.values():
            if not room.started:
                room_id = room.room_id
                room.add_player(player)
                player.room_id = room_id
                debug_print(f'ROOM_JOINED room_id={room_id} room_name=Room{room_id} players={len(room.players)}/4')
                sendWithSize(f'ROOM_JOINED room_id={room_id} room_name=Room{room_id} players={len(room.players)}/4',
                             client_socket, secure)
                break
        else:
            debug_print('JOIN_FAIL reason="No room found"')
            sendWithSize('JOIN_FAIL reason="No room found"', client_socket, secure)


def cmdCreate(player, client_socket, rooms_lock, rooms, secure):
    with rooms_lock:
        room_id = len(rooms)
        room_name = f'Room{room_id}'
        rooms[room_id] = GameRoom(room_id)
        rooms[room_id].add_player(player)
        player.room_id = room_id
        debug_print(f'ROOM_CREATED room_id={room_id} room_name={room_name}')
        sendWithSize(f'ROOM_CREATED room_id={room_id} room_name={room_name}', client_socket, secure)


def cmdView(client_socket, rooms_lock, rooms, secure):
    with rooms_lock:
        if not rooms:
            debug_print("VIEW_ROOM_LIST")
            sendWithSize("VIEW_ROOM_LIST", client_socket, secure)
        else:
            room_list = [
                f"{room_id}=Room{room_id}({len(room.players)}/4)"
                for room_id, room in rooms.items()
                if not room.started
            ]
            response = "VIEW_ROOM_LIST " + " ".join(room_list)
            debug_print(response)
            sendWithSize(response, client_socket, secure)


def cmdCommands(player, command, rooms_lock, rooms, secure):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        room.handle_command(player, command, secure)


def cmdPlayers(player, client_socket, rooms_lock, rooms, secure):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        usernames = [p.username for p in room.players]
        response = "PLAYERS " + " ".join(usernames) + f" {room.started}"
        debug_print(response)
        sendWithSize(response, client_socket, secure)
    else:
        debug_print("PLAYERS")
        sendWithSize("PLAYERS", client_socket, secure)


def cmdLeave(player, client_socket, rooms_lock, rooms, secure):
    with rooms_lock:
        room = rooms.get(player.room_id)
        if room:
            room.players.remove(player)
            sendWithSize("LEAVE_SUCCESS", client_socket, secure)

            room_id_to_delete = player.room_id
            player.room_id = None
            player.is_alive = True

            if len(room.players) == 0:
                del rooms[room_id_to_delete]
        else:
            debug_print('LEAVE_FAIL reason="Not in a room."')
            sendWithSize('LEAVE_FAIL reason="Not in a room."', client_socket, secure)


def cmdStart(player, client_socket, rooms_lock, rooms, secure):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        with room.lock:
            if room.started:
                debug_print("START_FAIL reason='Game already started'")
                sendWithSize("START_FAIL reason='Game already started'", client_socket, secure)
            elif len(room.players) < 2:
                debug_print("START_FAIL reason='Not enough players to start the game'")
                sendWithSize("START_FAIL reason='Not enough players to start the game'", client_socket, secure)
            else:
                room.started = True
                start_message = "The game has started!"
                debug_print(f"STARTING msg='{start_message}'")
                sendWithSize(f"STARTING msg='{start_message}'", client_socket, secure)
                room.start_turn()
    else:
        debug_print("START_FAIL reason='Player not in a room'")
        sendWithSize("START_FAIL reason='Player not in a room'", client_socket, secure)


def cmdUsername(player, client_socket, secure):
    debug_print(f"USERNAME_SUCCESS {player.username}")
    sendWithSize(f"USERNAME_SUCCESS {player.username}", client_socket, secure)


def cmdPosition(player, client_socket, rooms, secure):
    board = rooms[player.room_id].board

    x = random.randint(0, 5)
    y = random.randint(0, 5)
    player.position = [x, y]

    # Ensure the position is not already occupied
    while board[player.position[1]][player.position[0]] is not None:
        player.position = [random.randint(0, 5), random.randint(0, 5)]

    board[player.position[1]][player.position[0]] = player

    debug_print(f"POSITION_SUCCESS {player.position[0]} {player.position[1]}")
    sendWithSize(f"POSITION_SUCCESS {player.position[0]} {player.position[1]}", client_socket, secure)


def cmdStatus(player, client_socket, rooms_lock, rooms, secure):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        with room.lock:
            room.broadcast_game_state(client_socket, secure)


def cmdChat(player, msg, client_socket, rooms_lock, rooms, secure):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        with room.lock:
            debug_print("CHAT_SUCCESS")
            sendWithSize("CHAT_SUCCESS", client_socket, secure)
            room.add_chat_message(player, msg)


def cmdBot(player, client_socket, rooms_lock, rooms, secure):
    with rooms_lock:
        bot1 = Player(FakeSocket("Bot1"), None, "BOT1")
        bot2 = Player(FakeSocket("Bot2"), None, "BOT2")
        bot3 = Player(FakeSocket("Bot3"), None, "BOT3")
        for bot in [bot1, bot2, bot3]:
            bot.is_bot = True

        room_id = len(rooms)
        room_name = f'Room{room_id}'
        room = GameRoom(room_id)
        room.add_player(player)
        room.add_player(bot1)
        room.add_player(bot2)
        room.add_player(bot3)

        rooms[room_id] = room
        player.room_id = room_id

        debug_print(f'CREATE_BOT room_id={room_id} room_name={room_name}')
        sendWithSize(f'CREATE_BOT room_id={room_id} room_name={room_name}', client_socket, secure)


def cmdLeaderboard(client_socket, secure):
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)

        leaderboard_data = sorted(
            (
                {"username": username, "wins": info.get("wins", 0)}
                for username, info in users.items()
                if not info.get("is_bot", False)
            ),
            key=lambda x: x["wins"],
            reverse=True
        )

        response = "LEADERBOARD " + " ".join(
            f"{user['username']}:{user['wins']}" for user in leaderboard_data
        )

        debug_print(json.dumps(response))
        sendWithSize(json.dumps(response), client_socket, secure)

    except Exception as e:
        error_response = {
            "type": "ERROR",
            "message": f"Failed to get leaderboard: {str(e)}"
        }
        debug_print(json.dumps(error_response))
        sendWithSize(json.dumps(error_response), client_socket, secure)


def cmdEndTurn(player, rooms_lock, rooms, client_socket, secure):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        with room.lock:
            room.end_turn()
    debug_print("END_TURN")
    sendWithSize("END_TURN", client_socket, secure)


def cmdJoinRoomName(player, command, client_socket, rooms_lock, rooms, secure):
    requested_name = command['args'].get('room_name')
    if not requested_name:
        debug_print('JOIN_FAIL reason="No room name provided"')
        sendWithSize('JOIN_FAIL reason="No room name provided"', client_socket, secure)
        return

    with rooms_lock:
        for room_id, room in rooms.items():
            room_name = f"Room{room_id}"
            if room_name.lower() == requested_name.lower() and not room.started:
                room.add_player(player)
                player.room_id = room_id
                response = f'JOIN_ROOM_NAME room_id={room_id} room_name={room_name} players={len(room.players)}/4'
                debug_print(response)
                sendWithSize(response, client_socket, secure)
                return

        debug_print(f'JOIN_ROOM_NAME_FAILED reason="Room {requested_name} not found or already started"')
        sendWithSize(f'JOIN_ROOM_NAME_FAILED reason="Room {requested_name} not found or already started"', client_socket, secure)
