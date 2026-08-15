import os
import base64
import hashlib

def get_machine_key() -> bytes:
	"""Generate a unique machine key based on user and OS information."""
	try:
		raw_id = f"{os.getenv('COMPUTERNAME', '')}-{os.getenv('USERNAME', '')}-{os.getenv('USERDOMAIN', '')}"
		if raw_id == "--":
			raw_id = "default_gemini_dich_truyen_secret_key"
		return hashlib.sha256(raw_id.encode("utf-8")).digest()
	except Exception:
		return hashlib.sha256(b"default_gemini_dich_truyen_secret_key").digest()


def xor_encrypt(data: str, key: bytes) -> str:
	"""Encrypt text data using simple XOR with key and base64 encoding."""
	if not data:
		return ""
	data_bytes = data.encode("utf-8")
	encrypted_bytes = bytearray()
	key_len = len(key)
	for i, b in enumerate(data_bytes):
		encrypted_bytes.append(b ^ key[i % key_len])
	return base64.b64encode(encrypted_bytes).decode("ascii")


def xor_decrypt(encrypted_data: str, key: bytes) -> str:
	"""Decrypt base64 XOR encrypted text."""
	if not encrypted_data:
		return ""
	try:
		encrypted_bytes = base64.b64decode(encrypted_data.encode("ascii"))
		decrypted_bytes = bytearray()
		key_len = len(key)
		for i, b in enumerate(encrypted_bytes):
			decrypted_bytes.append(b ^ key[i % key_len])
		return decrypted_bytes.decode("utf-8")
	except Exception:
		return ""


def encrypt_api_key(api_key: str) -> str:
	key = get_machine_key()
	return xor_encrypt(api_key, key)


def decrypt_api_key(encrypted_key: str) -> str:
	key = get_machine_key()
	return xor_decrypt(encrypted_key, key)
