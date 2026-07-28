import os
import requests
from telethon import TelegramClient, events
import sqlite3

# إعداد التوكنات الأساسية
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
API_ID = 7219208
API_HASH = "64342b78a8d90e3f691d7a3a09112e7b"

# توكن حساب رايلوي
RAILWAY_API_KEY = "4f08e771-2c65-4bb2-a0ee-eb9acff7a867"

conn = sqlite3.connect('deployments.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, project_id TEXT)')
conn.commit()

bot = TelegramClient('deployer_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def deploy_independent_project(session_string, user_bot_token, user_id):
    url = "https://backboard.railway.app/graphql/v2"
    headers = {
        "Authorization": f"Bearer {RAILWAY_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        # 1. إنشاء مشروع مستقل تماماً للمستخدم الجديد
        q_project = """
        mutation projectCreate($name: String!) {
          projectCreate(input: { name: $name }) {
            id
            environments { edges { node { id } } }
          }
        }
        """
        res_proj = requests.post(url, json={"query": q_project, "variables": {"name": f"Tython-User-{user_id}"}}, headers=headers).json()
        
        if "errors" in res_proj:
            return False, f"⚠️ عذراً، يبدو أنك وصلت لحد الحساب المجاني للمشاريع في رايلوي: `{res_proj['errors'][0]['message']}`"
        
        proj_data = res_proj["data"]["projectCreate"]
        project_id = proj_data["id"]
        environment_id = proj_data["environments"]["edges"][0]["node"]["id"]

        # 2. إنشاء قاعدة بيانات Postgres مستقلة داخل مشروع هذا المستخدم
        q_service = """
        mutation serviceCreate($input: ServiceCreateInput!) {
          serviceCreate(input: {
            projectId: $input.projectId,
            name: $input.name,
            source: $input.source
          }) {
            id
          }
        }
        """
        # ملاحظة GraphQL: سنقوم بتمرير المدخلات بصيغة صحيحة
        q_service_clean = """
        mutation serviceCreate($projectId: String!, $name: String!, $source: ServiceSourceInput!) {
          serviceCreate(input: {
            projectId: $projectId,
            name: $name,
            source: $source
          }) {
            id
          }
        }
        """
        
        res_db = requests.post(url, json={
            "query": q_service_clean,
            "variables": {
                "projectId": project_id,
                "name": "postgres",
                "source": { "image": "postgres:15" }
            }
        }, headers=headers).json()

        if "errors" in res_db:
            return False, f"خطأ في إنشاء قاعدة البيانات: {res_db['errors'][0]['message']}"

        # 3. إنشاء خدمة السورس (الأنشر) داخل نفس المشروع
        res_repo = requests.post(url, json={
            "query": q_service_clean,
            "variables": {
                "projectId": project_id,
                "name": "tython-worker",
                "source": { "repo": "https://github.com/mustafanqnq-cmd/sarmdi-web-mine.git" }
            }
        }, headers=headers).json()

        if "errors" in res_repo:
            return False, f"خطأ في ربط السورس: {res_repo['errors'][0]['message']}"
        
        service_id = res_repo["data"]["serviceCreate"]["id"]

        # 4. حقن كافة الفارات كاملة (مع ربط رابط الداتا بيز تلقائياً بالسورس الجديد)
        env_variables = {
            "API_HASH": "64342b78a8d90e3f691d7a3a09112e7b",
            "API_ID": "7219208",
            "ENV": ".",
            "LAUNCHER_PROXY_URL": "https://falling-leafgithub-proxy.mustafanqnq.workers.dev/",
            "LAUNCHER_SECRET": "SUPHE999",
            "TZ": "Asia/Baghdad",
            "SESSION": session_string,
            "BOT_TOKEN": user_bot_token,
            "DATABASE_URL": "${{postgres.DATABASE_URL}}"
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
                    "environmentId": environment_id,
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

    msg = await event.reply("⏳ جاري إنشاء مشروع مستقل للمستخدم + قاعدة بيانات Postgres + سورس الأنشر وحقن الفارات... يرجى الانتظار 🔄")

    success, result = deploy_independent_project(session_string, user_bot_token, user_id)

    if success:
        project_id = result
        cursor.execute('INSERT INTO users (user_id, project_id) VALUES (?, ?)', (user_id, project_id))
        conn.commit()
        await msg.edit(
            f"✅ **تم إنشاء المشروع المستقل وكافة المكونات بنجاح تام!**\n\n"
            f"🔹 تم بناء مشروع جديد خاص بالمستخدم.\n"
            f"🔹 تم إنشاء قاعدة بيانات Postgres مستقلة.\n"
            f"🔹 تم ربط السورس وحقن جميع الفارات كاملة.\n"
            f"🚀 معرف المشروع: `{project_id}`"
        )
    else:
        await msg.edit(f"❌ **فشل التنصيب:**\n\n{result}")

print("Independent Deployer Bot is Running...")
bot.run_until_disconnected()
