import json
import os
import random
import threading

USERS_FILE = "users.json"

class Player:
    def __init__(self, socket, address, username=None):
        self.socket = socket
        self.address = address
        self.username = username
        self.room_id = None
        self.position = None
        self.is_alive = True
        self.last_action = None
        self.encrypted = False
        self.turn_ready = False

def gameScan(args, player, GRID_SIZE, players):
    x, y = int(args['x']), int(args['y'])
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                for p in players:
                    if p != player and p.is_alive and not p.encrypted and p.position[0] == nx and p.position[1] == ny:
                        return ("Scan found suspicious activity nearby.", True)
    return ("Scan revealed no threats nearby.", True)

def gameHack(args, player, players):
    x, y = int(args['x']), int(args['y'])
    msg = "Hack failed. No player at this location."
    for p in players:
        if p != player and p.position[0] == x and p.position[1] == y and p.is_alive:
            p.is_alive = False
            msg = f"Hack successful. Player {p.username} eliminated!"
            break
    return (msg, True)


def gameEvade(player,board):
    board[player.position[1]][player.position[0]] = None
    while True:
        x, y = random.randint(0, 5), random.randint(0, 5)
        if not board[y][x]:
            board[y][x] = player
            player.position = (x, y)
            break
    msg = f"Evade successful. You moved to a new location. {x} {y}"
    success = True

    return (msg,success)

def gameEncrypt(player):
    player.encrypted = True
    msg = "Your location is encrypted for the next turn."
    success = True

    return (msg,success)

class GameRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self.players = []
        self.board = create_empty_board()
        self.turn_index = 0  # Keep track of whose turn it is
        self.started = False
        self.actions_log = []
        self.lock = threading.Lock()
        self.GRID_SIZE = 6
        self.chat_messages = []  # Store chat messages
        self.chat_lock = threading.Lock()  # Lock for chat messages
    
    def broadcast_game_state(self, client_socket):
        # Broadcast alive/dead status
        status_msg = "STATUS "
        status_msg += " ".join(
            [f"{p.username}={'ALIVE' if p.is_alive else 'DEAD'}" for p in self.players]
        )

        # Broadcast turn info
        current_turn_msg = f"|TURN username={self.players[self.turn_index].username}"

        # Broadcast win/loss if only one player is alive
        alive_players = [p for p in self.players if p.is_alive]
        winner_msg = "|WINNER "
        if len(alive_players) == 1 and self.started:
            winner = alive_players[0]
            winner_msg += f"username={winner.username}"
            self.started = False  # Stop the game
        
        # Broadcast the chat messages every 0.5 seconds
        chat_msg = "|CHAT "
        chat_msg += " // ".join(self.chat_messages)

        sendWithSize(f"{status_msg}{current_turn_msg}{winner_msg}{chat_msg}", client_socket)

        
    
    def add_chat_message(self,player, message):
        with self.chat_lock:
            if len(self.chat_messages) >= 4:
                self.chat_messages.pop(0)
            self.chat_messages.append(f"{player.username}: {message}")

    def add_player(self, player):
        with self.lock:
            self.players.append(player)
            if len(self.players) == 4:
                self.started = True
                self.start_turn()
                self.init_game()

    def init_game(self):
        for player in self.players:
            while True:
                x, y = random.randint(0, 5), random.randint(0, 5)
                if not self.board[y][x]:
                    self.board[y][x] = player
                    player.position = (x, y)
                    break

    def start_turn(self):
        # Start the turn for the current player
        while not self.players[self.turn_index].is_alive:
            self.turn_index = (self.turn_index + 1) % len(self.players)
        current_player = self.players[self.turn_index]
        current_player.turn_ready = True

    def end_turn(self):
        # End the current player's turn and start the next player's turn
        current_player = self.players[self.turn_index]
        current_player.turn_ready = False
        
        # Move to the next player (circularly)
        self.turn_index = (self.turn_index + 1) % len(self.players)
        self.start_turn()

    def handle_command(self, player, command):
        with self.lock:
            # Check if it's the player's turn
            if not player.turn_ready:
                sendWithSize('ACTION_RESULT success=false msg="It\'s not your turn!"', player.socket)
                return

            cmd_type = command['type']
            args = command.get('args', {})
            msg = ""
            success = False

            if not player.is_alive:
                sendWithSize('ACTION_RESULT success=false msg="You are eliminated."', player.socket)
                return

            # Handle the command based on its type
            match cmd_type:
                case 'SCAN':
                    msg, success = gameScan(args, player, self.GRID_SIZE, self.players)
                case 'HACK':
                    msg, success = gameHack(args, player, self.players)
                case 'EVADE':
                    msg, success = gameEvade(player, self.board)
                case 'ENCRYPT':
                    msg, success = gameEncrypt(player)

            sendWithSize(f'ACTION_RESULT success={success} msg="{msg}"', player.socket)

            if success:
                self.end_turn()  # Move to the next turn after a successful action

def sendWithSize(message, conn):
    message = message.encode()
    length = str(len(message)).zfill(8)
    conn.sendall(length.encode() + message)

def recvWithSize(conn):
    length_data = conn.recv(8)
    if not length_data:
        return None
    try:
        length = int(length_data.decode().strip())
    except ValueError:
        return None
    message = b""
    while len(message) < length:
        chunk = conn.recv(length - len(message))
        if not chunk:
            return None
        message += chunk
    return message.decode()

def checkPlayer(username,password,clients):
    users = {}

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = json.load(f)

    if username in users and users[username] == password:
        for player in clients.values():
            if player.username == username:
                return False
        return True
    else:
        return False

def savePlayer(username,password):
    users = {}

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = json.load(f)

    if username in users:
        return False

    users[username] = password
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

    return True

def parse_command(msg):
    parts = msg.strip().split()
    cmd_type = parts[0]
    args = {}

    for part in parts[1:]:
        if '=' in part:
            key, value = part.split('=', 1)
            args[key] = value

    return {'type': cmd_type, 'args': args}

def create_empty_board():
    size = 6
    return [[None for _ in range(size)] for _ in range(size)]

def cleanup_player(client_socket, player,rooms_lock,rooms,clients,clients_lock):
    if player.username:
        if player.room_id != None:
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
                    else:
                        usernames = [p.username for p in room.players]
                        sendWithSize(f"PLAYERS " + " ".join(usernames) + f" {room.started}", client_socket)
        with clients_lock:
            clients.pop(client_socket)

def cmdLogin(player,command,client_socket,clients):
    username = command['args']['username']
    password = command['args']['password']
    if checkPlayer(username, password,clients):
        player.username = username
        sendWithSize(f"LOGIN_SUCCESS username={username}", client_socket)
    else:
        sendWithSize('LOGIN_FAIL reason="Invalid password or username"', client_socket)

def cmdRegister(player,command,client_socket):
    username = command['args']['username']
    password = command['args']['password']
    if savePlayer(username, password):
        player.username = username
        sendWithSize(f"REGISTER_SUCCESS username={username}", client_socket)
    else:
        sendWithSize('REGISTER_FAIL reason="Username already exists"', client_socket)

def cmdJoin(player,client_socket,rooms_lock,rooms):
    with rooms_lock:
        for room in rooms.values():
            if not room.started:
                room_id = room.room_id
                room.add_player(player)
                player.room_id = room_id
                sendWithSize(f'ROOM_JOINED room_id={room_id} room_name=Room{room_id} players={len(room.players)}/4', client_socket)
                break
        else:
            sendWithSize('JOIN_FAIL reason="No room found"', client_socket)

def cmdCreate(player,client_socket,rooms_lock,rooms):
    with rooms_lock:
        room_id = len(rooms)
        room_name = f'Room{room_id}'
        rooms[room_id] = GameRoom(room_id)
        rooms[room_id].add_player(player)
        player.room_id = room_id
        sendWithSize(f'ROOM_CREATED room_id={room_id} room_name={room_name}', client_socket)

def cmdView(client_socket,rooms_lock,rooms):
    with rooms_lock:
        if not rooms:
            sendWithSize("VIEW_ROOM_LIST", client_socket)
        else:
            room_list = []
            for room_id, room in rooms.items():
                room_name = f"Room{room_id}"
                player_count = len(room.players)
                room_list.append(f"{room_id}={room_name}({player_count}/4)")
            response = "VIEW_ROOM_LIST " + " ".join(room_list)
            sendWithSize(response, client_socket)

def cmdCommands(player,command,rooms_lock,rooms):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        room.handle_command(player, command)

def cmdPlayers(player,client_socket,rooms_lock,rooms):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        usernames = [p.username for p in room.players]
        response = "PLAYERS " + " ".join(usernames) + f" {room.started}"
        sendWithSize(response, client_socket)
    else:
        sendWithSize("PLAYERS", client_socket)

def cmdLeave(player,client_socket,rooms_lock,rooms):
    with rooms_lock:
        room = rooms.get(player.room_id)
        if room:
            room.players.remove(player)
            sendWithSize("LEAVE_SUCCESS", client_socket)
            room_id_to_delete = player.room_id
            player.room_id = None
            player.is_alive = True

            if len(room.players) == 0:
                del rooms[room_id_to_delete]
            else:
                usernames = [p.username for p in room.players]
                sendWithSize(f"PLAYERS " + " ".join(usernames) + f" {room.started}", client_socket)
        else:
            sendWithSize('LEAVE_FAIL reason="Not in a room."', client_socket)

def cmdStart(player,client_socket,rooms_lock,rooms):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        with room.lock:
            if room.started:
                sendWithSize("START_FAIL reason='Game already started'", client_socket)
            elif len(room.players) < 2:
                sendWithSize("START_FAIL reason='Not enough players to start the game'", client_socket)
            else:
                room.started = True
                start_message = "The game has started!"
                for p in room.players:
                    sendWithSize(f"STARTING msg='{start_message}'", p.socket)
                
                room.start_turn()
    else:
        sendWithSize("START_FAIL reason='Player not in a room'", client_socket)

def cmdUsername(player,client_socket):
    sendWithSize(f"USERNAME_SUCCESS {player.username}",client_socket)

def cmdPosition(player,client_socket,rooms):

    board = rooms[player.room_id].board
    x = random.randint(0, 5)
    y = random.randint(0, 5)

    player.position = [x,y]

    while board[player.position[1]][player.position[0]] != None:
        player.position[1] = random.randint(0, 5)
        player.position[0] = random.randint(0, 5)

    board[player.position[1]][player.position[0]] = player
    
    sendWithSize(f"POSITION_SUCCESS {player.position[0]} {player.position[1]}",client_socket)

def cmdStatus(player, client_socket, rooms_lock, rooms):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        with room.lock:
            room.broadcast_game_state(client_socket)

def cmdChat(player,msg,client_socket, rooms_lock, rooms):
    with rooms_lock:
        room = rooms.get(player.room_id)
    if room:
        with room.lock:
            sendWithSize("CHAT_SUCCESS",client_socket)
            room.add_chat_message(player,msg)