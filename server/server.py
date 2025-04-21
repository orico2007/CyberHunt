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

def handle_client(client_socket, addr):

    secure = DiffieHellmanChannel()
    client_socket.send(str(secure.public).encode())  # Send server DH public key
    client_pub = int(client_socket.recv(4096).decode())
    secure.generate_shared_key(client_pub)

    player = Player(address=addr, socket=client_socket)
    with clients_lock:
        clients[client_socket] = player

    try:
        while True:
            msg = recvWithSize(client_socket, secure)
            if msg is None:
                print(f"[DISCONNECT] {addr} disconnected unexpectedly.")
                cleanup_player(client_socket,player,rooms_lock,rooms,clients,clients_lock, secure)
                break
            command = parse_command(msg)
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


    except Exception as e:
        print(f"[DISCONNECT] {addr} disconnected.")
        cleanup_player(client_socket,player,rooms_lock,rooms,clients,clients_lock, secure)

def main():
    s.bind(ADDR)
    s.listen()
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()