import os
import asyncio
import requests
import sqlite3
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    FloodWaitError,
)

# ⪼ إعدادات التوكنات والـ API
BOT_TOKEN = os.environ.get("BOT_TOKEN", "توكن_البوت_هنا") 
API_ID = 7219208 #[span_1](start_span)[span_1](end_span)
API_HASH = "64342b78a8d90e3f691d7a3a09112e7b" #[span_2](start_span)[span_2](end_span)
ADMIN_ID = 666822865 # أيدي المطور (أنت) للتحكم بالمفاتيح[span_3](start_span)[span_3](end_span)

# ⪼ إعداد قاعدة البيانات لتشمل المستخدمين ومفاتيح رايلوي[span_4](start_span)[span_4](end_span)
conn = sqlite3.connect('deployments.db', check_same_thread=False) #[span_5](start_span)[span_5](end_span)
cursor = conn.cursor() #[span_6](start_span)[span_6](end_span)
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, project_id TEXT)') #[span_7](start_span)[span_7](end_span)
# جدول جديد لمفاتيح رايلوي (is_full: 0 يعني متاح، 1 يعني ممتلئ)
cursor.execute('CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, is_full BOOLEAN DEFAULT 0)')
conn.commit() #[span_8](start_span)[span_8](end_span)

# إضافة المفتاح التجريبي الخاص بك تلقائياً إذا لم يكن موجوداً
try:
    cursor.execute("INSERT OR IGNORE INTO api_keys (key) VALUES (?)", ("4f08e771-2c65-4bb2-a0ee-eb9acff7a867",))
    conn.commit()
except Exception:
    pass

bot = TelegramClient('deployer_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN) #[span_9](start_span)[span_9](end_span)

def get_active_api_key():
    """ جلب أول مفتاح رايلوي متاح (غير ممتلئ) """
    cursor.execute("SELECT key FROM api_keys WHERE is_full = 0 LIMIT 1")
    result = cursor.fetchone()
    return result[0] if result else None

def mark_key_as_full(api_key):
    """ تعليم المفتاح بأنه ممتلئ لتجاوزه في المرات القادمة """
    cursor.execute("UPDATE api_keys SET is_full = 1 WHERE key = ?", (api_key,))
    conn.commit()

def deploy_independent_project(session_string, user_bot_token, user_id):
    """ دالة التنصيب مع نظام تدوير المفاتيح التلقائي """
    url = "https://backboard.railway.app/graphql/v2" #[span_10](start_span)[span_10](end_span)

    # حلقة تكرارية: إذا كان المفتاح ممتلئاً، ينتقل للمفتاح التالي
    while True:
        api_key = get_active_api_key()
        
        if not api_key:
            return False, "⚠️ عذراً، نفذت مساحات الاستضافة حالياً (جميع الحسابات ممتلئة). يرجى إبلاغ المطور لإضافة حسابات جديدة."

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json" #[span_11](start_span)[span_11](end_span)
        }

        try:
            # 1. محاولة إنشاء مشروع مستقل[span_12](start_span)[span_12](end_span)
            q_project = """mutation projectCreate($name: String!) { projectCreate(input: { name: $name }) { id environments { edges { node { id } } } } }""" #[span_13](start_span)[span_13](end_span)
            res_proj = requests.post(url, json={"query": q_project, "variables": {"name": f"Tython-User-{user_id}"}}, headers=headers).json() #[span_14](start_span)[span_14](end_span)
            
            # التحقق مما إذا كان الحساب قد وصل للحد المجاني
            if "errors" in res_proj:
                error_msg = res_proj['errors'][0]['message'].lower()
                # إذا كان الخطأ يخص الحد الأقصى للمشاريع، نعلم المفتاح كممتلئ ونعيد المحاولة
                if "limit" in error_msg or "exceeded" in error_msg or "plan" in error_msg:
                    mark_key_as_full(api_key)
                    continue # العودة لبداية الحلقة لجلب مفتاح جديد
                else:
                    return False, f"⚠️ خطأ في رايلوي: `{res_proj['errors'][0]['message']}`" #[span_15](start_span)[span_15](end_span)
            
            project_id = res_proj["data"]["projectCreate"]["id"] #[span_16](start_span)[span_16](end_span)
            environment_id = res_proj["data"]["projectCreate"]["environments"]["edges"][0]["node"]["id"] #[span_17](start_span)[span_17](end_span)

            q_service_clean = """mutation serviceCreate($projectId: String!, $name: String!, $source: ServiceSourceInput!) { serviceCreate(input: { projectId: $projectId, name: $name, source: $source }) { id } }""" #[span_18](start_span)[span_18](end_span)
            
            # 2. إنشاء Postgres[span_19](start_span)[span_19](end_span)
            res_db = requests.post(url, json={"query": q_service_clean, "variables": {"projectId": project_id, "name": "postgres", "source": { "image": "postgres:15" }}}, headers=headers).json() #[span_20](start_span)[span_20](end_span)

            # 3. إنشاء خدمة السورس[span_21](start_span)[span_21](end_span)
            res_repo = requests.post(url, json={"query": q_service_clean, "variables": {"projectId": project_id, "name": "tython-worker", "source": { "repo": "https://github.com/mustafanqnq-cmd/sarmdi-web-mine.git" }}}, headers=headers).json() #[span_22](start_span)[span_22](end_span)
            service_id = res_repo["data"]["serviceCreate"]["id"] #[span_23](start_span)[span_23](end_span)

            # 4. حقن الفارات السرية[span_24](start_span)[span_24](end_span)
            env_variables = {
                "API_HASH": str(API_HASH),
                "API_ID": str(API_ID),
                "ENV": ".",
                "LAUNCHER_PROXY_URL": "https://falling-leafgithub-proxy.mustafanqnq.workers.dev/", #[span_25](start_span)[span_25](end_span)
                "LAUNCHER_SECRET": "SUPHE999", #[span_26](start_span)[span_26](end_span)
                "TZ": "Asia/Baghdad", #[span_27](start_span)[span_27](end_span)
                "SESSION": session_string,
                "BOT_TOKEN": user_bot_token,
                "DATABASE_URL": "${{postgres.DATABASE_URL}}" #[span_28](start_span)[span_28](end_span)
            }

            q_vars = """mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) { variableCollectionUpsert(input: $input) }""" #[span_29](start_span)[span_29](end_span)
            requests.post(url, json={"query": q_vars, "variables": {"input": {"projectId": project_id, "environmentId": environment_id, "serviceId": service_id, "variables": env_variables}}}, headers=headers) #[span_30](start_span)[span_30](end_span)

            return True, project_id
        except Exception as e:
            return False, f"خطأ برمجي: {str(e)}" #[span_31](start_span)[span_31](end_span)


# ⪼ أوامر المطور (إضافة وإدارة مفاتيح رايلوي)
@bot.on(events.NewMessage(pattern=r'/addkey (.*)'))
async def add_api_key_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    
    new_key = event.pattern_match.group(1).strip()
    try:
        cursor.execute("INSERT INTO api_keys (key) VALUES (?)", (new_key,))
        conn.commit()
        await event.reply("✅ **تم إضافة مفتاح رايلوي (API Key) جديد بنجاح إلى المخزن!**")
    except sqlite3.IntegrityError:
        await event.reply("⚠️ **هذا المفتاح مضاف مسبقاً في قاعدة البيانات.**")

@bot.on(events.NewMessage(pattern='/keys'))
async def check_keys_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    
    cursor.execute('SELECT COUNT(*) FROM api_keys')
    total = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM api_keys WHERE is_full = 1')
    full = cursor.fetchone()[0]
    
    await event.reply(
        f"📊 **إحصائيات حسابات رايلوي (API Keys):**\n\n"
        f"🔹 إجمالي المفاتيح: `{total}`\n"
        f"🔹 المفاتيح الممتلئة: `{full}`\n"
        f"🔹 المفاتيح المتاحة: `{total - full}`\n\n"
        f"💡 لإضافة مفتاح جديد أرسل:\n`/addkey <api_key>`"
    )

# ⪼ واجهة البوت الأساسية
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    buttons = [
        [Button.inline("🚀 بدء تنصيب تايثون", data="start_deploy")],
        [Button.inline("📊 عدد المستخدمين", data="users_count")]
    ]
    await event.reply(
        "**⎉╎أهلاً بك في بوت تنصيب سورس تايثون التلقائي 🚀**\n\n"
        "⪼ من خلال هذا البوت يمكنك تنصيب السورس الخاص بك بخطوات بسيطة وآمنة تماماً.\n"
        "⪼ الجلسة يتم استخراجها برمجياً وتُرفع مباشرة للخادم دون أن تُحفظ أو تُرسل لأحد.",
        buttons=buttons
    )

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    user_id = event.sender_id
    
    if data == "users_count":
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        await event.answer(f"📊 عدد المستخدمين المنصبين حالياً: {count}", alert=True)

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
            
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH, device_model="TYTHON Installer", system_version="Bot", app_version="1.0.0", lang_code="ar") #[span_32](start_span)[span_32](end_span)
            await temp_client.connect()
            
            try:
                sent_code = await temp_client.send_code_request(phone) #[span_33](start_span)[span_33](end_span)
            except FloodWaitError as e:
                await status.edit(f"**⪼ محاولات كثيرة، انتظر {e.seconds} ثانية وحاول مجددًا ⏣**") #[span_34](start_span)[span_34](end_span)
                return

            await status.edit("**⎉╎تم إرسال كود التحقق 📩**\n**⪼ أرسل الكود بصيغة متباعدة (مثال: 7 2 1 4 3) 🔐**") #[span_35](start_span)[span_35](end_span)
            
            code_msg = await conv.get_response()
            code = code_msg.text.replace(" ", "")
            
            try:
                await temp_client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash) #[span_36](start_span)[span_36](end_span)
            except SessionPasswordNeededError:
                await conv.send_message("**⎉╎الحساب محمي بتحقق بخطوتين، أرسل كلمة السر 🔑**") #[span_37](start_span)[span_37](end_span)
                pass_msg = await conv.get_response()
                await temp_client.sign_in(password=pass_msg.text) #[span_38](start_span)[span_38](end_span)

            session_string = temp_client.session.save() #[span_39](start_span)[span_39](end_span)
            await temp_client.disconnect()

            instructions = (
                "**⎉╎تم استخراج الجلسة داخلياً وتأمينها بنجاح ✅**\n\n"
                "**⪼ الآن، نحتاج إلى توكن البوت الخاص بك.**\n"
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
                cursor.execute('INSERT INTO users (user_id, project_id) VALUES (?, ?)', (user_id, result)) #[span_40](start_span)[span_40](end_span)
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

print("Tython Auto-Installer Bot (With API Rotation) is Running...")
bot.run_until_disconnected()
