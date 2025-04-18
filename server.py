import socket
import threading
from protocol import *

USERS_FILE = "users.json"
ADDR = ("0.0.0.0", 5050)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

rooms = {}
clients = {}

rooms_lock = threading.Lock()
clients_lock = threading.Lock()

def handle_client(client_socket, addr):
    player = Player(address=addr, socket=client_socket)
    with clients_lock:
        clients[client_socket] = player

    try:
        while True:
            msg = recvWithSize(client_socket)
            if msg is None:
                print(f"[DISCONNECT] {addr} disconnected unexpectedly.")
                break
            command = parse_command(msg)
            match command['type']:
                case 'LOGIN':
                    cmdLogin(player,command,client_socket,clients)
                case'REGISTER':
                    cmdRegister(player,command,client_socket)
                case'JOIN':
                    cmdJoin(player,client_socket,rooms_lock,rooms)
                case'CREATE':
                    cmdCreate(player,client_socket,rooms_lock,rooms)
                case 'VIEW':
                    cmdView(client_socket,rooms_lock,rooms)
                case action if action in ('SCAN', 'HACK', 'EVADE', 'ENCRYPT'):
                    cmdCommands(player,command,rooms_lock,rooms)
                case 'PLAYERS':
                    cmdPlayers(player,client_socket,rooms_lock,rooms)
                case 'LEAVE':
                    cmdLeave(player,client_socket,rooms_lock,rooms)
                case 'START':
                    cmdStart(player,client_socket,rooms_lock,rooms)
                case 'USERNAME':
                    cmdUsername(player,client_socket)
                case 'POSITION':
                    cmdPosition(player,client_socket,rooms)
                case 'STATUS':
                    cmdStatus(player, client_socket, rooms_lock, rooms)
                case 'CHAT':
                    print(msg)
                    cmdChat(player, msg[msg.find("msg=")+4:], client_socket, rooms_lock, rooms)


    except Exception as e:
        print(f"[DISCONNECT] {addr} disconnected.")
        cleanup_player(client_socket,player,rooms_lock,rooms,clients,clients_lock)

def main():
    s.bind(ADDR)
    s.listen()
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()