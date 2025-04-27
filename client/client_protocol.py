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

    if isinstance(decrypted, str):
        return decrypted
    else:
        return decrypted.decode()

def parse_command(msg):
    parts = msg.strip().split()
    cmd_type = parts[0]
    args = {}

    for part in parts[1:]:
        if '=' in part:
            key, value = part.split('=', 1)
            args[key] = value
    return {'type': cmd_type, 'args': args}

def send_command(cmd, client_socket, secure):
    sendWithSize(cmd, client_socket, secure)
    returned = recvWithSize(client_socket, secure)
    returnedP = parse_command(returned)
    cmdType = cmd.split()[0]
    if cmdType in ["SCAN", "HACK", "ENCRYPT", "EVADE"]:
        while not returnedP["type"].startswith("ACTION_RESULT"):
            returned = recvWithSize(client_socket, secure)
            returnedP = parse_command(returned)
    elif cmdType == "LEADERBOARD":
        return returned
    else:
        while not cmdType in returnedP["type"]:
            returned = recvWithSize(client_socket, secure)
            returnedP = parse_command(returned)
    return returned

def parse_status(response):
    parts = response.split("|")
    print(parts)
    return [parse_command(parts[0]),parse_command(parts[1]),parse_command(parts[2]) if parts[2] else ""]

