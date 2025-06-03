import socket
import threading

from protocol import *
from KeyExchange import DiffieHellmanChannel, RSAChannel

# Server configuration
ADDR = ("0.0.0.0", 5050)
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Shared resources
rooms = {}
clients = {}

# Thread locks
rooms_lock = threading.Lock()
clients_lock = threading.Lock()

DEBUG = False

def debug_print(*args):
    if DEBUG:
        print("[DEBUG]", *args)

def handle_client(client_socket, addr):
    secure = DiffieHellmanChannel()

    try:
        # Key exchange
        client_socket.send(str(secure.public).encode())
        client_pub = int(client_socket.recv(4096).decode())
        secure.generate_shared_key(client_pub)
        debug_print("Key exchange completed!")

    except (ValueError, UnicodeDecodeError, TypeError) as e:
        print(f"[KEY EXCHANGE ERROR] {e}")
        debug_print(f"[KEY EXCHANGE ERROR] {e}")
        client_socket.close()
        return

    player = Player(address=addr, socket=client_socket)

    with clients_lock:
        clients[client_socket] = player

    try:
        while True:
            msg = recvWithSize(client_socket, secure)
            if msg is None:
                print(f"[DISCONNECT] {addr} disconnected unexpectedly.")
                debug_print(f"[DISCONNECT] {addr} disconnected unexpectedly.")
                cleanup_player(client_socket, player, rooms_lock, rooms, clients, clients_lock, secure)
                break

            command = parse_command(msg)
            debug_print(command)

            match command['type']:
                case 'LOGIN':
                    cmdLogin(player, command, client_socket, clients, secure)
                case 'REGISTER':
                    cmdRegister(player, command, client_socket, secure)
                case 'JOIN':
                    cmdJoin(player, client_socket, rooms_lock, rooms, secure)
                case 'CREATE':
                    cmdCreate(player, client_socket, rooms_lock, rooms, secure)
                case 'VIEW':
                    cmdView(client_socket, rooms_lock, rooms, secure)
                case action if action in ('SCAN', 'HACK', 'EVADE', 'ENCRYPT'):
                    cmdCommands(player, command, rooms_lock, rooms, secure)
                case 'PLAYERS':
                    cmdPlayers(player, client_socket, rooms_lock, rooms, secure)
                case 'LEAVE':
                    cmdLeave(player, client_socket, rooms_lock, rooms, secure)
                case 'START':
                    cmdStart(player, client_socket, rooms_lock, rooms, secure)
                case 'USERNAME':
                    cmdUsername(player, client_socket, secure)
                case 'POSITION':
                    cmdPosition(player, client_socket, rooms, secure)
                case 'STATUS':
                    cmdStatus(player, client_socket, rooms_lock, rooms, secure)
                case 'CHAT':
                    msg_content = msg[msg.find("msg=") + 4:]
                    cmdChat(player, msg_content, client_socket, rooms_lock, rooms, secure)
                case 'CREATE_BOT':
                    cmdBot(player, client_socket, rooms_lock, rooms, secure)
                case 'LEADERBOARD':
                    cmdLeaderboard(client_socket, secure)
                case 'END_TURN':
                    cmdEndTurn(player, rooms_lock, rooms, client_socket, secure)
                case 'JOIN_ROOM_NAME':
                    cmdJoinRoomName(player, command, client_socket, rooms_lock, rooms, secure)

    except Exception as e:
        print(f"[DISCONNECT] {addr} disconnected.")
        debug_print(f"[DISCONNECT] {addr} disconnected due to error: {e}")
        cleanup_player(client_socket, player, rooms_lock, rooms, clients, clients_lock, secure)

def main():
    try:
        server_socket.bind(ADDR)
        server_socket.listen()
    except socket.error as e:
        print(f"[SOCKET ERROR] {e}")
        debug_print(f"[SOCKET ERROR] {e}")
        exit(1)

    print("SERVER IS RUNNING")
    debug_print("SERVER IS RUNNING")

    while True:
        conn, addr = server_socket.accept()
        debug_print(f"New connection: {addr}")
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
