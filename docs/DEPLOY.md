# Deployment для Макса

Ниже — рекомендуемый single-server deployment на Linux (Ubuntu/Debian-подобная система).

## Что нужно на сервере

- Python **3.12.x**
- `python3-venv`, `pip`
- Git
- Nginx (если нужен домен/HTTPS/reverse proxy)
- systemd

**Node.js / npm не нужны.** Frontend уже статический и обслуживается FastAPI.

## 1. Клонирование

```bash
sudo mkdir -p /opt/sber-transport-assistant
sudo chown "$USER":"$USER" /opt/sber-transport-assistant
git clone https://github.com/Gavrilov71/sber-transport-assistant.git /opt/sber-transport-assistant
cd /opt/sber-transport-assistant
```

## 2. Python environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Если `python3.12` называется на сервере просто `python3`, используйте `python3`, предварительно проверив `python3 --version`.

## 3. `.env`

`.env` намеренно отсутствует в Git. Создать вручную:

```bash
cp .env.example .env
nano .env
```

Минимум заполнить:

```env
APP_ENV=production
APP_HOST=127.0.0.1
APP_PORT=8000
GIGACHAT_CREDENTIALS=<Authorization Key>
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_MODEL=GigaChat-3-Ultra
GIGACHAT_VERIFY_SSL=false
```

Права:

```bash
chmod 600 .env
```

Никогда не добавлять `.env` в Git.

## 4. Проверка до systemd

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

В другом терминале:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/diagnostics/gigachat
```

`/api/health` должен вернуть `status: ok`, а после настройки GigaChat `agent_ready` должен стать `true`.

## 5. systemd

Создать `/etc/systemd/system/sber-transport.service`:

```ini
[Unit]
Description=SBER Transport Assistant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/sber-transport-assistant
EnvironmentFile=/opt/sber-transport-assistant/.env
ExecStart=/opt/sber-transport-assistant/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Перед запуском отдать каталог сервисному пользователю либо выбрать отдельного пользователя приложения:

```bash
sudo chown -R www-data:www-data /opt/sber-transport-assistant
sudo systemctl daemon-reload
sudo systemctl enable --now sber-transport
sudo systemctl status sber-transport
```

### Почему один worker

Conversation state сейчас хранится в памяти процесса. Несколько Uvicorn workers получили бы разные состояния диалога. Пока не добавлен Redis/БД, используйте `--workers 1`.

## 6. Nginx

Пример `/etc/nginx/sites-available/sber-transport`:

```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN;

    client_max_body_size 2m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

Затем:

```bash
sudo ln -s /etc/nginx/sites-available/sber-transport /etc/nginx/sites-enabled/sber-transport
sudo nginx -t
sudo systemctl reload nginx
```

HTTPS можно добавить Certbot или инфраструктурным способом сервера.

## 7. Обновление

```bash
cd /opt/sber-transport-assistant
sudo -u www-data git pull --ff-only
sudo -u www-data .venv/bin/pip install -r requirements.txt
sudo systemctl restart sber-transport
curl http://127.0.0.1:8000/api/health
```

Перед production update желательно:

```bash
GIGACHAT_CREDENTIALS=test-placeholder-for-mocked-tests .venv/bin/python -m pytest -q
```

## 8. Rollback

Сначала посмотреть историю:

```bash
git log --oneline -10
```

Затем вернуть известный стабильный commit и перезапустить сервис. На production не делайте произвольный `git reset --hard` без фиксации текущего commit SHA.

## 9. Что не должно попадать на сервер из локальной разработки

- `.venv/` или `.venv-new/` с Windows;
- `.env` из рабочего компьютера;
- `references/` с исходниками дизайна;
- `raw_sources/` и большие PDF-кэши;
- `.pytest_cache/`, `__pycache__/`, IDE-файлы;
- вложенная копия `sber-main/sber-main/`.

Сервер сам создаёт Linux `.venv` из `requirements.txt`.
