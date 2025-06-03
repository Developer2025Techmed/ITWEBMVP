import secrets
strong_key = secrets.token_hex(32) # Generates a 64-character hexadecimal string
print(strong_key)
