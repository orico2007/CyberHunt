

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

def parse_command(msg):
    parts = msg.strip().split()
    cmd_type = parts[0]
    args = {}

    for part in parts[1:]:
        if '=' in part:
            key, value = part.split('=', 1)
            args[key] = value

    return {'type': cmd_type, 'args': args}

def send_command(cmd, client_socket):
    sendWithSize(cmd, client_socket)
    returned = recvWithSize(client_socket)
    returnedP = parse_command(returned)
    cmdType = cmd.split()[0]
    if cmdType in ["SCAN", "HACK", "ENCRYPT", "EVADE"]:
        while not returnedP["type"].startswith("ACTION_RESULT"):
            returned = recvWithSize(client_socket)
            returnedP = parse_command(returned)
    else:
        while not cmdType in returnedP["type"]:
            returned = recvWithSize(client_socket)
            returnedP = parse_command(returned)

    return returned

def parse_status(response):
    parts = response.split("|")
    print(parts)
    return [parse_command(parts[0]),parse_command(parts[1]),parse_command(parts[2]) if parts[2] else ""]

