import os
import requests
from telethon import TelegramClient, events
import sqlite3

# إعداد التوكنات الأساسية للبوت الخاص بك
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
API_ID = 7219208
API_HASH = "64342b78a8d90e3f691d7a3a09112e7b"

# توكن حساب رايلوي
RAILWAY_API_KEYS = [
    "bc397469-c89b-4841-8395-d551762c5a7d",  
]

conn = sqlite3.connect('deployments.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, project_id TEXT)')
conn.commit()

bot = TelegramClient('deployer_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def deploy_template_to_railway(session_string, user_bot_token, user_id):
    # استخدام نقطة نهاية الـ Templates في رايلوي لضمان جلب السورس وقاعدة البيانات معاً
    url = "https://backboard.railway.app/graphql/v2"
    
    api_key = RAILWAY_API_KEYS[0]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        # استعلام النشر عبر القالب (Template Deployment)
        # هذا الاستعلام يخبر رايلوي بإنشاء المشروع، جلب الريبو، إضافة داتا بيز، وحقن الفارات دفعة واحدة
        query = """
        mutation templateDeploy($input: TemplateDeployInput!) {
          templateDeploy(input: $input) {
            projectId
          }
        }
        """
        
        # الفارات التي سيتم حقنها مباشرة في بيئة المستخدم المستضافة حديثاً
        variables = {
            "input": {
                "code": "sarmdi-web-mine", # أو رابط الريبو الكامل إذا تطلب الأمر
                "variables": {
                    "API_HASH": "64342b78a8d90e3f691d7a3a09112e7b",
                    "API_ID": "7219208",
                    "ENV": ".",
                    "LAUNCHER_PROXY_URL": "https://falling-leafgithub-proxy.mustafanqnq.workers.dev/",
                    "LAUNCHER_SECRET": "SUPHE999",
                    "TZ": "Asia/Baghdad",
                    "SESSION": session_string,
                    "BOT_TOKEN": user_bot_token # توكن بوت المستخدم الخاص
                }
            }
        }

        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers).json()

        if "errors" in response:
            error_msg = response['errors'][0]['message']
            return False, f"⚠️ فشل نشر التيمبليت:\n`{error_msg}`"

        project_id = response["data"]["templateDeploy"]["projectId"]
        return True, project_id

    except Exception as e:
        return False, f"خطأ برمجي: {str(e)}"

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply(
        "أهلاً بك في بوت تنصيب سورس تايثون 🚀\n\n"
        "للبدء بالتنصيب، أرسل الأمر بالشكل التالي:\n"
        "`/deploy SESSION_STRING USER_BOT_TOKEN`\n\n"
        "*(ملاحظة: افصل بين السيشن وتوكن بوتك بمسافة واحدة)*"
    )

@bot.on(events.NewMessage(pattern=r'/deploy (.*) (.*)'))
async def deploy_handler(event):
    user_id = event.sender_id
    session_string = event.pattern_match.group(1).strip()
    user_bot_token = event.pattern_match.group(2).strip()

    # التحقق مما إذا كان المستخدم منصب مسبقاً
    cursor.execute('SELECT project_id FROM users WHERE user_id = ?', (user_id,))
    existing = cursor.fetchone()

    if existing:
        await event.reply(f"⚠️ لديك تنصيب قائم بالفعل!\nمعرف مشروعك: `{existing[0]}`")
        return

    msg = await event.reply("⏳ جاري إنشاء البيئة الكاملة (قاعدة البيانات + الأنشر + الفارات)... يرجى الانتظار 🔄")

    # تنفيذ التنصيب بنظام التيمبليت
    success, result = deploy_template_to_railway(session_string, user_bot_token, user_id)

    if success:
        project_id = result
        cursor.execute('INSERT INTO users (user_id, project_id) VALUES (?, ?)', (user_id, project_id))
        conn.commit()
        await msg.edit(
            f"✅ **تم التنصيب الشامل بنجاح تام!**\n\n"
            f"🔹 تم إنشاء قاعدة بيانات Postgres مستقلة.\n"
            f"🔹 تم حقن السيشن وتوكن البوت والـ LAUNCHER_SECRET.\n"
            f"🚀 معرف المشروع الخاص بك: `{project_id}`"
        )
    else:
        await msg.edit(f"❌ **فشل التنصيب:**\n\n{result}")

print("Advanced Deployer Bot is Running...")
bot.run_until_disconnected()
