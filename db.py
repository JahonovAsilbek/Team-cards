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

    # Bloklangan userlar
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS blocked_users (
            telegram_id BIGINT PRIMARY KEY,
            blocked_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Tashkilotlar (owner_id bilan)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            unique_id VARCHAR(16) UNIQUE NOT NULL,
            owner_id BIGINT NOT NULL
        )
    """)
    # Migratsiya: owner_id ustuni qo'shish (eski jadval uchun)
    await pool.execute("""
        ALTER TABLE organizations ADD COLUMN IF NOT EXISTS owner_id BIGINT
    """)

    # Ishtirokchilar
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id SERIAL PRIMARY KEY,
            org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
            fio TEXT NOT NULL
        )
    """)

    # Kartalar
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id SERIAL PRIMARY KEY,
            participant_id INTEGER REFERENCES participants(id) ON DELETE CASCADE,
            card_number TEXT NOT NULL
        )
    """)
    await pool.execute("""
        ALTER TABLE cards ALTER COLUMN card_number TYPE TEXT
    """)

    # Ko'p-ga-ko'p: user <-> tashkilot
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS user_orgs (
            telegram_id BIGINT NOT NULL,
            org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
            full_name TEXT,
            username TEXT,
            PRIMARY KEY (telegram_id, org_id)
        )
    """)

    # Eski user_sessions dan user_orgs ga migratsiya
    exists = await pool.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'user_sessions'
        )
    """)
    if exists:
        await pool.execute("""
            INSERT INTO user_orgs (telegram_id, org_id, full_name, username)
            SELECT telegram_id, org_id, full_name, username FROM user_sessions
            ON CONFLICT DO NOTHING
        """)
        await pool.execute("DROP TABLE IF EXISTS user_sessions")

    # Eski shifrlanmagan kartalarni shifrlash
    rows = await pool.fetch("SELECT id, card_number FROM cards")
    for row in rows:
        try:
            decrypt_card(row["card_number"])
        except Exception:
            encrypted = encrypt_card(row["card_number"])
            await pool.execute(
                "UPDATE cards SET card_number = $1 WHERE id = $2",
                encrypted, row["id"]
            )


async def close_db():
    global pool
    if pool:
        await pool.close()


# --- Blocked Users ---

async def is_blocked(telegram_id: int) -> bool:
    row = await pool.fetchval(
        "SELECT 1 FROM blocked_users WHERE telegram_id = $1", telegram_id
    )
    return row is not None


async def block_user(telegram_id: int):
    await pool.execute(
        "INSERT INTO blocked_users (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING",
        telegram_id
    )


async def unblock_user(telegram_id: int):
    await pool.execute(
        "DELETE FROM blocked_users WHERE telegram_id = $1", telegram_id
    )


async def get_blocked_users():
    return await pool.fetch(
        "SELECT * FROM blocked_users ORDER BY blocked_at DESC"
    )


# --- Organizations ---

async def create_org(name: str, unique_id: str, owner_id: int) -> int:
    return await pool.fetchval(
        "INSERT INTO organizations (name, unique_id, owner_id) VALUES ($1, $2, $3) RETURNING id",
        name, unique_id, owner_id
    )


async def get_all_orgs():
    return await pool.fetch("SELECT * FROM organizations ORDER BY id")


async def get_org(org_id: int):
    return await pool.fetchrow("SELECT * FROM organizations WHERE id = $1", org_id)


async def get_org_by_unique_id(unique_id: str):
    return await pool.fetchrow("SELECT * FROM organizations WHERE unique_id = $1", unique_id)


async def get_user_owned_orgs(telegram_id: int):
    return await pool.fetch(
        "SELECT * FROM organizations WHERE owner_id = $1 ORDER BY id", telegram_id
    )


async def is_org_owner(telegram_id: int, org_id: int) -> bool:
    row = await pool.fetchval(
        "SELECT 1 FROM organizations WHERE id = $1 AND owner_id = $2",
        org_id, telegram_id
    )
    return row is not None


async def rename_org(org_id: int, new_name: str):
    await pool.execute("UPDATE organizations SET name = $1 WHERE id = $2", new_name, org_id)


async def delete_org(org_id: int):
    await pool.execute("DELETE FROM organizations WHERE id = $1", org_id)


# --- User Orgs (many-to-many) ---

async def add_user_to_org(telegram_id: int, org_id: int, full_name: str = None, username: str = None):
    await pool.execute(
        """INSERT INTO user_orgs (telegram_id, org_id, full_name, username)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (telegram_id, org_id) DO UPDATE
           SET full_name = $3, username = $4""",
        telegram_id, org_id, full_name, username
    )


async def remove_user_from_org(telegram_id: int, org_id: int):
    await pool.execute(
        "DELETE FROM user_orgs WHERE telegram_id = $1 AND org_id = $2",
        telegram_id, org_id
    )


async def get_user_orgs(telegram_id: int):
    return await pool.fetch(
        """SELECT o.* FROM organizations o
           JOIN user_orgs uo ON uo.org_id = o.id
           WHERE uo.telegram_id = $1 ORDER BY o.id""",
        telegram_id
    )


async def get_org_members(org_id: int):
    return await pool.fetch(
        "SELECT * FROM user_orgs WHERE org_id = $1 ORDER BY telegram_id", org_id
    )


async def is_org_member(telegram_id: int, org_id: int) -> bool:
    row = await pool.fetchval(
        "SELECT 1 FROM user_orgs WHERE telegram_id = $1 AND org_id = $2",
        telegram_id, org_id
    )
    return row is not None


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


async def get_participants_for_user(telegram_id: int):
    """User a'zo bo'lgan barcha tashkilotlardan ishtirokchilar"""
    return await pool.fetch(
        """SELECT p.*, o.name AS org_name FROM participants p
           JOIN organizations o ON o.id = p.org_id
           JOIN user_orgs uo ON uo.org_id = o.id
           WHERE uo.telegram_id = $1 ORDER BY p.id""",
        telegram_id
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

async def card_exists(participant_id: int, card_number: str) -> bool:
    """Ishtirokchida shu karta borligini tekshirish"""
    rows = await pool.fetch(
        "SELECT card_number FROM cards WHERE participant_id = $1", participant_id
    )
    for row in rows:
        try:
            decrypted = decrypt_card(row["card_number"])
        except Exception:
            decrypted = row["card_number"]
        if decrypted == card_number:
            return True
    return False


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
            pass
        result.append(row)
    return result


async def delete_card(card_id: int):
    await pool.execute("DELETE FROM cards WHERE id = $1", card_id)
