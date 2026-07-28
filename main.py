import os
import requests
from telethon import TelegramClient, events
import sqlite3

# إعداد التوكنات الأساسية
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

def deploy_full_stack(session_string, user_bot_token, user_id):
    url = "https://backboard.railway.app/graphql/v2"
    api_key = RAILWAY_API_KEYS[0]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        # 1. إنشاء المشروع الأساسي
        q_project = """
        mutation projectCreate($name: String!) {
          projectCreate(input: { name: $name }) {
            id
            environments { edges { node { id } } }
          }
        }
        """
        res1 = requests.post(url, json={"query": q_project, "variables": {"name": f"Tython-{user_id}"}}, headers=headers).json()
        if "errors" in res1:
            return False, f"خطأ في إنشاء المشروع: {res1['errors'][0]['message']}"
        
        proj_data = res1["data"]["projectCreate"]
        project_id = proj_data["id"]
        env_id = proj_data["environments"]["edges"][0]["node"]["id"]

        # 2. إنشاء خدمة قاعدة البيانات (Postgres) داخل المشروع
        q_db = """
        mutation serviceCreate($input: ServiceCreateInput!) {
          serviceCreate(input: $input) {
            id
          }
        }
        """
        res_db = requests.post(url, json={
            "query": q_db,
            "variables": {
                "input": {
                    "projectId": project_id,
                    "name": "postgres",
                    "source": { "image": "postgres:15" } # صورة بوستجرس رسمية
                }
            }
        }, headers=headers).json()
        
        if "errors" in res_db:
            return False, f"خطأ في إنشاء قاعدة البيانات: {res_db['errors'][0]['message']}"

        # 3. إنشاء خدمة السورس (الأنشر)
        res_service = requests.post(url, json={
            "query": q_db,
            "variables": {
                "input": {
                    "projectId": project_id,
                    "name": "tython-worker",
                    "source": { "repo": "https://github.com/mustafanqnq-cmd/sarmdi-web-mine.git" }
                }
            }
        }, headers=headers).json()

        if "errors" in res_service:
            return False, f"خطأ في ربط السورس: {res_service['errors'][0]['message']}"
        
        service_id = res_service["data"]["serviceCreate"]["id"]

        # 4. حقن كافة الفارات الثابتة والمتغيرة (بما فيها توكن البوت والسيشن)
        env_variables = {
            "API_HASH": "64342b78a8d90e3f691d7a3a09112e7b",
            "API_ID": "7219208",
            "ENV": ".",
            "LAUNCHER_PROXY_URL": "https://falling-leafgithub-proxy.mustafanqnq.workers.dev/",
            "LAUNCHER_SECRET": "SUPHE999",
            "TZ": "Asia/Baghdad",
            "SESSION": session_string,
            "BOT_TOKEN": user_bot_token,
            "DATABASE_URL": "${{postgres.DATABASE_URL}}" # ربط تلقائي بقاعدة البيانات التي أنشأناها قبل قليل
        }

        q_vars = """
        mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) {
          variableCollectionUpsert(input: $input)
        }
        """
        requests.post(url, json={
            "query": q_vars,
            "variables": {
                "input": {
                    "projectId": project_id,
                    "environmentId": env_id,
                    "serviceId": service_id,
                    "variables": env_variables
                }
            }
        }, headers=headers)

        return True, project_id

    except Exception as e:
        return False, f"خطأ برمجي: {str(e)}"

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply(
        "أهلاً بك في بوت تنصيب سورس تايثون 🚀\n\n"
        "للبدء بالتنصيب، أرسل الأمر بالشكل التالي:\n"
        "`/deploy SESSION_STRING USER_BOT_TOKEN`"
    )

@bot.on(events.NewMessage(pattern=r'/deploy (.*) (.*)'))
async def deploy_handler(event):
    user_id = event.sender_id
    session_string = event.pattern_match.group(1).strip()
    user_bot_token = event.pattern_match.group(2).strip()

    cursor.execute('SELECT project_id FROM users WHERE user_id = ?', (user_id,))
    existing = cursor.fetchone()

    if existing:
        await event.reply(f"⚠️ لديك تنصيب قائم بالفعل!\nمعرف مشروعك: `{existing[0]}`")
        return

    msg = await event.reply("⏳ جاري بناء البيئة الكاملة (قاعدة بيانات Postgres + سورس الأنشر + حقن الفارات)... يرجى الانتظار 🔄")

    success, result = deploy_full_stack(session_string, user_bot_token, user_id)

    if success:
        project_id = result
        cursor.execute('INSERT INTO users (user_id, project_id) VALUES (?, ?)', (user_id, project_id))
        conn.commit()
        await msg.edit(
            f"✅ **تم التنصيب الشامل بنجاح تام!**\n\n"
            f"🔹 تم إنشاء قاعدة بيانات Postgres مستقلة.\n"
            f"🔹 تم حقن السيشن، توكن بوت المستخدم، والـ LAUNCHER_SECRET.\n"
            f"🚀 معرف المشروع: `{project_id}`"
        )
    else:
        await msg.edit(f"❌ **فشل التنصيب:**\n\n{result}")

print("Full-Stack Deployer Bot is Running...")
bot.run_until_disconnected()
