import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if (root / ".env").exists():
    raise SystemExit(".env уже существует, данные не изменены.")
password = secrets.token_urlsafe(20)
content = (root / ".env.example").read_text().replace("generate-a-long-random-secret", secrets.token_urlsafe(64)).replace("generate-a-random-password", secrets.token_urlsafe(40)).replace("set-a-long-random-initial-password", password)
for name, data in [(".env", content), (".local-access.txt", "Адрес: http://localhost:8096\nЛогин: department\nПароль: " + password + "\n\nЭто начальный пароль. Смените его через меню учётной записи.\n")]:
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(data)
print("Созданы .env и .local-access.txt с правами 600.")
