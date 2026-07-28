import os
import requests
from telethon import TelegramClient, events
import sqlite3

# إعداد التوكنات 
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
API_ID = 7219208
API_HASH = "64342b78a8d90e3f691d7a3a09112e7b"

# التوكن الصحيح الخاص بحسابك في رايلوي
RAILWAY_API_KEYS = [
    "bc397469-c89b-4841-8395-d551762c5a7d",  
]

# قاعدة بيانات محلية لحفظ التنصيبات
conn = sqlite3.connect('deployments.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, project_id TEXT)')
conn.commit()

bot = TelegramClient('deployer_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def deploy_to_railway(session_string, user_id):
    url = "https://backboard.railway.app/graphql/v2"
    
    env_variables = {
        "API_HASH": "64342b78a8d90e3f691d7a3a09112e7b",
        "API_ID": "7219208",
        "ENV": ".",
        "LAUNCHER_PROXY_URL": "https://falling-leafgithub-proxy.mustafanqnq.workers.dev/",
        "LAUNCHER_SECRET": "SUPHE999",
        "TZ": "Asia/Baghdad",
        "SESSION": session_string
    }

    api_key = RAILWAY_API_KEYS[0]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        # الخطوة 1: محاولة إنشاء المشروع الأساسي
        query_create_project = """
        mutation projectCreate($name: String!) {
          projectCreate(input: { name: $name }) {
            id
            environments { edges { node { id } } }
          }
        }
        """
        res1 = requests.post(url, json={
            "query": query_create_project,
            "variables": {"name": f"Tython-User-{user_id}"}
        }, headers=headers).json()

        if "errors" in res1:
            error_msg = res1['errors'][0]['message']
            return False, f"⚠️ تم الرفض من Railway أثناء إنشاء المشروع.\nالسبب الرسمي: `{error_msg}`"

        project_data = res1["data"]["projectCreate"]
        project_id = project_data["id"]
        environment_id = project_data["environments"]["edges"][0]["node"]["id"]

        # الخطوة 2: ربط السورس
        query_create_service = """
        mutation serviceCreate($projectId: String!, $repo: String!, $name: String!) {
          serviceCreate(input: {
            projectId: $projectId,
            name: $name,
            source: { repo: $repo }
          }) {
            id
          }
        }
        """
        res2 = requests.post(url, json={
            "query": query_create_service,
            "variables": {
                "projectId": project_id,
                "repo": "https://github.com/mustafanqnq-cmd/sarmdi-web-mine.git",
                "name": "tython-worker"
            }
        }, headers=headers).json()

        if "errors" in res2:
            error_msg2 = res2['errors'][0]['message']
            return False, f"⚠️ تم الرفض من Railway أثناء ربط السورس.\nالسبب الرسمي: `{error_msg2}`"

        service_id = res2["data"]["serviceCreate"]["id"]

        # الخطوة 3: حقن الفارات
        query_upsert_vars = """
        mutation variableCollectionUpsert($projectId: String!, $environmentId: String!, $serviceId: String!, $variables: Map!) {
          variableCollectionUpsert(input: {
            projectId: $projectId,
            environmentId: $environmentId,
            serviceId: $serviceId,
            variables: $variables
          })
        }
        """
        res3 = requests.post(url, json={
            "query": query_upsert_vars,
            "variables": {
                "projectId": project_id,
                "environmentId": environment_id,
                "serviceId": service_id,
                "variables": env_variables
            }
        }, headers=headers).json()

        if "errors" in res3:
            return False, f"خطأ في حقن الفارات: {res3['errors'][0]['message']}"

        return True, project_id

    except Exception as e:
        return False, f"خطأ برمجي: {str(e)}"

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply("أهلاً بك في بوت تنصيب سورس تايثون 🚀\n\nللتنصيب أرسل الأمر كالتالي:\n`/deploy SESSION_HERE`")

@bot.on(events.NewMessage(pattern=r'/deploy (.*)'))
async def deploy_handler(event):
    user_id = event.sender_id
    session_string = event.pattern_match.group(1).strip()

    cursor.execute('SELECT project_id FROM users WHERE user_id = ?', (user_id,))
    existing = cursor.fetchone()

    if existing:
        await event.reply(f"⚠️ لديك تنصيب قائم بالفعل!\nمعرف مشروعك: `{existing[0]}`")
        return

    msg = await event.reply("⏳ جاري الاتصال بـ Railway... يرجى الانتظار.")

    success, result = deploy_to_railway(session_string, user_id)

    if success:
        project_id = result
        cursor.execute('INSERT INTO users (user_id, project_id) VALUES (?, ?)', (user_id, project_id))
        conn.commit()
        await msg.edit(f"✅ **تم التنصيب وحقن الفارات بنجاح!**\nمعرف المشروع: `{project_id}`")
    else:
        await msg.edit(f"❌ **فشل التنصيب:**\n\n{result}")

print("Deployer Bot is Running...")
bot.run_until_disconnected()
