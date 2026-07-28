import os
import asyncio
import requests
import sqlite3
import asyncpg
from urllib.parse import urlparse
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    FloodWaitError,
)

# ⪼ استدعاء فارات التحكم من بيئة الاستضافة
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 

# === [ الفارات الجديدة المطلوبة من رايلوي ] ===
RAILWAY_PROJECT_ID = os.environ.get("RAILWAY_PROJECT_ID") 
RAILWAY_ENV_ID = os.environ.get("RAILWAY_ENV_ID") 
CENTRAL_DB_URL = os.environ.get("CENTRAL_DB_URL") 

API_ID = 7219208 
API_HASH = "64342b78a8d90e3f691d7a3a09112e7b" 

# ⪼ إعداد قاعدة البيانات المحلية للبوت
conn = sqlite3.connect('deployments.db', check_same_thread=False) 
cursor = conn.cursor() 
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, service_id TEXT)') 
cursor.execute('CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, is_full BOOLEAN DEFAULT 0)')
conn.commit() 

bot_config = {"is_active": True}
bot = TelegramClient('deployer_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN) 

def get_active_api_key():
    cursor.execute("SELECT key FROM api_keys WHERE is_full = 0 LIMIT 1")
    result = cursor.fetchone()
    return result[0] if result else None

def mark_key_as_full(api_key):
    cursor.execute("UPDATE api_keys SET is_full = 1 WHERE key = ?", (api_key,))
    conn.commit()

def railway_query(query, variables, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        res = requests.post("https://backboard.railway.app/graphql/v2", json={"query": query, "variables": variables}, headers=headers, timeout=30).json()
        if "errors" in res and res["errors"]:
            return None, res["errors"][0]["message"]
        return res.get("data"), None
    except Exception as e:
        return None, str(e)

async def create_user_logical_database(user_id):
    """ إنشاء قاعدة بيانات فرعية معزولة للمستخدم داخل القاعدة المركزية """
    db_name = f"tython_user_{user_id}"
    try:
        sys_conn = await asyncpg.connect(CENTRAL_DB_URL)
        await sys_conn.execute(f'CREATE DATABASE "{db_name}"')
        await sys_conn.close()
    except Exception as e:
        if "already exists" not in str(e).lower():
            return None, f"فشل إنشاء الداتا بيز المعزولة: {e}"
            
    parsed = urlparse(CENTRAL_DB_URL)
    new_url = parsed._replace(path=f"/{db_name}").geturl()
    return new_url, None

async def deploy_user_service(session_string, user_bot_token, user_id):
    api_key = get_active_api_key()
    if not api_key:
        return False, "⚠️ عذراً، لا يوجد مفتاح API نشط في البوت. يرجى إضافة مفتاح من لوحة التحكم."

    user_db_url, db_err = await create_user_logical_database(user_id)
    if db_err:
        return False, db_err

    q_service_create = """mutation serviceCreate($projectId: String!, $name: String!, $source: ServiceSourceInput!) { serviceCreate(input: { projectId: $projectId, name: $name, source: $source }) { id } }""" 
    data_svc, err_svc = railway_query(q_service_create, {
        "projectId": RAILWAY_PROJECT_ID, 
        "name": f"Tython-Worker-{user_id}", 
        "source": {"repo": "https://github.com/mustafanqnq-cmd/sarmdi-web-mine.git"}
    }, api_key)
    
    if err_svc:
        if "limit" in err_svc.lower():
            mark_key_as_full(api_key)
        return False, f"⚠️ خطأ إنشاء خدمة السورس: `{err_svc}`"
    
    worker_service_id = data_svc["serviceCreate"]["id"] 

    env_variables = {
        "API_HASH": str(API_HASH),
        "API_ID": str(API_ID),
        "ENV": ".",
        "LAUNCHER_PROXY_URL": "https://falling-leafgithub-proxy.mustafanqnq.workers.dev/", 
        "LAUNCHER_SECRET": "SUPHE999", 
        "TZ": "Asia/Baghdad", 
        "SESSION": session_string,
        "BOT_TOKEN": user_bot_token,
        "DATABASE_URL": user_db_url 
    }
    
    q_vars = """mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) { variableCollectionUpsert(input: $input) }""" 
    _, err_v2 = railway_query(q_vars, {
        "input": {"projectId": RAILWAY_PROJECT_ID, "environmentId": RAILWAY_ENV_ID, "serviceId": worker_service_id, "variables": env_variables}
    }, api_key)
    
    if err_v2:
        return False, f"⚠️ خطأ حقن الفارات: `{err_v2}`"

    q_deploy = """mutation deploymentCreate($input: DeploymentCreateInput!) { deploymentCreate(input: $input) { id } }"""
    railway_query(q_deploy, {"input": {"projectId": RAILWAY_PROJECT_ID, "environmentId": RAILWAY_ENV_ID, "serviceId": worker_service_id}}, api_key)

    return True, worker_service_id


# ⪼ واجهة البوت 
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id
    if not bot_config["is_active"] and user_id != ADMIN_ID:
        return await event.reply("⚠️ **عذراً، البوت متوقف حالياً لأغراض الصيانة.**")

    buttons = [
        [Button.inline("🚀 بدء تنصيب تايثون", data="start_deploy")],
        [Button.inline("📊 عدد المستخدمين", data="users_count")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([Button.inline("➕ اضف API KEY", data="add_api_key"), Button.inline("🗑 مسح الـ Keys", data="delete_all_keys")])
        buttons.append([Button.inline("📴 إطفاء البوت" if bot_config["is_active"] else "🟢 تشغيل البوت", data="toggle_bot")])

    await event.reply("**⎉╎أهلاً بك في بوت تنصيب سورس تايثون التلقائي 🚀**", buttons=buttons)

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    user_id = event.sender_id
    
    if data == "toggle_bot":
        if user_id != ADMIN_ID: return
        bot_config["is_active"] = not bot_config["is_active"]
        await event.answer("تم تغيير حالة البوت", alert=True)
        return

    elif data == "users_count":
        cursor.execute('SELECT COUNT(*) FROM users')
        await event.answer(f"📊 المستخدمين: {cursor.fetchone()[0]}", alert=True)

    elif data == "delete_all_keys":
        if user_id != ADMIN_ID: return
        cursor.execute("DELETE FROM api_keys")
        conn.commit()
        await event.answer("🗑 تم مسح جميع المفاتيح بنجاح!", alert=True)

    elif data == "add_api_key":
        if user_id != ADMIN_ID: return
        await event.answer("راجع الرسائل الخاصة...", alert=False)
        async with bot.conversation(event.chat_id, timeout=120) as conv:
            await conv.send_message("أرسل مفتاح الـ API الخاص بـ Railway الآن:")
            try:
                new_key = (await conv.get_response()).text.strip()
                cursor.execute("INSERT OR IGNORE INTO api_keys (key) VALUES (?)", (new_key,))
                conn.commit()
                await conv.send_message("✅ تم حفظ المفتاح بنجاح!")
            except Exception as e:
                await conv.send_message(f"⚠️ حدث خطأ: {e}")

    elif data == "start_deploy":
        if not bot_config["is_active"] and user_id != ADMIN_ID:
            return await event.answer("⚠️ البوت متوقف حالياً للصيانة.", alert=True)

        cursor.execute('SELECT service_id FROM users WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            return await event.answer("⚠️ لديك تنصيب قائم بالفعل!", alert=True)
        
        await event.answer("جاري التجهيز...", alert=False)
        await start_deployment_process(event.chat_id, user_id)

async def start_deployment_process(chat_id, user_id):
    async with bot.conversation(chat_id, timeout=300) as conv:
        try:
            await conv.send_message("**⎉╎أرسل الآن رقم هاتفك مع الرمز الدولي 📱**")
            phone = (await conv.get_response()).text.replace("+", "").replace(" ", "")
            status = await conv.send_message("⏳ جاري الاتصال...")
            
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH, device_model="TYTHON", system_version="Bot", app_version="1.0.0", lang_code="ar")
            await temp_client.connect()
            
            try:
                sent_code = await temp_client.send_code_request(phone)
            except FloodWaitError as e:
                return await status.edit(f"انتظر {e.seconds} ثانية وحاول مجددًا.")

            await status.edit("**⎉╎أرسل الكود بصيغة متباعدة (مثال: 7 2 1 4 3) 🔐**")
            code = (await conv.get_response()).text.replace(" ", "")
            
            try:
                await temp_client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash)
            except SessionPasswordNeededError:
                await conv.send_message("**⎉╎أرسل كلمة السر (التحقق بخطوتين) 🔑**")
                await temp_client.sign_in(password=(await conv.get_response()).text)

            session_string = temp_client.session.save()
            await temp_client.disconnect()

            await conv.send_message("**⪼ أرسل الآن توكن البوت الخاص بك من @BotFather 👇**")
            user_bot_token = (await conv.get_response()).text.strip()
            deploy_msg = await conv.send_message("**⏳ جاري عزل قاعدة البيانات وبناء السورس...**")
            
            success, result = await deploy_user_service(session_string, user_bot_token, user_id)

            if success:
                cursor.execute('INSERT INTO users (user_id, service_id) VALUES (?, ?)', (user_id, result))
                conn.commit()
                await deploy_msg.edit("✅ **تم التنصيب وعزل البيانات بنجاح تام!**")
            else:
                await deploy_msg.edit(f"❌ **فشل التنصيب:**\n\n{result}")

        except Exception as e:
            await conv.send_message(f"**⪼ حدث خطأ: {e} ⏣**")
        finally:
            if 'temp_client' in locals() and temp_client.is_connected():
                await temp_client.disconnect()

print("Secure Tython Deployer is Running...")
bot.run_until_disconnected()
