import os
import asyncpg
from cryptography.fernet import Fernet

pool: asyncpg.Pool | None = None
fernet = Fernet(os.environ["ENCRYPTION_KEY"].encode())


def encrypt_card(card_number: str) -> str:
    return fernet.encrypt(card_number.encode()).decode()


def decrypt_card(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()


async def init_db():
    global pool
    pool = await asyncpg.create_pool(
        os.environ["DATABASE_URL"], min_size=1, max_size=5,
        statement_cache_size=0
    )
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            unique_id VARCHAR(16) UNIQUE NOT NULL
        )
    """)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id SERIAL PRIMARY KEY,
            org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
            fio TEXT NOT NULL
        )
    """)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id SERIAL PRIMARY KEY,
            participant_id INTEGER REFERENCES participants(id) ON DELETE CASCADE,
            card_number TEXT NOT NULL
        )
    """)
    # Eski VARCHAR(16) ni TEXT ga o'zgartirish
    await pool.execute("""
        ALTER TABLE cards ALTER COLUMN card_number TYPE TEXT
    """)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            telegram_id BIGINT PRIMARY KEY,
            org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
            full_name TEXT,
            username TEXT
        )
    """)
    # Eski jadvalga yangi ustunlar qo'shish
    await pool.execute("""
        ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS full_name TEXT
    """)
    await pool.execute("""
        ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS username TEXT
    """)
    # Eski shifrlanmagan kartalarni shifrlash (bir martalik migratsiya)
    rows = await pool.fetch("SELECT id, card_number FROM cards")
    for row in rows:
        try:
            decrypt_card(row["card_number"])
        except Exception:
            # Shifrlanmagan — shifrlash kerak
            encrypted = encrypt_card(row["card_number"])
            await pool.execute(
                "UPDATE cards SET card_number = $1 WHERE id = $2",
                encrypted, row["id"]
            )


async def close_db():
    global pool
    if pool:
        await pool.close()


# --- Organizations ---

async def create_org(name: str, unique_id: str) -> int:
    return await pool.fetchval(
        "INSERT INTO organizations (name, unique_id) VALUES ($1, $2) RETURNING id",
        name, unique_id
    )


async def get_all_orgs():
    return await pool.fetch("SELECT * FROM organizations ORDER BY id")


async def get_org(org_id: int):
    return await pool.fetchrow("SELECT * FROM organizations WHERE id = $1", org_id)


async def get_org_by_unique_id(unique_id: str):
    return await pool.fetchrow("SELECT * FROM organizations WHERE unique_id = $1", unique_id)


async def rename_org(org_id: int, new_name: str):
    await pool.execute("UPDATE organizations SET name = $1 WHERE id = $2", new_name, org_id)


async def delete_org(org_id: int):
    await pool.execute("DELETE FROM organizations WHERE id = $1", org_id)


# --- Participants ---

async def create_participant(org_id: int, fio: str) -> int:
    return await pool.fetchval(
        "INSERT INTO participants (org_id, fio) VALUES ($1, $2) RETURNING id",
        org_id, fio
    )


async def get_participants(org_id: int):
    return await pool.fetch(
        "SELECT * FROM participants WHERE org_id = $1 ORDER BY id", org_id
    )


async def get_all_participants():
    return await pool.fetch(
        "SELECT p.*, o.name AS org_name FROM participants p "
        "JOIN organizations o ON o.id = p.org_id ORDER BY p.id"
    )


async def get_participant(participant_id: int):
    return await pool.fetchrow("SELECT * FROM participants WHERE id = $1", participant_id)


async def rename_participant(participant_id: int, new_fio: str):
    await pool.execute(
        "UPDATE participants SET fio = $1 WHERE id = $2", new_fio, participant_id
    )


async def delete_participant(participant_id: int):
    await pool.execute("DELETE FROM participants WHERE id = $1", participant_id)


# --- Cards ---

async def add_card(participant_id: int, card_number: str) -> int:
    encrypted = encrypt_card(card_number)
    return await pool.fetchval(
        "INSERT INTO cards (participant_id, card_number) VALUES ($1, $2) RETURNING id",
        participant_id, encrypted
    )


async def get_cards(participant_id: int):
    rows = await pool.fetch(
        "SELECT * FROM cards WHERE participant_id = $1 ORDER BY id", participant_id
    )
    result = []
    for row in rows:
        row = dict(row)
        try:
            row["card_number"] = decrypt_card(row["card_number"])
        except Exception:
            pass  # Eski shifrlanmagan kartalar uchun
        result.append(row)
    return result


async def delete_card(card_id: int):
    await pool.execute("DELETE FROM cards WHERE id = $1", card_id)


# --- User Sessions ---

async def set_user_session(telegram_id: int, org_id: int, full_name: str = None, username: str = None):
    await pool.execute(
        """INSERT INTO user_sessions (telegram_id, org_id, full_name, username)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (telegram_id) DO UPDATE
           SET org_id = $2, full_name = $3, username = $4""",
        telegram_id, org_id, full_name, username
    )


async def get_user_session(telegram_id: int):
    return await pool.fetchrow(
        "SELECT * FROM user_sessions WHERE telegram_id = $1", telegram_id
    )


async def get_org_users(org_id: int):
    return await pool.fetch(
        "SELECT * FROM user_sessions WHERE org_id = $1 ORDER BY telegram_id", org_id
    )


async def delete_user_session(telegram_id: int):
    await pool.execute("DELETE FROM user_sessions WHERE telegram_id = $1", telegram_id)
