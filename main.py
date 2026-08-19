import asyncio, logging, sqlite3, random, os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
def get_db_connection():
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if DATABASE_URL and PSYCOPG2_AVAILABLE:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    return sqlite3.connect("anicard_chat_stats.db")
TOKEN = "8415798182:AAG1-OkNu4Ur9uj4e4mWHD2yjPwNNoMp0JA"
ADMIN_USERNAME = ["Ale7xey", "femfoy"]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

event_active = False
boss_name = "Монстр"
boss_hp = 0
boss_max_hp = 1000
last_speakers = {}

# ==================== ДЛЯ СИСТЕМЫ ЛОТОВ ====================
LOT_ADMINS = [1288349934, 5351220125, 5764862480, 7292012107, 6234768539, 1633881251, 6021297158]
pending_lots = {}
lot_counter = 1
admin_messages = {}


def init_event_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS user_profiles (
        user_id INTEGER PRIMARY KEY, 
        username TEXT, 
        first_name TEXT, 
        message_count INTEGER DEFAULT 0, 
        rank INTEGER DEFAULT 0
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS daily_stats (
        user_id INTEGER, 
        msg_date TEXT, 
        message_count INTEGER DEFAULT 0, 
        PRIMARY KEY (user_id, msg_date)
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS match_damage (
        user_id INTEGER PRIMARY KEY, 
        damage_dealt INTEGER DEFAULT 0
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS prizes_pool (
        id SERIAL PRIMARY KEY, 
        prize_text TEXT
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS user_prizes (
        id SERIAL PRIMARY KEY, 
        user_id INTEGER, 
        prize_text TEXT
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS game_cards (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        rating INTEGER DEFAULT 0,
        price REAL DEFAULT 0,
        UNIQUE(name, rating)
    )""")

    # ========== ОБЛОЖКИ ==========
    cursor.execute("""CREATE TABLE IF NOT EXISTS covers (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        rating INTEGER DEFAULT 0,
        price REAL DEFAULT 0,
        emoji TEXT DEFAULT '📁',
        description TEXT
    )""")

    # ========== КОЛЛЕКЦИОННЫЕ КАРТЫ ==========
    cursor.execute("""CREATE TABLE IF NOT EXISTS collection_cards (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        rarity TEXT DEFAULT 'Эпическая',
        price REAL DEFAULT 0,
        emoji TEXT DEFAULT '🟪',
        description TEXT,
        cover_id INTEGER,
        FOREIGN KEY (cover_id) REFERENCES covers(id)
    )""")

    # ========== КОЛЛЕКЦИИ ИГРОКОВ ==========
    cursor.execute("""CREATE TABLE IF NOT EXISTS user_collection_cards (
        user_id INTEGER,
        card_id INTEGER,
        quantity INTEGER DEFAULT 1,
        acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, card_id),
        FOREIGN KEY (card_id) REFERENCES collection_cards(id)
    )""")

    # ========== ТАБЛИЦА ДЛЯ ЛОТОВ ==========
    cursor.execute("""CREATE TABLE IF NOT EXISTS lots (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        username TEXT,
        first_name TEXT,
        description TEXT,
        file_id TEXT,
        status TEXT DEFAULT 'pending',
        accepted_by INTEGER,
        published_by INTEGER,
        created_at TEXT,
        updated_at TEXT
    )""")

    conn.commit()
    conn.close()


def migrate_db():
    """Обновляет базу данных - добавляет новые колонки"""
    conn = get_db_connection()
    cursor = conn.cursor()
    using_postgres = is_postgres()

    try:
        if using_postgres:
            # PostgreSQL — проверяем через information_schema
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'covers'
            """)
            columns = [row[0] for row in cursor.fetchall()]

            if 'rating' not in columns:
                print("🔄 Добавляем колонку rating в covers...")
                cursor.execute("ALTER TABLE covers ADD COLUMN rating INTEGER DEFAULT 0")
                print("✅ Колонка rating добавлена в covers")

            if 'price' not in columns:
                print("🔄 Добавляем колонку price в covers...")
                cursor.execute("ALTER TABLE covers ADD COLUMN price REAL DEFAULT 0")
                print("✅ Колонка price добавлена в covers")

            if 'emoji' not in columns:
                print("🔄 Добавляем колонку emoji в covers...")
                cursor.execute("ALTER TABLE covers ADD COLUMN emoji TEXT DEFAULT '📁'")
                print("✅ Колонка emoji добавлена в covers")

            if 'description' not in columns:
                print("🔄 Добавляем колонку description в covers...")
                cursor.execute("ALTER TABLE covers ADD COLUMN description TEXT")
                print("✅ Колонка description добавлена в covers")

            # Проверяем таблицу collection_cards
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'collection_cards'
            """)
            columns = [row[0] for row in cursor.fetchall()]

            if 'cover_id' not in columns:
                print("🔄 Добавляем колонку cover_id в collection_cards...")
                cursor.execute("ALTER TABLE collection_cards ADD COLUMN cover_id INTEGER")
                print("✅ Колонка cover_id добавлена в collection_cards")

            if 'description' not in columns:
                print("🔄 Добавляем колонку description в collection_cards...")
                cursor.execute("ALTER TABLE collection_cards ADD COLUMN description TEXT")
                print("✅ Колонка description добавлена в collection_cards")

            if 'emoji' not in columns:
                print("🔄 Добавляем колонку emoji в collection_cards...")
                cursor.execute("ALTER TABLE collection_cards ADD COLUMN emoji TEXT DEFAULT '🟪'")
                print("✅ Колонка emoji добавлена в collection_cards")

        else:
            # SQLite — используем PRAGMA
            cursor.execute("PRAGMA table_info(covers)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'rating' not in columns:
                print("🔄 Добавляем колонку rating в covers...")
                cursor.execute("ALTER TABLE covers ADD COLUMN rating INTEGER DEFAULT 0")
                print("✅ Колонка rating добавлена в covers")

            if 'price' not in columns:
                print("🔄 Добавляем колонку price в covers...")
                cursor.execute("ALTER TABLE covers ADD COLUMN price REAL DEFAULT 0")
                print("✅ Колонка price добавлена в covers")

            if 'emoji' not in columns:
                print("🔄 Добавляем колонку emoji в covers...")
                cursor.execute("ALTER TABLE covers ADD COLUMN emoji TEXT DEFAULT '📁'")
                print("✅ Колонка emoji добавлена в covers")

            if 'description' not in columns:
                print("🔄 Добавляем колонку description в covers...")
                cursor.execute("ALTER TABLE covers ADD COLUMN description TEXT")
                print("✅ Колонка description добавлена в covers")

            cursor.execute("PRAGMA table_info(collection_cards)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'cover_id' not in columns:
                print("🔄 Добавляем колонку cover_id в collection_cards...")
                cursor.execute("ALTER TABLE collection_cards ADD COLUMN cover_id INTEGER")
                print("✅ Колонка cover_id добавлена в collection_cards")

            if 'description' not in columns:
                print("🔄 Добавляем колонку description в collection_cards...")
                cursor.execute("ALTER TABLE collection_cards ADD COLUMN description TEXT")
                print("✅ Колонка description добавлена в collection_cards")

            if 'emoji' not in columns:
                print("🔄 Добавляем колонку emoji в collection_cards...")
                cursor.execute("ALTER TABLE collection_cards ADD COLUMN emoji TEXT DEFAULT '🟪'")
                print("✅ Колонка emoji добавлена в collection_cards")

        conn.commit()
        print("✅ Миграция базы данных завершена!")

    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")

    conn.close()

def load_lots_from_db():
    """Загружает все лоты из базы данных при запуске бота"""
    global lot_counter, pending_lots

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, user_id, username, first_name, description, file_id, 
               status, accepted_by, published_by, created_at
        FROM lots
        WHERE status IN ('pending', 'accepted', 'published')
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    pending_lots = {}

    for row in rows:
        lot_id, user_id, username, first_name, description, file_id, status, accepted_by, published_by, created_at = row

        lot_data = {
            "id": lot_id,
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "description": description,
            "file_id": file_id,
            "status": status,
            "accepted_by": accepted_by,
            "published_by": published_by,
            "created_at": created_at
        }

        pending_lots[lot_id] = lot_data

        if lot_id >= lot_counter:
            lot_counter = lot_id + 1

    print(f"📦 Загружено лотов из БД: {len(pending_lots)}")


def save_lot_to_db(lot_data):
    """Сохраняет или обновляет лот в базе данных"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM lots WHERE id = ?", (lot_data["id"],))
    exists = cursor.fetchone()

    if exists:
        cursor.execute("""
            UPDATE lots SET
                status = ?,
                accepted_by = ?,
                published_by = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            lot_data["status"],
            lot_data.get("accepted_by"),
            lot_data.get("published_by"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            lot_data["id"]
        ))
    else:
        cursor.execute("""
            INSERT INTO lots (
                id, user_id, username, first_name, description, file_id, 
                status, accepted_by, published_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lot_data["id"],
            lot_data["user_id"],
            lot_data["username"],
            lot_data["first_name"],
            lot_data["description"],
            lot_data["file_id"],
            lot_data["status"],
            lot_data.get("accepted_by"),
            lot_data.get("published_by"),
            lot_data["created_at"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    conn.commit()
    conn.close()


def delete_lot_from_db(lot_id):
    """Удаляет лот из базы данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lots WHERE id = ?", (lot_id,))
    conn.commit()
    conn.close()


# ==================== АДМИН-КОМАНДЫ ====================

# ---------- ОБЫЧНЫЕ КАРТЫ ----------

@dp.message(Command("картплюс"))
async def add_card(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("⛔ Только для админов!")
        return

    parts = message.text.split()
    if len(parts) < 4:
        await message.answer(
            "❌ Используйте: /картплюс Название Рейтинг Цена\n"
            "Пример: /картплюс Сид 90 150.5"
        )
        return

    try:
        price = float(parts[-1])
        rating = int(parts[-2])
    except ValueError:
        await message.answer("❌ Рейтинг и цена должны быть числами!")
        return

    name = " ".join(parts[1:-2])

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO game_cards (name, rating, price) VALUES (?, ?, ?)",
            (name, rating, price)
        )
        conn.commit()
        price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
        await message.answer(
            f"✅ Карта {name} добавлена!\n"
            f"⭐ Рейтинг: {rating}\n"
            f"💰 Цена: {price_str} ПТ"
        )
    except sqlite3.IntegrityError:
        await message.answer(f"❌ Карта {name} с рейтингом {rating} уже существует!")

    conn.close()


@dp.message(Command("картминус"))
async def remove_card(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("⛔ Только для админов!")
        return

    parts = message.text.split()
    if len(parts) < 3 or not parts[-1].isdigit():
        await message.answer(
            "❌ Используйте: /картминус Название Рейтинг\n"
            "Пример: /картминус Сид 90"
        )
        return

    name = " ".join(parts[1:-1])
    rating = int(parts[-1])

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM game_cards WHERE name = ? AND rating = ?", (name, rating))

    if cursor.rowcount == 0:
        await message.answer(f"❌ Карта {name} с рейтингом {rating} не найдена!")
    else:
        conn.commit()
        await message.answer(f"🗑️ Карта {name} (⭐{rating}) удалена!")

    conn.close()


@dp.message(Command("карты"))
async def show_all_cards(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("⛔ Только для админов!")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, rating, price FROM game_cards ORDER BY name, rating")
    cards = cursor.fetchall()
    conn.close()

    if not cards:
        await message.answer("📭 В базе нет карт!")
        return

    mid = len(cards) // 2
    first_half = cards[:mid]
    second_half = cards[mid:]

    text1 = "🃏 ВСЕ КАРТЫ (1/2)\n━━━━━━━━━━━━━━━━━━\n"
    for name, rating, price in first_half:
        price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
        text1 += f"• {name} ⭐{rating} — {price_str} ПТ\n"
    await message.answer(text1)

    if second_half:
        text2 = "🃏 ВСЕ КАРТЫ (2/2)\n━━━━━━━━━━━━━━━━━━\n"
        for name, rating, price in second_half:
            price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
            text2 += f"• {name} ⭐{rating} — {price_str} ПТ\n"
        await message.answer(text2)


# ---------- ОБЛОЖКИ ----------

@dp.message(Command("облплюс"))
async def add_cover(message: types.Message):
    """Добавить обложку: /облплюс Название Рейтинг Цена"""
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("⛔ Только для админов!")
        return

    parts = message.text.split()
    if len(parts) < 4:
        await message.answer(
            "❌ Используйте: /облплюс Название Рейтинг Цена\n"
            "Пример: /облплюс Аниме 85 150.5"
        )
        return

    try:
        price = float(parts[-1])
        rating = int(parts[-2])
    except ValueError:
        await message.answer("❌ Рейтинг и цена должны быть числами!")
        return

    name = " ".join(parts[1:-2])

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO covers (name, rating, price) VALUES (?, ?, ?)",
            (name, rating, price)
        )
        conn.commit()
        price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
        await message.answer(
            f"✅ Обложка «{name}» добавлена!\n"
            f"⭐ Рейтинг: {rating}\n"
            f"💰 Цена: {price_str} ПТ"
        )
    except sqlite3.IntegrityError:
        await message.answer(f"❌ Обложка «{name}» уже существует!")

    conn.close()


@dp.message(Command("облминус"))
async def remove_cover(message: types.Message):
    """Удалить обложку: /облминус Название"""
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("⛔ Только для админов!")
        return

    name = message.text.replace("/облминус", "").strip()
    if not name:
        await message.answer("❌ Используйте: /облминус Название")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM covers WHERE name = ?", (name,))
    if cursor.rowcount == 0:
        await message.answer(f"❌ Обложка «{name}» не найдена!")
    else:
        conn.commit()
        await message.answer(f"🗑️ Обложка «{name}» удалена!")

    conn.close()


@dp.message(Command("обл"))
async def show_covers(message: types.Message):
    """Показать все обложки: /обл"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, rating, price, emoji, description
        FROM covers
        ORDER BY name
    """)
    covers = cursor.fetchall()
    conn.close()

    if not covers:
        await message.answer("📭 Нет обложек! Добавьте: /облплюс Название Рейтинг Цена")
        return

    text = "📁 ВСЕ ОБЛОЖКИ\n━━━━━━━━━━━━━━━━━━\n"
    for cover_id, name, rating, price, emoji, description in covers:
        price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
        text += f"{emoji} {name} ⭐{rating} — {price_str} ПТ (ID: {cover_id})\n"
        if description:
            text += f"   📝 {description}\n"
        text += "\n"

    await message.answer(text)


# ---------- КОЛЛЕКЦИОННЫЕ КАРТЫ ----------

@dp.message(Command("колплюс"))
async def add_collection_card(message: types.Message):
    """Добавить коллекционную карту: /колплюс Название Редкость Цена"""
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("⛔ Только для админов!")
        return

    parts = message.text.split()
    if len(parts) < 4:
        await message.answer(
            "❌ Используйте: /колплюс Название Редкость Цена\n"
            "Пример: /колплюс Джотаро Легендарная 200\n\n"
            "⭐ Редкости: Эпическая, Легендарная, Мифическая"
        )
        return

    try:
        price = float(parts[-1])
    except ValueError:
        await message.answer("❌ Цена должна быть числом!")
        return

    rarity = parts[-2]
    name = " ".join(parts[1:-2])

    valid_rarities = ["Эпическая", "Легендарная", "Мифическая"]
    if rarity not in valid_rarities:
        await message.answer(
            f"❌ Неверная редкость!\n"
            f"Доступные: {', '.join(valid_rarities)}"
        )
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    rarity_emojis = {
        "Эпическая": "🟪",
        "Легендарная": "🟧",
        "Мифическая": "🔴"
    }

    try:
        cursor.execute(
            "INSERT INTO collection_cards (name, rarity, price, emoji) VALUES (?, ?, ?, ?)",
            (name, rarity, price, rarity_emojis.get(rarity, "🟪"))
        )
        conn.commit()
        price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
        await message.answer(
            f"✅ Коллекционная карта «{name}» добавлена!\n"
            f"{rarity_emojis.get(rarity, '🟪')} Редкость: {rarity}\n"
            f"💰 Цена: {price_str} ПТ"
        )
    except sqlite3.IntegrityError:
        await message.answer(f"❌ Карта «{name}» уже существует!")

    conn.close()


@dp.message(Command("колминус"))
async def remove_collection_card(message: types.Message):
    """Удалить коллекционную карту: /колминус Название"""
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("⛔ Только для админов!")
        return

    name = message.text.replace("/колминус", "").strip()
    if not name:
        await message.answer("❌ Используйте: /колминус Название")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM collection_cards WHERE name = ?", (name,))
    if cursor.rowcount == 0:
        await message.answer(f"❌ Карта «{name}» не найдена!")
    else:
        conn.commit()
        await message.answer(f"🗑️ Коллекционная карта «{name}» удалена!")

    conn.close()


@dp.message(Command("кол"))
async def show_collection_cards(message: types.Message):
    """Показать все коллекционные карты: /кол (разбито на 2 части)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, rarity, price, emoji, description
        FROM collection_cards
        ORDER BY 
            CASE rarity
                WHEN 'Мифическая' THEN 1
                WHEN 'Легендарная' THEN 2
                WHEN 'Эпическая' THEN 3
            END,
            name
    """)
    cards = cursor.fetchall()
    conn.close()

    if not cards:
        await message.answer("📭 Нет коллекционных карт! Добавьте: /колплюс Название Редкость Цена")
        return

    # Группируем по редкости
    grouped = {}
    for card in cards:
        rarity = card[2]
        if rarity not in grouped:
            grouped[rarity] = []
        grouped[rarity].append(card)

    rarity_order = ["Мифическая", "Легендарная", "Эпическая"]

    # Формируем полный текст
    all_text = ""
    for rarity in rarity_order:
        if rarity in grouped:
            all_text += f"\n⭐ {rarity}:\n"
            for card in grouped[rarity]:
                card_id, name, r, price, emoji, description = card
                price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
                all_text += f"  {emoji} {name} — {price_str} ПТ (ID: {card_id})\n"
                if description:
                    all_text += f"     📝 {description}\n"

    # Разбиваем на 2 части
    mid = len(all_text) // 2
    # Ищем место для разрыва (после строки с редкостью)
    split_pos = all_text.rfind('\n⭐', 0, mid)
    if split_pos == -1:
        split_pos = mid

    part1 = "🃏 КОЛЛЕКЦИОННЫЕ КАРТЫ (1/2)\n━━━━━━━━━━━━━━━━━━\n" + all_text[:split_pos].strip()
    part2 = "🃏 КОЛЛЕКЦИОННЫЕ КАРТЫ (2/2)\n━━━━━━━━━━━━━━━━━━\n" + all_text[split_pos:].strip()

    # Отправляем
    await message.answer(part1)
    await message.answer(part2)

@dp.message(Command("дать_кол"))
async def give_collection_card(message: types.Message):
    """Выдать коллекционную карту: /дать_кол @username Название [количество]"""
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("⛔ Только для админов!")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "❌ Используйте: /дать_кол @username Название [количество]\n"
            "Пример: /дать_кол @Ale7xey Джотаро 2"
        )
        return

    username = parts[1].replace("@", "")
    card_name = " ".join(parts[2:-1]) if len(parts) > 3 else parts[2]
    quantity = int(parts[-1]) if len(parts) > 3 and parts[-1].isdigit() else 1

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM user_profiles WHERE username = ?", (f"@{username}",))
    user_row = cursor.fetchone()
    if not user_row:
        await message.answer(f"❌ Пользователь @{username} не найден!")
        conn.close()
        return

    user_id = user_row[0]

    cursor.execute("SELECT id, name FROM collection_cards WHERE name = ?", (card_name,))
    card_row = cursor.fetchone()
    if not card_row:
        await message.answer(f"❌ Коллекционная карта «{card_name}» не найдена!")
        conn.close()
        return

    card_id, card_name_db = card_row

    cursor.execute("""
        INSERT INTO user_collection_cards (user_id, card_id, quantity) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, card_id) 
        DO UPDATE SET quantity = quantity + ?
    """, (user_id, card_id, quantity, quantity))

    conn.commit()
    conn.close()

    await message.answer(f"✅ Коллекционная карта «{card_name_db}» (x{quantity}) выдана @{username}!")


@dp.message(Command("мои_кол"))
async def show_my_collection_cards(message: types.Message):
    """Показать мои коллекционные карты: /мои_кол"""
    user_id = message.from_user.id

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT cc.name, cc.rarity, cc.price, cc.emoji, uc.quantity
        FROM user_collection_cards uc
        JOIN collection_cards cc ON uc.card_id = cc.id
        WHERE uc.user_id = ?
        ORDER BY 
            CASE cc.rarity
                WHEN 'Мифическая' THEN 1
                WHEN 'Легендарная' THEN 2
                WHEN 'Эпическая' THEN 3
            END,
            cc.name
    """, (user_id,))

    cards = cursor.fetchall()
    conn.close()

    if not cards:
        await message.answer("📭 У вас нет коллекционных карт!")
        return

    grouped = {}
    for card in cards:
        rarity = card[1]
        if rarity not in grouped:
            grouped[rarity] = []
        grouped[rarity].append(card)

    text = "🎴 МОИ КОЛЛЕКЦИОННЫЕ КАРТЫ\n━━━━━━━━━━━━━━━━━━\n"
    rarity_order = ["Мифическая", "Легендарная", "Эпическая"]

    for rarity in rarity_order:
        if rarity in grouped:
            text += f"\n⭐ {rarity}:\n"
            for card in grouped[rarity]:
                name, r, price, emoji, quantity = card
                price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
                text += f"  {emoji} {name} — {price_str} ПТ (x{quantity})\n"

    await message.answer(text)


# ==================== ОСТАЛЬНЫЕ КОМАНДЫ ====================

@dp.message(Command("выдать"))
async def give_prize_manual_cmd(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAME:
        return

    if " | " not in message.text:
        await message.answer(
            "⚠️ Неверный формат!\nИспользуйте: /выдать @username Название приза | @контакт"
        )
        return

    command_part, content_part = message.text.split(maxsplit=1)

    try:
        target_identifier, prize_and_contact = content_part.split(maxsplit=1)
    except ValueError:
        await message.answer("⚠️ Ошибка синтаксиса. Пример: /выдать @username Карточка | @контакт")
        return

    if not target_identifier.startswith("@"):
        await message.answer("❌ Первый аргумент должен быть юзернеймом через @!")
        return

    prize_name, contact_info = prize_and_contact.split(" | ", 1)
    prize_name = prize_name.strip()
    contact_info = contact_info.strip()
    display_name = target_identifier.replace("@", "")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM user_profiles WHERE username = ? LIMIT 1", (target_identifier,))
    user_row = cursor.fetchone()

    if not user_row:
        cursor.execute("SELECT user_id, first_name FROM user_profiles WHERE first_name LIKE ? LIMIT 1",
                       (f"%{display_name}%",))
        user_row = cursor.fetchone()

        if user_row:
            await message.answer(
                f"⚠️ Найден пользователь по имени: {user_row[1]}\n"
                f"Используйте его ID или попросите написать что-нибудь в чат."
            )
            conn.close()
            return

    if user_row:
        target_user_id = user_row[0]
        cursor.execute("INSERT INTO user_prizes (user_id, prize_text) VALUES (?, ?)", (target_user_id, prize_name))
        conn.commit()

        try:
            private_text = f"🎁 Поздравляем!\nВы выиграли {prize_name}, чтобы забрать приз обратитесь к {contact_info}"
            await bot.send_message(chat_id=target_user_id, text=private_text)
            await message.answer(f"✅ Приз успешно выдан игроку {display_name}!")
        except Exception:
            await message.answer(
                f"✅ Приз добавлен в /мои_карты для {display_name}.\n"
                f"⚠️ Бот не смог написать ему в ЛС."
            )
    else:
        await message.answer(
            f"❌ Игрок {target_identifier} не найден в базе!\n\n"
            f"📌 Чтобы бот узнал его ID, человек должен написать хотя бы одно слово в чат.\n"
            f"📌 Или добавьте его вручную: /добавить {target_identifier}"
        )

    conn.close()


@dp.message(Command("добавить"))
async def add_user_manual(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAME:
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].startswith("@"):
        await message.answer("⚠️ Использование: /добавить @username")
        return
    target_username = args[1]
    display_name = target_username.replace("@", "")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user_profiles WHERE username = ? LIMIT 1", (target_username,))
    if cursor.fetchone():
        await message.answer(f"⚠️ Человек {display_name} уже добавлен ранее!")
        conn.close()
        return
    temp_id = random.randint(10000000, 99999999)
    cursor.execute(
        "INSERT INTO user_profiles (user_id, username, first_name, message_count, rank) VALUES (?, ?, ?, 0, 0)",
        (temp_id, target_username, display_name))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Человек {display_name} добавлен!")


@dp.message(Command("up"))
async def upgrade_user_short_cmd(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAME:
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].startswith("@"):
        await message.answer("⚠️ Использование: /up @username")
        return

    target_username = args[1]
    display_name = target_username.replace("@", "")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, rank FROM user_profiles WHERE username = ? LIMIT 1", (target_username,))
    row = cursor.fetchone()

    if row:
        u_id, current_rank = row
        if current_rank >= 10:
            await message.answer(f"⚠️ У игрока {display_name} уже максимальный 10 ранг!")
            conn.close()
            return
        new_rank = current_rank + 1
        cursor.execute("UPDATE user_profiles SET rank = ? WHERE user_id = ?", (new_rank, u_id))
        conn.commit()
        await message.answer(f"⭐ Ранг игрока {display_name} повышен до {new_rank}!")
    else:
        await message.answer(f"❌ Игрок {target_username} не найден в базе активности чата!\n"
                             f"Ему нужно написать хотя бы 1 слово в группу.")
    conn.close()


@dp.message(Command("down"))
async def downgrade_user_short_cmd(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAME:
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].startswith("@"):
        await message.answer("⚠️ Использование: /down @username")
        return

    target_username = args[1]
    display_name = target_username.replace("@", "")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, rank FROM user_profiles WHERE username = ? LIMIT 1", (target_username,))
    row = cursor.fetchone()

    if row:
        u_id, current_rank = row
        if current_rank <= 0:
            await message.answer(f"⚠️ У игрока {display_name} уже минимальный 0 ранг!")
            conn.close()
            return
        new_rank = current_rank - 1
        cursor.execute("UPDATE user_profiles SET rank = ? WHERE user_id = ?", (new_rank, u_id))
        conn.commit()
        await message.answer(f"📉 Ранг игрока {display_name} понижен до {new_rank}!")
    else:
        await message.answer(f"❌ Игрок {target_username} не найден в базе активности чата!\n"
                             f"Ему нужно написать хотя бы 1 слово в группу.")
    conn.close()


@dp.message(Command("add_prize"))
async def add_prize_cmd(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAME:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Использование: /add_prize Название карты")
        return
    prize_text = args[1]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO prizes_pool (prize_text) VALUES (?)", (prize_text,))
    conn.commit()
    conn.close()
    await message.answer(f"📦 Карта добавлена в пул: {prize_text}")


@dp.message(Command("remove_prize"))
async def remove_prize_cmd(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("⛔ Эта команда доступна только администраторам!")
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer(
            "⚠️ Неверный формат!\n"
            "Используйте: /remove_prize ID\n"
            "ID можно узнать командой /пул"
        )
        return

    prize_id = int(args[1])

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT prize_text FROM prizes_pool WHERE id = ?", (prize_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        await message.answer(
            f"❌ Карта с ID {prize_id} не найдена в пуле!\n"
            f"Используйте /пул чтобы увидеть все ID."
        )
        return

    prize_name = row[0]
    cursor.execute("DELETE FROM prizes_pool WHERE id = ?", (prize_id,))
    conn.commit()
    conn.close()

    await message.answer(
        f"🗑️ Карта «{prize_name}» (ID: {prize_id}) успешно удалена из пула!"
    )


@dp.message(Command("пул"))
async def show_prize_pool(message: types.Message):
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("⛔ Эта команда доступна только администраторам!")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, prize_text FROM prizes_pool ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "📦 ПУЛ НАГРАД ПУСТ!\n\n"
            "Администратор может добавить карты командой:\n"
            "/add_prize Название карты"
        )
        return

    total_cards = len(rows)

    text = f"📦 ПУЛ НАГРАД 📦\n"
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Всего карт в пуле: {total_cards}\n"
    text += f"━━━━━━━━━━━━━━━━━━\n\n"

    for index, row in enumerate(rows, start=1):
        card_id, card_name = row
        text += f"{index}. 🃏 {card_name} (ID: {card_id})\n"

    text += f"\n━━━━━━━━━━━━━━━━━━\n"
    text += f"ℹ️ Управление пулом (для админа):\n"
    text += f"• Добавить: /add_prize Название\n"
    text += f"• Удалить: /remove_prize ID"

    await message.answer(text)


@dp.message(Command("start_event"))
async def start_event_cmd(message: types.Message):
    global event_active, boss_name, boss_hp, boss_max_hp, last_speakers
    if message.from_user.username not in ADMIN_USERNAME:
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3 or not args[2].isdigit():
        await message.answer("⚠️ Использование: /start_event Сукуна 2000")
        return
    if event_active:
        await message.answer("⚠️ Событие уже идет! Сначала одолейте текущего босса.")
        return
    boss_name = args[1]
    boss_max_hp = int(args[2])
    boss_hp = boss_max_hp
    event_active = True
    last_speakers.clear()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM match_damage")
    conn.commit()
    conn.close()
    await message.answer(
        f"⚔️ ОБЪЯВЛЕНО ПОЛНОМАСШТАБНОЕ СОБЫТИЕ! ⚔️\n\n🔴 Появился Мировой Босс: {boss_name}\n❤️ Здоровье Босса: {boss_hp} HP\n\n📝 Правила: Общайтесь фразами от 4 символов. Не более 3 сообщений подряд от одного человека!"
    )


# ==================== ИНФОРМАЦИОННЫЕ КОМАНДЫ ====================

@dp.message(Command("чат"))
async def show_chat_rules(message: types.Message):
    args = message.text.split()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM user_profiles")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(message_count) FROM user_profiles")
    total_messages_row = cursor.fetchone()[0]
    total_messages = total_messages_row if total_messages_row else 0

    rules_text = (
        "📊 ПАНЕЛЬ АКТИВНОСТИ ФАН-ЧАТА 📊\n━━━━━━━━━━━━━━━━━━\n"
        f"👥 Зарегистрировано участников: {total_users}\n"
        f"💬 Всего сообщений в чате: {total_messages}\n━━━━━━━━━━━━━━━━━━\n"
        "📝 Действующие правила начисления баллов:\n• Сообщение должно быть длиннее 1 буквы!\n• Засчитывается не более 3 сообщений подряд от одного человека!\n━━━━━━━━━━━━━━━━━━\n"
    )

    if len(args) > 1 and args[1].isdigit():
        days_num = int(args[1])
        rules_text += f"⏳ Показ активности за последние {days_num} дней (включая сегодня):\n━━━━━━━━━━━━━━━━━━\n"

        today = datetime.now()
        date_list = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_num)]
        placeholders = ",".join(["?"] * len(date_list))

        cursor.execute(f"""
            SELECT p.username, p.first_name, SUM(d.message_count) as total_days_msg
            FROM daily_stats d
            JOIN user_profiles p ON d.user_id = p.user_id
            WHERE d.msg_date IN ({placeholders})
            GROUP BY d.user_id
            HAVING total_days_msg > 0
            ORDER BY total_days_msg DESC
            LIMIT 20
        """, tuple(date_list))
    else:
        rules_text += "ℹ️ Показ активности за все время существования канала:\n━━━━━━━━━━━━━━━━━━\n"
        cursor.execute(
            "SELECT username, first_name, message_count FROM user_profiles WHERE message_count > 0 ORDER BY message_count DESC LIMIT 20")

    top_rows = cursor.fetchall()
    conn.close()

    rules_text += "🏆 ТОП-20 АКТИВИСТОВ КАНАЛА:\n"
    if not top_rows:
        rules_text += "В рейтинге пока пусто... Начните общаться!"
    else:
        for index, row in enumerate(top_rows, start=1):
            username, first_name, count = row
            display_name = username.replace("@", "") if username and username != "Нет юзернейма" else (
                    first_name or "Пользователь")
            rules_text += f"{index}. {display_name} — {count} собщ.\n"

    await message.answer(rules_text)


@dp.message(Command("status"))
async def show_my_status(message: types.Message):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Нет юзернейма"
    first_name = message.from_user.first_name or "Пользователь"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT message_count, rank FROM user_profiles WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("SELECT rank FROM user_profiles WHERE username = ?", (username,))
        exist_row = cursor.fetchone()
        if exist_row:
            cursor.execute("UPDATE user_profiles SET user_id = ?, first_name = ? WHERE username = ?",
                           (user_id, first_name, username))
            rank = exist_row[0] if exist_row[0] is not None else 0
            msg_count = 0
        else:
            cursor.execute(
                "INSERT INTO user_profiles (user_id, username, first_name, message_count, rank) VALUES (?, ?, ?, 0, 0)",
                (user_id, username, first_name))
            rank, msg_count = 0, 0
        conn.commit()
    else:
        msg_count, rank = row
        if rank is None: rank = 0

    cursor.execute("SELECT COUNT(*) FROM user_prizes WHERE user_id = ?", (user_id,))
    cards_count = cursor.fetchone()[0]
    conn.close()

    rank_display = f"{rank} (МАКС)" if rank >= 10 else str(rank)

    status_text = (f"👤 Профиль игрока: {first_name}\n"
                   f"━━━━━━━━━━━━━━━━━━\n"
                   f"📊 Написано сообщений: {msg_count}\n"
                   f"🎖 Ранг (Побед в рейдах): ⭐ Ранг {rank_display}\n"
                   f"🎒 Собрано карточек: {cards_count} шт.\n"
                   f"📜 Чтобы посмотреть свои карты, введите /мои_карты")
    await message.answer(status_text)


@dp.message(Command("мои_карты"))
async def show_my_cards(message: types.Message):
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT prize_text FROM user_prizes WHERE user_id = ? ORDER BY id ASC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        await message.answer("🎒 У вас пока нет выигранных карт!")
        return
    text = f"🎒 Ваша коллекция карт:\n━━━━━━━━━━━━━━━━━━\n"
    for row in rows:
        text += f"• {row[0]}\n"
    await message.answer(text)


@dp.message(Command("event_top"))
async def show_event_top(message: types.Message):
    global event_active, boss_name, boss_hp, boss_max_hp
    if not event_active:
        await message.answer("⚔️ Сейчас нет активного события! Ждите запуска рейда от админа.")
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_profiles.username, user_profiles.first_name, match_damage.damage_dealt 
        FROM match_damage 
        JOIN user_profiles ON match_damage.user_id = user_profiles.user_id
        WHERE match_damage.damage_dealt > 0 
        ORDER BY match_damage.damage_dealt DESC LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()

    text = f"📊 Рейтинг урона по Боссу {boss_name}:\n❤️ Осталось здоровья: {boss_hp}/{boss_max_hp} HP\n━━━━━━━━━━━━━━━━━━\n"
    if not rows:
        text += "Удары еще никто не нанес!"
    else:
        for index, row in enumerate(rows, start=1):
            username, first_name, dmg = row
            mention = username if username and username != "Нет юзернейма" else f"{first_name}"
            text += f"{index}. {mention} — нанес {dmg} урона ⚔️\n"
    await message.answer(text)


# ==================== СИСТЕМА ЛОТОВ ====================

async def remove_buttons_from_admins(lot_id):
    """Удаляет кнопки у всех админов после обработки лота"""
    if lot_id in admin_messages:
        for admin_id, message_id in admin_messages[lot_id].items():
            try:
                await bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=None
                )
                print(f"✅ Кнопки удалены у админа {admin_id} для лота #{lot_id}")
            except Exception as e:
                print(f"❌ Не удалось удалить кнопки у админа {admin_id}: {e}")
        del admin_messages[lot_id]


@dp.message(Command("лот"))
async def create_lot(message: types.Message):
    """Создает новый лот с фото и описанием"""
    try:
        if not message.reply_to_message:
            await message.answer(
                "❌ Ответьте (реплай) на сообщение с фотографией!\n\n"
                "📝 Как создать лот:\n"
                "1️⃣ Отправьте фото в чат\n"
                "2️⃣ Ответьте на это фото командой /лот\n"
                "3️⃣ В этом же сообщении напишите описание лота"
            )
            return

        if not message.reply_to_message.photo:
            await message.answer("❌ Вы должны ответить на ФОТОГРАФИЮ!")
            return

        description = message.text.replace("/лот", "").strip()
        if not description:
            await message.answer("❌ Напишите описание лота после команды /лот")
            return

        photo = message.reply_to_message.photo[-1]
        file_id = photo.file_id
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без username"
        first_name = message.from_user.first_name or "Пользователь"

        global lot_counter
        lot_id = lot_counter
        lot_counter += 1

        lot_data = {
            "id": lot_id,
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "description": description,
            "file_id": file_id,
            "status": "pending",
            "accepted_by": None,
            "published_by": None,
            "created_at": datetime.now().strftime("%d.%m.%Y %H:%M")
        }

        pending_lots[lot_id] = lot_data
        save_lot_to_db(lot_data)

        await message.answer(
            f"✅ Лот #{lot_id} отправлен на модерацию!\n"
            f"📝 Описание: {description}\n\n"
            f"⏳ Ожидайте решения администратора."
        )

        await notify_admins(lot_id, lot_data)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        print(f"Ошибка в create_lot: {e}")


async def notify_admins(lot_id, lot_data):
    """Отправляет лот на проверку админам и сохраняет message_id"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Лот принят", callback_data=f"accept_lot_{lot_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_lot_{lot_id}")
        ]
    ])

    admin_text = (
        f"📦 НОВЫЙ ЛОТ #{lot_id}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 Продавец: {lot_data['username']}\n"
        f"📛 Имя: {lot_data['first_name']}\n"
        f"🆔 ID: {lot_data['user_id']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 Описание:\n{lot_data['description']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏳ Ожидает модерации..."
    )

    sent_count = 0
    for admin_id in LOT_ADMINS:
        try:
            msg = await bot.send_photo(
                chat_id=admin_id,
                photo=lot_data['file_id'],
                caption=admin_text,
                reply_markup=keyboard
            )
            if lot_id not in admin_messages:
                admin_messages[lot_id] = {}
            admin_messages[lot_id][admin_id] = msg.message_id
            sent_count += 1
            print(f"✅ Лот #{lot_id} отправлен админу {admin_id}")
        except Exception as e:
            print(f"❌ Не удалось отправить админу {admin_id}: {e}")

    if sent_count == 0:
        await bot.send_message(
            chat_id=lot_data['user_id'],
            text="⚠️ Нет доступных администраторов для модерации лота."
        )


@dp.callback_query()
async def handle_all_callbacks(callback: types.CallbackQuery):
    try:
        print(f"🔔 Получен callback: {callback.data} от {callback.from_user.id}")

        if not callback.data.startswith(('accept_lot_', 'reject_lot_', 'publish_lot_')):
            print(f"⚠️ Неизвестный callback: {callback.data}")
            await callback.answer("⚠️ Неизвестная команда", show_alert=True)
            return

        try:
            last_underscore = callback.data.rfind('_')
            action = callback.data[:last_underscore]
            lot_id_str = callback.data[last_underscore + 1:]
            lot_id = int(lot_id_str)
            print(f"📦 Действие: {action}, Лот: #{lot_id}")
        except Exception as e:
            print(f"❌ Ошибка парсинга callback: {e}")
            await callback.answer(f"❌ Ошибка парсинга: {e}", show_alert=True)
            return

        if callback.from_user.id not in LOT_ADMINS:
            print(f"⛔ Пользователь {callback.from_user.id} не админ!")
            await callback.answer("⛔ У вас нет прав!", show_alert=True)
            return

        if lot_id not in pending_lots:
            print(f"❌ Лот #{lot_id} не найден!")
            await callback.answer("❌ Лот уже обработан!", show_alert=True)
            await remove_buttons_from_admins(lot_id)
            try:
                await callback.message.delete()
            except:
                pass
            return

        lot_data = pending_lots[lot_id]
        print(f"📊 Статус лота: {lot_data['status']}")

        # ========== ПРИНЯТЬ ЛОТ ==========
        if action == "accept_lot":
            try:
                if lot_data["status"] != "pending":
                    await callback.answer("❌ Этот лот уже обработан!", show_alert=True)
                    await remove_buttons_from_admins(lot_id)
                    return

                print(f"✅ Админ {callback.from_user.first_name} принимает лот #{lot_id}")

                lot_data["status"] = "accepted"
                lot_data["accepted_by"] = callback.from_user.id
                save_lot_to_db(lot_data)

                await remove_buttons_from_admins(lot_id)

                publish_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📢 Лот опубликован", callback_data=f"publish_lot_{lot_id}")]
                ])

                await callback.message.edit_caption(
                    caption=(
                        f"📦 ЛОТ #{lot_id} ПРИНЯТ\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"👤 Продавец: {lot_data['username']}\n"
                        f"📝 Описание: {lot_data['description']}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"✅ Принял: {callback.from_user.first_name}\n"
                        f"⏳ Нажмите «Лот опубликован» после публикации"
                    ),
                    reply_markup=publish_keyboard
                )

                try:
                    await bot.send_message(
                        chat_id=lot_data['user_id'],
                        text=(
                            f"✅ ЛОТ #{lot_id} ПРИНЯТ!\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"📝 {lot_data['description']}\n\n"
                            f"👤 Администратор {callback.from_user.first_name} принял ваш лот.\n"
                            f"⏳ Ожидайте публикации."
                        )
                    )
                    print(f"✅ Уведомление отправлено продавцу {lot_data['user_id']}")
                except Exception as e:
                    print(f"❌ Не удалось уведомить продавца: {e}")

                await callback.answer("✅ Лот принят!", show_alert=True)

            except Exception as e:
                error_text = f"Ошибка при принятии лота: {e}"
                print(f"❌ {error_text}")
                await callback.answer(f"❌ {error_text[:100]}", show_alert=True)

        # ========== ОТКЛОНИТЬ ЛОТ ==========
        elif action == "reject_lot":
            try:
                if lot_data["status"] != "pending":
                    await callback.answer("❌ Этот лот уже обработан!", show_alert=True)
                    await remove_buttons_from_admins(lot_id)
                    return

                print(f"❌ Админ {callback.from_user.first_name} отклоняет лот #{lot_id}")

                lot_data["status"] = "rejected"
                save_lot_to_db(lot_data)

                await remove_buttons_from_admins(lot_id)

                await callback.message.edit_caption(
                    caption=(
                        f"📦 ЛОТ #{lot_id} ОТКЛОНЕН\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"👤 Продавец: {lot_data['username']}\n"
                        f"📝 Описание: {lot_data['description']}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"❌ Отклонил: {callback.from_user.first_name}"
                    ),
                    reply_markup=None
                )

                try:
                    await bot.send_message(
                        chat_id=lot_data['user_id'],
                        text=(
                            f"❌ ЛОТ #{lot_id} ОТКЛОНЕН!\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"📝 {lot_data['description']}\n\n"
                            f"Администратор {callback.from_user.first_name} отклонил ваш лот."
                        )
                    )
                    print(f"✅ Уведомление отправлено продавцу {lot_data['user_id']}")
                except Exception as e:
                    print(f"❌ Не удалось уведомить продавца: {e}")

                del pending_lots[lot_id]
                delete_lot_from_db(lot_id)
                print(f"🗑️ Лот #{lot_id} удален из очереди")

                await callback.answer("❌ Лот отклонен!", show_alert=True)

            except Exception as e:
                error_text = f"Ошибка при отклонении лота: {e}"
                print(f"❌ {error_text}")
                await callback.answer(f"❌ {error_text[:100]}", show_alert=True)

        # ========== ОПУБЛИКОВАТЬ ЛОТ ==========
        elif action == "publish_lot":
            try:
                if lot_data["status"] != "accepted":
                    await callback.answer("❌ Этот лот не принят!", show_alert=True)
                    return

                print(f"📢 Админ {callback.from_user.first_name} публикует лот #{lot_id}")

                lot_data["status"] = "published"
                lot_data["published_by"] = callback.from_user.id
                save_lot_to_db(lot_data)

                await callback.message.edit_caption(
                    caption=(
                        f"📦 ЛОТ #{lot_id} ОПУБЛИКОВАН\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"👤 Продавец: {lot_data['username']}\n"
                        f"📝 Описание: {lot_data['description']}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"✅ Опубликовал: {callback.from_user.first_name}\n"
                        f"📢 Лот успешно опубликован!"
                    ),
                    reply_markup=None
                )

                try:
                    await bot.send_message(
                        chat_id=lot_data['user_id'],
                        text=(
                            f"📢 ЛОТ #{lot_id} ОПУБЛИКОВАН!\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"📝 {lot_data['description']}\n\n"
                            f"✅ Ваш лот опубликован администратором {callback.from_user.first_name}!"
                        )
                    )
                    print(f"✅ Уведомление отправлено продавцу {lot_data['user_id']}")
                except Exception as e:
                    print(f"❌ Не удалось уведомить продавца: {e}")

                del pending_lots[lot_id]
                print(f"📢 Лот #{lot_id} опубликован и удален из очереди")

                await callback.answer("📢 Лот опубликован!", show_alert=True)

            except Exception as e:
                error_text = f"Ошибка при публикации лота: {e}"
                print(f"❌ {error_text}")
                await callback.answer(f"❌ {error_text[:100]}", show_alert=True)

    except Exception as e:
        error_text = f"Общая ошибка: {e}"
        print(f"❌ {error_text}")
        try:
            await callback.answer(f"❌ {error_text[:100]}", show_alert=True)
        except:
            pass


@dp.message(Command("лоты"))
async def show_pending_lots(message: types.Message):
    if message.from_user.id not in LOT_ADMINS:
        await message.answer("⛔ Только для админов лотов!")
        return

    if not pending_lots:
        await message.answer("📭 Нет лотов на модерации!")
        return

    text = "📦 ВСЕ ЛОТЫ\n━━━━━━━━━━━━━━━━━━\n"

    pending = []
    accepted = []
    published = []

    for lot_id, lot in pending_lots.items():
        if lot['status'] == 'pending':
            pending.append((lot_id, lot))
        elif lot['status'] == 'accepted':
            accepted.append((lot_id, lot))
        elif lot['status'] == 'published':
            published.append((lot_id, lot))

    if pending:
        text += "⏳ ОЖИДАЮТ МОДЕРАЦИИ:\n"
        for lot_id, lot in pending:
            text += f"  #{lot_id} — {lot['username']}\n"
            text += f"  📝 {lot['description'][:50]}...\n\n"

    if accepted:
        text += "✅ ПРИНЯТЫ (ОЖИДАЮТ ПУБЛИКАЦИИ):\n"
        for lot_id, lot in accepted:
            text += f"  #{lot_id} — {lot['username']}\n"
            text += f"  📝 {lot['description'][:50]}...\n\n"

    if published:
        text += "📢 ОПУБЛИКОВАНЫ:\n"
        for lot_id, lot in published:
            text += f"  #{lot_id} — {lot['username']}\n"
            text += f"  📝 {lot['description'][:50]}...\n\n"

    await message.answer(text)


@dp.message(Command("мои_лоты"))
async def show_my_lots(message: types.Message):
    user_id = message.from_user.id

    my_lots = []
    for lot_id, lot in pending_lots.items():
        if lot['user_id'] == user_id:
            my_lots.append((lot_id, lot))

    if not my_lots:
        await message.answer("📭 У вас нет активных лотов!")
        return

    text = "📦 МОИ ЛОТЫ\n━━━━━━━━━━━━━━━━━━\n"
    for lot_id, lot in my_lots:
        status_text = {
            'pending': '⏳ На модерации',
            'accepted': '✅ Принят (ждет публикации)',
            'published': '📢 Опубликован',
            'rejected': '❌ Отклонен'
        }.get(lot['status'], lot['status'])

        text += f"🔹 #{lot_id} — {status_text}\n"
        text += f"   📝 {lot['description'][:50]}...\n"
        text += f"   🕐 {lot['created_at']}\n\n"

    await message.answer(text)


@dp.message(Command("myid"))
async def get_my_id(message: types.Message):
    await message.answer(
        f"🆔 Ваш ID: {message.from_user.id}\n"
        f"👤 Username: @{message.from_user.username}\n"
        f"📛 Имя: {message.from_user.first_name}"
    )


# ==================== ОБРАБОТКА СТАВОК ====================

@dp.message()
async def process_bets(message: types.Message):
    if not message.text:
        return

    text = message.text.strip()

    if not text.lower().startswith(("ст", "ставка")):
        return

    lines = text.split('\n')

    if len(lines) < 2:
        await message.reply("❌ Напишите карты после 'Ставка'")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    total = 0.0
    result_parts = []
    has_missing = False

    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if not parts:
            continue

        # Проверяем, начинается ли строка с "Кол." или "Кол"
        is_collection = False
        card_name = ""
        rating = None

        # Проверяем первый элемент
        if parts[0] in ["Кол.", "Кол"]:
            is_collection = True
            # Название карты - все остальные части
            card_name = " ".join(parts[1:])
        else:
            # Обычная карта или обложка
            # Ищем рейтинг (последнее число)
            rating = None
            name_parts = []
            for i, part in enumerate(parts):
                if part.isdigit():
                    rating = int(part)
                else:
                    name_parts.append(part)
            card_name = " ".join(name_parts)

        if not card_name:
            result_parts.append(f"❌ Не указано название!")
            continue

        price = None
        found = False

        # ===== ПОИСК КОЛЛЕКЦИОННОЙ КАРТЫ =====
        if is_collection:
            cursor.execute(
                "SELECT name, rarity, price, emoji FROM collection_cards WHERE name = ?",
                (card_name,)
            )
            row = cursor.fetchone()
            if row:
                found = True
                name, rarity, price, emoji = row
                price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
                result_parts.append(f"✅ {emoji} {name} ({rarity}) → {price_str} ПТ")
            else:
                result_parts.append(f"❌ Коллекционная карта «{card_name}» не найдена!")
                has_missing = True

        # ===== ПОИСК ОБЛОЖКИ =====
        elif parts[0] == "Обл":
            if rating is None:
                result_parts.append(f"❌ {card_name} — не указан рейтинг")
                continue

            cursor.execute(
                "SELECT name, rating, price, emoji FROM covers WHERE name = ? AND rating = ?",
                (card_name, rating)
            )
            row = cursor.fetchone()
            if row:
                found = True
                name, r, price, emoji = row
                price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
                result_parts.append(f"✅ {emoji} {name} (Обложка) ⭐{rating} → {price_str} ПТ")
            else:
                result_parts.append(f"❌ Обложка «{card_name} ⭐{rating}» не найдена!")
                has_missing = True

        # ===== ПОИСК ОБЫЧНОЙ КАРТЫ =====
        else:
            if rating is None:
                # Проверяем, может это коллекционная карта без "Кол."?
                cursor.execute(
                    "SELECT name, rarity, price, emoji FROM collection_cards WHERE name = ?",
                    (card_name,)
                )
                row = cursor.fetchone()
                if row:
                    found = True
                    name, rarity, price, emoji = row
                    price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
                    result_parts.append(f"✅ {emoji} {name} ({rarity}) → {price_str} ПТ")
                else:
                    result_parts.append(f"❌ {card_name} — не указан рейтинг")
                continue

            cursor.execute(
                "SELECT name, rating, price FROM game_cards WHERE name = ? AND rating = ?",
                (card_name, rating)
            )
            row = cursor.fetchone()
            if row:
                found = True
                name, r, price = row
                price_str = f"{price:.1f}" if price % 1 != 0 else str(int(price))
                result_parts.append(f"✅ 🃏 {name} ⭐{rating} → {price_str} ПТ")
            else:
                result_parts.append(f"❌ Карта «{card_name} ⭐{rating}» не найдена!")
                has_missing = True

        if found and price is not None:
            total += price

    conn.close()

    if not result_parts:
        await message.reply("❌ Не найдено ни одной карты!")
        return

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

    total_str = f"{total:.1f}" if total % 1 != 0 else str(int(total))

    result = f"📊 ИТОГ СТАВКИ\n"
    result += f"👤 {username}\n"
    result += "━━━━━━━━━━━━━━━━━━\n"
    result += "\n".join(result_parts)
    result += "\n━━━━━━━━━━━━━━━━━━\n"
    result += f"💰 Общая сумма: {total_str} ПТ"

    if has_missing:
        result += "\n\n⚠️ Некоторые позиции не найдены!"

    await message.reply(result)

# ==================== ОБРАБОТЧИК РЕЙДА ====================

@dp.message()
async def process_event_chat(message: types.Message):
    global event_active, boss_name, boss_hp, last_speakers

    if not message.text:
        return

    if message.text.startswith("/") or message.from_user.is_bot or message.left_chat_member or message.new_chat_members:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Нет юзернейма"
    first_name = message.from_user.first_name or "Охотник"
    current_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO user_profiles (user_id, username, first_name, message_count, rank) 
        VALUES (?, ?, ?, 1, 0)
        ON CONFLICT(user_id) DO UPDATE SET message_count = message_count + 1, username = excluded.username, first_name = excluded.first_name
    """, (user_id, username, first_name))

    cursor.execute("""
        INSERT INTO daily_stats (user_id, msg_date, message_count) 
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, msg_date) DO UPDATE SET message_count = message_count + 1
    """, (user_id, current_date))
    conn.commit()

    if not event_active:
        conn.close()
        return

    if not message.text or len(message.text.strip()) < 4:
        conn.close()
        return

    if chat_id not in last_speakers:
        last_speakers[chat_id] = {"user_id": user_id, "count": 1}
    else:
        current_speaker = last_speakers[chat_id]
        if current_speaker["user_id"] == user_id:
            current_speaker["count"] += 1
            if current_speaker["count"] > 3:
                conn.close()
                return
        else:
            last_speakers[chat_id] = {"user_id": user_id, "count": 1}

    damage = random.randint(15, 35)
    boss_hp -= damage

    cursor.execute("""
        INSERT INTO match_damage (user_id, damage_dealt) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET damage_dealt = damage_dealt + excluded.damage_dealt
    """, (user_id, damage))
    conn.commit()

    if boss_hp <= 0:
        event_active = False
        await message.answer(f"💥 Босс {boss_name} повержен! 💥\nБот совершает решающий удар кубиков...")
        dice_msg = await message.answer_dice(emoji="🎲")
        await asyncio.sleep(3.5)

        if dice_msg.dice.value in (2, 3, 4, 5, 6):
            cursor.execute("SELECT user_id FROM match_damage ORDER BY damage_dealt DESC LIMIT 1")
            winner_row = cursor.fetchone()
            if winner_row:
                w_id = winner_row[0]
                cursor.execute("SELECT username, first_name, rank FROM user_profiles WHERE user_id = ?", (w_id,))
                w_username, w_first_name, current_rank = cursor.fetchone()
                w_mention = w_username if w_username and w_username != "Нет юзернейма" else w_first_name

                if current_rank < 10:
                    new_rank = current_rank + 1
                    cursor.execute("UPDATE user_profiles SET rank = ? WHERE user_id = ?", (new_rank, w_id))
                else:
                    new_rank = current_rank

                cursor.execute("SELECT id, prize_text FROM prizes_pool ORDER BY RANDOM() LIMIT 1")
                prize_row = cursor.fetchone()
                if prize_row:
                    prize_id, card_name = prize_row
                    cursor.execute("DELETE FROM prizes_pool WHERE id = ?", (prize_id,))
                    cursor.execute("INSERT INTO user_prizes (user_id, prize_text) VALUES (?, ?)", (w_id, card_name))
                    conn.commit()
                    await message.answer(
                        f"🎉 РЕЙД ЗАВЕРШЕН ПОБЕДОЙ! 🏆\n\n🥇 Лучший охотник: {w_mention}\n⭐ Его ранг повышен до: {new_rank}\n🎁 Награда: карта {card_name} добавлена в /мои_карты!"
                    )
                else:
                    conn.commit()
                    await message.answer(
                        f"🎉 РЕЙД ЗАВЕРШЕН ПОБЕДОЙ! 🏆\n\n🥇 Лучший охотник: {w_mention} (Ранг повышен до {new_rank}).\n⚠️ Карты в пуле админа кончились!"
                    )
        else:
            await message.answer(f"❌ КРИТИЧЕСКАЯ НЕУДАЧА! Босс {boss_name} сбежал!")

    conn.commit()
    conn.close()


# ==================== ЗАПУСК ====================

async def main():
    init_event_db()
    migrate_db()
    load_lots_from_db()
    print("Рейд-бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
