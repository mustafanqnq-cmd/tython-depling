import os
import asyncio
import requests
import sqlite3
import secrets
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    FloodWaitError,
)

# ⪼ استدعاء التوكن وأيدي المطور من بيئة الاستضافة (Railway Variables) لضمان أمان GitHub
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) # يجب إضافته في فارات رايلوي

API_ID = 7219208 
API_HASH = "64342b78a8d90e3f691d7a3a09112e7b" 

# ⪼ إعداد قاعدة البيانات
conn = sqlite3.connect('deployments.db', check_same_thread=False) 
cursor = conn.cursor() 
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, project_id TEXT)') 
cursor.execute('CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, is_full BOOLEAN DEFAULT 0)')
conn.commit() 

# ⪼ تهيئة البوت
bot = TelegramClient('deployer_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN) 

def get_active_api_key():
    cursor.execute("SELECT key FROM api_keys WHERE is_full = 0 LIMIT 1")
    result = cursor.fetchone()
    return result[0] if result else None

def mark_key_as_full(api_key):
    cursor.execute("UPDATE api_keys SET is_full = 1 WHERE key = ?", (api_key,))
    conn.commit()

def deploy_independent_project(session_string, user_bot_token, user_id):
    url = "https://backboard.railway.app/graphql/v2" 

    while True:
        api_key = get_active_api_key()
        
        if not api_key:
            return False, "⚠️ عذراً، نفذت مساحات الاستضافة حالياً. يرجى إبلاغ المطور."

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json" 
        }

        try:
            # 1. إنشاء المشروع
            q_project = """mutation projectCreate($name: String!) { projectCreate(input: { name: $name }) { id environments { edges { node { id } } } } }""" 
            res_proj = requests.post(url, json={"query": q_project, "variables": {"name": f"Tython-User-{user_id}"}}, headers=headers).json() 
            
            if "errors" in res_proj:
                error_msg = res_proj['errors'][0]['message'].lower()
                if "limit" in error_msg or "exceeded" in error_msg or "plan" in error_msg:
                    mark_key_as_full(api_key)
                    continue 
                else:
                    return False, f"⚠️ خطأ في رايلوي: `{res_proj['errors'][0]['message']}`" 
            
            project_id = res_proj["data"]["projectCreate"]["id"] 
            environment_id = res_proj["data"]["projectCreate"]["environments"]["edges"][0]["node"]["id"] 

            # 2. إنشاء قاعدة البيانات Postgres
            q_service_clean = """mutation serviceCreate($projectId: String!, $name: String!, $source: ServiceSourceInput!) { serviceCreate(input: { projectId: $projectId, name: $name, source: $source }) { id } }""" 
            res_db = requests.post(url, json={"query": q_service_clean, "variables": {"projectId": project_id, "name": "postgres", "source": { "image": "postgres:15" }}}, headers=headers).json() 
            db_service_id = res_db["data"]["serviceCreate"]["id"]

            # 3. حقن فارات قاعدة البيانات
            db_password = secrets.token_hex(12) # توليد كلمة مرور عشوائية قوية لكل مستخدم
            db_vars = {
                "POSTGRES_USER": "postgres",
                "POSTGRES_PASSWORD": db_password,
                "POSTGRES_DB": "tython_db"
            }
            q_vars = """mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) { variableCollectionUpsert(input: $input) }""" 
            requests.post(url, json={"query": q_vars, "variables": {"input": {"projectId": project_id, "environmentId": environment_id, "serviceId": db_service_id, "variables": db_vars}}}, headers=headers)

            # 4. إنشاء خدمة السورس (الأنشر)
            res_repo = requests.post(url, json={"query": q_service_clean, "variables": {"projectId": project_id, "name": "tython-worker", "source": { "repo": "https://github.com/mustafanqnq-cmd/sarmdi-web-mine.git" }}}, headers=headers).json() 
            worker_service_id = res_repo["data"]["serviceCreate"]["id"] 

            # 5. حقن فارات السورس (مع ربط رابط الداتا بيز الداخلي)
            env_variables = {
                "API_HASH": str(API_HASH),
                "API_ID": str(API_ID),
                "ENV": ".",
                "LAUNCHER_PROXY_URL": "https://falling-leafgithub-proxy.mustafanqnq.workers.dev/", 
                "LAUNCHER_SECRET": "SUPHE999", 
                "TZ": "Asia/Baghdad", 
                "SESSION": session_string,
                "BOT_TOKEN": user_bot_token,
                "DATABASE_URL": f"postgresql://postgres:{db_password}@postgres.railway.internal:5432/tython_db" 
            }
            requests.post(url, json={"query": q_vars, "variables": {"input": {"projectId": project_id, "environmentId": environment_id, "serviceId": worker_service_id, "variables": env_variables}}}, headers=headers) 

            # 6. إجبار رايلوي على بدء التنصيب فوراً
            q_deploy = """mutation deploymentCreate($input: DeploymentCreateInput!) { deploymentCreate(input: $input) { id } }"""
            
            # تنصيب قاعدة البيانات
            requests.post(url, json={"query": q_deploy, "variables": {"input": {"projectId": project_id, "environmentId": environment_id, "serviceId": db_service_id}}}, headers=headers)
            
            # تنصيب سورس تايثون
            requests.post(url, json={"query": q_deploy, "variables": {"input": {"projectId": project_id, "environmentId": environment_id, "serviceId": worker_service_id}}}, headers=headers)

            return True, project_id
        except Exception as e:
            return False, f"خطأ برمجي: {str(e)}" 


# ⪼ واجهة البوت الأساسية (تتغير حسب المستخدم)
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    buttons = [
        [Button.inline("🚀 بدء تنصيب تايثون", data="start_deploy")],
        [Button.inline("📊 عدد المستخدمين", data="users_count")]
    ]
    
    # إضافة أزرار الإدارة الشفافة إذا كان المستخدم هو المطور فقط
    if event.sender_id == ADMIN_ID:
        buttons.append([Button.inline("➕ اضف API KEY", data="add_api_key")])
        buttons.append([Button.inline("🗑 حذف كُل حسابات الـ API KEY", data="delete_all_keys")])

    await event.reply(
        "**⎉╎أهلاً بك في بوت تنصيب سورس تايثون التلقائي 🚀**\n\n"
        "⪼ من خلال هذا البوت يمكنك تنصيب السورس الخاص بك بخطوات بسيطة وآمنة تماماً.\n"
        "⪼ الجلسة يتم استخراجها برمجياً وتُرفع مباشرة للخادم دون أن تُحفظ أو تُرسل لأحد.",
        buttons=buttons
    )

# ⪼ التعامل مع الأزرار
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    user_id = event.sender_id
    
    if data == "users_count":
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        await event.answer(f"📊 عدد المستخدمين المنصبين حالياً: {count}", alert=True)

    elif data == "delete_all_keys":
        if user_id != ADMIN_ID:
            return await event.answer("⚠️ هذا الزر مخصص للمطور فقط!", alert=True)
        
        cursor.execute("DELETE FROM api_keys")
        conn.commit()
        await event.answer("🗑 تم مسح جميع مفاتيح API من البوت بنجاح! (لم تتأثر حساباتك في رايلوي)", alert=True)

    elif data == "add_api_key":
        if user_id != ADMIN_ID:
            return await event.answer("⚠️ هذا الزر مخصص للمطور فقط!", alert=True)
        
        await event.answer("راجع الرسائل الخاصة لإضافة المفتاح...", alert=False)
        async with bot.conversation(event.chat_id, timeout=120) as conv:
            await conv.send_message("**⎉╎أرسل الآن مفتاح `RAILWAY_API_KEY` الجديد لإضافته للمخزن:**")
            try:
                response = await conv.get_response()
                new_key = response.text.strip()
                
                cursor.execute("INSERT INTO api_keys (key) VALUES (?)", (new_key,))
                conn.commit()
                
                # عرض إحصائيات سريعة للمطور بعد الإضافة
                cursor.execute('SELECT COUNT(*) FROM api_keys')
                total = cursor.fetchone()[0]
                await conv.send_message(f"✅ **تمت إضافة المفتاح بنجاح!**\n📊 إجمالي المفاتيح في البوت الآن: `{total}`")
            except sqlite3.IntegrityError:
                await conv.send_message("⚠️ **هذا المفتاح مضاف مسبقاً في قاعدة البيانات!**")
            except asyncio.TimeoutError:
                await conv.send_message("⚠️ **انتهى وقت الانتظار. حاول مرة أخرى.**")

    elif data == "start_deploy":
        cursor.execute('SELECT project_id FROM users WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            await event.answer("⚠️ لديك تنصيب قائم بالفعل!", alert=True)
            return
        
        await event.answer("جاري بدء عملية التنصيب...", alert=False)
        await start_deployment_process(event.chat_id, user_id)

async def start_deployment_process(chat_id, user_id):
    """ نظام المحادثة لاستخراج الجلسة والتوكن والتنصيب """
    async with bot.conversation(chat_id, timeout=300) as conv:
        try:
            await conv.send_message("**⎉╎أرسل الآن رقم هاتفك مع الرمز الدولي (مثال: +964...) 📱**")
            phone_msg = await conv.get_response()
            phone = phone_msg.text.replace("+", "").replace(" ", "")
            
            status = await conv.send_message(f"**⎉╎جاري الاتصال بتليجرام للرقم {phone}... ⏳**")
            
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH, device_model="TYTHON Installer", system_version="Bot", app_version="1.0.0", lang_code="ar")
            await temp_client.connect()
            
            try:
                sent_code = await temp_client.send_code_request(phone)
            except FloodWaitError as e:
                await status.edit(f"**⪼ محاولات كثيرة، انتظر {e.seconds} ثانية وحاول مجددًا ⏣**")
                return

            await status.edit("**⎉╎تم إرسال كود التحقق 📩**\n**⪼ أرسل الكود بصيغة متباعدة (مثال: 7 2 1 4 3) 🔐**")
            
            code_msg = await conv.get_response()
            code = code_msg.text.replace(" ", "")
            
            try:
                await temp_client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash)
            except SessionPasswordNeededError:
                await conv.send_message("**⎉╎الحساب محمي بتحقق بخطوتين، أرسل كلمة السر 🔑**")
                pass_msg = await conv.get_response()
                await temp_client.sign_in(password=pass_msg.text)

            session_string = temp_client.session.save()
            await temp_client.disconnect()

            instructions = (
                "**⎉╎تم استخراج الجلسة داخلياً وتأمينها بنجاح ✅**\n\n"
                "**⪼ الآن، نحتاج إلى توكن البوت الخاص بك (لحساب تايثون).**\n"
                "1. اذهب إلى @BotFather\n"
                "2. أرسل أمر `/newbot` لصنع بوت جديد.\n"
                "3. انسخ التوكن (Token) وأرسله هنا 👇"
            )
            await conv.send_message(instructions)
            token_msg = await conv.get_response()
            user_bot_token = token_msg.text.strip()

            deploy_msg = await conv.send_message("**⏳ جاري الآن بناء مشروعك على الخادم وربط السورس... يرجى الانتظار 🔄**")
            
            success, result = deploy_independent_project(session_string, user_bot_token, user_id)

            if success:
                cursor.execute('INSERT INTO users (user_id, project_id) VALUES (?, ?)', (user_id, result))
                conn.commit()
                await deploy_msg.edit(
                    f"✅ **تم تنصيب سورس تايثون بنجاح تام!**\n\n"
                    f"🔹 تم تشفير الجلسة وحقنها تلقائياً.\n"
                    f"🔹 تم ربط توكن البوت الخاص بك.\n"
                    f"🚀 معرف مشروعك: `{result}`\n\n"
                    f"**⪼ يمكنك الآن التوجه لبوتك واستخدام السورس.**"
                )
            else:
                await deploy_msg.edit(f"❌ **فشل التنصيب:**\n\n{result}")

        except asyncio.TimeoutError:
            await conv.send_message("**⪼ انتهى الوقت، يرجى إعادة المحاولة من جديد ⏣**")
        except Exception as e:
            await conv.send_message(f"**⪼ حدث خطأ: {e} ⏣**")
        finally:
            if 'temp_client' in locals() and temp_client.is_connected():
                await temp_client.disconnect()

print("Secure Tython Deployer is Running...")
bot.run_until_disconnected()
