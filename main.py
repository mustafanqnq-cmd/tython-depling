import os
import requests
from telethon import TelegramClient, events
import sqlite3

# 1. سحب التوكنات والرموز من متغيرات البيئة لحمايتها (لا تضعها مباشرة هنا إذا كنت سترفع الكود لـ Github)
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
API_ID = 7219208
API_HASH = "64342b78a8d90e3f691d7a3a09112e7b"

# قائمة مفاتيح API لحساباتك المتعددة في Railway (تمت إضافة الحساب الذي أرسلته كمثال)
# يمكنك إضافة المزيد من المفاتيح في هذه القائمة كلما امتلأ حساب
RAILWAY_API_KEYS = [
    "a9e959ca-79d5-40f7-a322-fd087444559d",  # الحساب الأول
    # "مفتاح_الحساب_الثاني_هنا",               
    # "مفتاح_الحساب_الثالث_هنا"                
]

# 2. قاعدة بيانات محلية خفيفة (تحفظ الآيدي الخاص بالمستخدم وآيدي مشروعه فقط)
conn = sqlite3.connect('deployments.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, project_id TEXT)')
conn.commit()

# تهيئة البوت
bot = TelegramClient('deployer_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def deploy_to_railway(session_string, user_id):
    url = "https://backboard.railway.app/graphql/v2"
    
    # القائمة الكاملة للفارات الثابتة المطلوبة للأنشر + سيشن المستخدم
    env_variables = {
        "API_HASH": "64342b78a8d90e3f691d7a3a09112e7b",
        "API_ID": "7219208",
        "ENV": ".",
        "LAUNCHER_PROXY_URL": "https://falling-leafgithub-proxy.mustafanqnq.workers.dev/",
        "LAUNCHER_SECRET": "SUPHE999",
        "TZ": "Asia/Baghdad",
        "SESSION": session_string
    }

    # حلقة تنقل البوت من حساب لآخر في حال امتلاء السعة المجانية لأحدها
    for api_key in RAILWAY_API_KEYS:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            # الخطوة 1: إنشاء مشروع جديد باسم المستخدم
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

            # التحقق مما إذا كان الحساب ممتلئاً لتخطيه
            if "errors" in res1:
                error_msg = res1['errors'][0]['message']
                if "limit exceeded" in error_msg.lower():
                    continue # تخطى هذا الحساب وانتقل للمفتاح التالي
                else:
                    return False, f"خطأ في إنشاء المشروع: {error_msg}"

            project_data = res1["data"]["projectCreate"]
            project_id = project_data["id"]
            environment_id = project_data["environments"]["edges"][0]["node"]["id"]

            # الخطوة 2: ربط ريبو الأنشر الخاص بك بالمشروع (تم حل مشكلة Invalid service name)
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
                    "name": "tython-worker" # اسم الخدمة لتجنب الخطأ
                }
            }, headers=headers).json()

            if "errors" in res2:
                return False, f"خطأ في ربط الريبو: {res2['errors'][0]['message']}"

            service_id = res2["data"]["serviceCreate"]["id"]

            # الخطوة 3: حقن كافة الفارات بالملم في سيرفر Railway مباشرة
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
            return False, str(e)

    # إذا فحص كل الحسابات وكانت كلها ممتلئة
    return False, "جميع الحسابات المتاحة ممتلئة حالياً! يرجى إضافة حسابات Railway جديدة لمصفوفة المفاتيح."

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply("أهلاً بك في بوت تنصيب سورس تايثون 🚀\n\nللتنصيب أرسل الأمر كالتالي:\n`/deploy SESSION_HERE`")

@bot.on(events.NewMessage(pattern=r'/deploy (.*)'))
async def deploy_handler(event):
    user_id = event.sender_id
    session_string = event.pattern_match.group(1).strip()

    # التحقق مما إذا كان المستخدم منصب مسبقاً
    cursor.execute('SELECT project_id FROM users WHERE user_id = ?', (user_id,))
    existing = cursor.fetchone()

    if existing:
        await event.reply(f"⚠️ لديك تنصيب قائم بالفعل!\nمعرف مشروعك: `{existing[0]}`")
        return

    msg = await event.reply("⏳ جاري إنشاء البيئة وحقن الـ الفارات... يرجى الانتظار.")

    # تنفيذ عملية التنصيب
    success, result = deploy_to_railway(session_string, user_id)

    if success:
        project_id = result
        # حفظ الآيدي الخاص بالمستخدم ومعرف المشروع فقط
        cursor.execute('INSERT INTO users (user_id, project_id) VALUES (?, ?)', (user_id, project_id))
        conn.commit()

        await msg.edit(f"✅ **تم التنصيب وحقن الفارات بنجاح!**\n\nتم إطلاق الأنشر وسورس تايثون يعمل الآن 🚀\nمعرف المشروع: `{project_id}`")
    else:
        await msg.edit(f"❌ **حدث خطأ أثناء التنصيب:**\n\n`{result}`")

print("Deployer Bot is Running...")
bot.run_until_disconnected()
