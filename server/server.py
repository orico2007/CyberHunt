import socket
import threading
from protocol import *
from KeyExchange import DiffieHellmanChannel, RSAChannel

ADDR = ("0.0.0.0", 5050)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

rooms = {}
clients = {}

rooms_lock = threading.Lock()
clients_lock = threading.Lock()

DEBUG = True

def debug_print(*args):
    if DEBUG:
        print("[DEBUG]", *args)


def handle_client(client_socket, addr):

    secure = DiffieHellmanChannel()
    client_socket.send(str(secure.public).encode())
    try:
        client_pub = int(client_socket.recv(4096).decode())
        secure.generate_shared_key(client_pub)
    except (ValueError, UnicodeDecodeError, TypeError) as e:
        print(f"[KEY EXCHANGE ERROR] {e}")
        debug_print(f"[KEY EXCHANGE ERROR] {e}")
        client_socket.close()
        return


    debug_print("key exchange complited!")

    player = Player(address=addr, socket=client_socket)
    with clients_lock:
        clients[client_socket] = player

    try:
        while True:
            msg = recvWithSize(client_socket, secure)
            if msg is None:

                debug_print(f"[DISCONNECT] {addr} disconnected unexpectedly.")

                print(f"[DISCONNECT] {addr} disconnected unexpectedly.")
                cleanup_player(client_socket,player,rooms_lock,rooms,clients,clients_lock, secure)
                break
            command = parse_command(msg)

            debug_print(command)

            match command['type']:
                case 'LOGIN':
                    cmdLogin(player,command,client_socket,clients, secure)
                case'REGISTER':
                    cmdRegister(player,command,client_socket, secure)
                case'JOIN':
                    cmdJoin(player,client_socket,rooms_lock,rooms, secure)
                case'CREATE':
                    cmdCreate(player,client_socket,rooms_lock,rooms, secure)
                case 'VIEW':
                    cmdView(client_socket,rooms_lock,rooms, secure)
                case action if action in ('SCAN', 'HACK', 'EVADE', 'ENCRYPT'):
                    cmdCommands(player,command,rooms_lock,rooms, secure)
                case 'PLAYERS':
                    cmdPlayers(player,client_socket,rooms_lock,rooms, secure)
                case 'LEAVE':
                    cmdLeave(player,client_socket,rooms_lock,rooms, secure)
                case 'START':
                    cmdStart(player,client_socket,rooms_lock,rooms, secure)
                case 'USERNAME':
                    cmdUsername(player,client_socket, secure)
                case 'POSITION':
                    cmdPosition(player,client_socket,rooms, secure)
                case 'STATUS':
                    cmdStatus(player, client_socket, rooms_lock, rooms, secure)
                case 'CHAT':
                    cmdChat(player, msg[msg.find("msg=")+4:], client_socket, rooms_lock, rooms, secure)
                case 'CREATE_BOT':
                    cmdBot(player,client_socket,rooms_lock,rooms, secure)
                case 'LEADERBOARD':
                    cmdLeaderboard(client_socket, secure)
                case 'END_TURN':
                    cmdEndTurn(player,rooms_lock,rooms, client_socket, secure)
                case 'JOIN_ROOM_NAME':
                    cmdJoinRoomName(player, command, client_socket, rooms_lock, rooms, secure)

    except Exception as e:
        debug_print(f"[DISCONNECT] {addr} disconnected.")
        print(f"[DISCONNECT] {addr} disconnected.")
        cleanup_player(client_socket,player,rooms_lock,rooms,clients,clients_lock, secure)

def main():
    try:
        s.bind(ADDR)
        s.listen()
    except socket.error as e:
        debug_print(f"[SOCKET ERROR] {e}")
        print(f"[SOCKET ERROR] {e}")
        exit(1)

    debug_print("SRVER IS RUNNING")
    print("SRVER IS RUNNING")
    while True:
        conn, addr = s.accept()
        debug_print(f"{conn, addr} added!")
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()