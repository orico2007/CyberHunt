from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
from Crypto.Hash import SHA256
from Crypto.Util.Padding import pad, unpad
from Crypto.PublicKey import RSA
import random

PRIME = 2**2048 - 159  # a big prime
GENERATOR = 2

class DiffieHellmanChannel:
    def __init__(self):
        self.private = random.randint(2, PRIME - 2)
        self.public = pow(GENERATOR, self.private, PRIME)
        self.shared_key = None

    def generate_shared_key(self, other_public):
        # Compute the shared secret using the other party's public key
        shared_secret = pow(other_public, self.private, PRIME)
        sha = SHA256.new()
        sha.update(str(shared_secret).encode())
        self.shared_key = sha.digest()[:16]  # Use only the first 16 bytes (AES-128)

    def encrypt(self, message):
        if isinstance(message, str):
            message_bytes = message.encode()  # Convert string to bytes
        elif isinstance(message, bytes):
            message_bytes = message  # Message is already in bytes
        else:
            raise TypeError("Message must be a string or bytes")

        # Pad the message to a 16-byte boundary
        padded_message = pad(message_bytes, AES.block_size)  # Pad to a multiple of 16 bytes
        iv = get_random_bytes(AES.block_size)  # Generate a random IV
        
        cipher = AES.new(self.shared_key, AES.MODE_CBC, iv)
        encrypted_message = cipher.encrypt(padded_message)  # Encrypt the padded message
        return iv + encrypted_message  # Return IV + encrypted message

    def decrypt(self, encrypted_message):
        iv = encrypted_message[:AES.block_size]  # Extract the IV from the beginning
        ciphertext = encrypted_message[AES.block_size:]  # Extract the ciphertext

        cipher = AES.new(self.shared_key, AES.MODE_CBC, iv)
        decrypted_message = unpad(cipher.decrypt(ciphertext), AES.block_size)  # Unpad after decryption
        return decrypted_message.decode()  # Convert bytes back to string


class RSAChannel:
    def __init__(self):
        key = RSA.generate(2048)
        self.private_key = key
        self.public_key = key.publickey()

    def get_public_key_bytes(self):
        return self.public_key.export_key()

    def load_peer_public_key(self, peer_key_bytes):
        self.peer_key = RSA.import_key(peer_key_bytes)
        self.cipher = PKCS1_OAEP.new(self.peer_key)

    def encrypt(self, plaintext):
        if isinstance(plaintext, str):
            plaintext = plaintext.encode()
        return self.cipher.encrypt(plaintext)  # returns bytes

    def decrypt(self, data):
        cipher = PKCS1_OAEP.new(self.private_key)
        return cipher.decrypt(data)
