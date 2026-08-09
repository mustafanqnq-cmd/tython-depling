import os
import json
import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

# ==========================================
# 1. الإعدادات الأساسية (تسحب بآمان من رايلوي)
# ==========================================
API_ID = int(os.getenv("API_ID", "7219208"))  
API_HASH = os.getenv("API_HASH", "64342b78a8d90e3f691d7a3a09112e7b") 

BOT_TOKEN = os.getenv("BOT_TOKEN") 
ADMIN_IDS = [666822865]  # ⚠️ استبدلها بالـ ID الخاص بك

USERBOT_REPO = "mustafanqnq-cmd/Sarmadi-Deploy-Web" 
TOKENS_FILE = "railway_tokens.json"

if not BOT_TOKEN:
    print("⚠️ تحذير: يرجى إضافة BOT_TOKEN في فارات رايلوي!")

# ==========================================
# 2. نظام حفظ توكنات حسابات رايلوي
# ==========================================
def load_railway_tokens():
    if os.path.exists(TOKENS_FILE):
        try:
            with open(TOKENS_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_railway_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f)

railway_tokens = load_railway_tokens() 
user_steps = {}       
user_data = {}        

app = Client("TythonDeployBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 3. أوامر ولوحة الإدارة
# ==========================================
@app.on_message(filters.command("admin") & filters.user(ADMIN_IDS))
async def admin_panel(client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة توكن رايلوي", callback_data="admin_add_token")],
        [InlineKeyboardButton("🗑 حذف توكن رايلوي", callback_data="admin_del_token")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")]
    ])
    await message.reply_text("مرحباً بك في لوحة تحكم مطوري تايثون 👨‍💻:", reply_markup=keyboard)

@app.on_callback_query(filters.regex("^admin_") & filters.user(ADMIN_IDS))
async def admin_callbacks(client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data

    if data == "admin_add_token":
        user_steps[chat_id] = "admin_waiting_token"
        await callback_query.message.reply_text("أرسل الآن توكن رايلوي (Railway API Token) الخاص بالحساب الجديد:")
    
    elif data == "admin_del_token":
        if len(railway_tokens) > 0:
            railway_tokens.pop()
            save_railway_tokens(railway_tokens)
            await callback_query.message.reply_text("✅ تم حذف آخر توكن رايلوي تم إضافته بنجاح.")
        else:
            await callback_query.message.reply_text("⚠️ القائمة فارغة! لا توجد توكنات لحذفها.")
    
    elif data == "admin_stats":
        count = len(railway_tokens)
        users_count = len(user_data)
        await callback_query.message.reply_text(
            f"📊 **إحصائيات المنصبين:**\n\n"
            f"✅ حسابات رايلوي المتوفرة للتنصيب: {count}\n"
            f"👥 عدد عمليات التنصيب الجارية: {users_count}"
        )

@app.on_message(filters.private & filters.user(ADMIN_IDS) & ~filters.command(["start", "admin"]))
async def admin_text_handler(client, message: Message):
    chat_id = message.chat.id
    step = user_steps.get(chat_id)

    if step == "admin_waiting_token":
        railway_tokens.append(message.text)
        save_railway_tokens(railway_tokens)
        user_steps.pop(chat_id, None)
        await message.reply_text("✅ تم إضافة توكن رايلوي وحفظه بنجاح! الحساب جاهز للتنصيب.")

# ==========================================
# 4. أوامر المستخدم (بدء التنصيب)
# ==========================================
@app.on_message(filters.command("start") & filters.private & ~filters.user(ADMIN_IDS))
async def start_command(client, message: Message):
    if len(railway_tokens) == 0:
        await message.reply_text("❌ السورس متوقف الى اشعار اخر، تواصل مع المطور للتنصيب المُباشر @CC99V")
        return

    START_TEXT = (
        "أهلًا عزيزي انا بوت تنصيب سورس تايثون (بوت تجريبي قيد التطوير) ألخاص ب - مُصـطَفَئٰ السّرمَدِيّ .\n"
        "هذا بوت تنصيب أمن وسَريع ومدته 5 ايام وإذا اردت الإشتراك راسل المُطور لكافة ألتَفاصيل.\n"
        "(وإذا فشل معك البوت ولم تستطع التنصيب تواصل مع المُطور للتنصيب المُباشر)."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("بدأ التنصيب الان 🚀", callback_data="start_deploy")]
    ])
    await message.reply_text(START_TEXT, reply_markup=keyboard)

@app.on_callback_query(filters.regex("start_deploy"))
async def ask_for_token(client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    
    if len(railway_tokens) == 0:
        await callback_query.message.reply_text("❌ السورس متوقف الى اشعار اخر، تواصل مع المطور للتنصيب المُباشر @CC99V")
        return
        
    user_steps[chat_id] = "waiting_for_token"
    TOKEN_TUTORIAL = (
        "**الخطوة الأولى: إستخراج توكن البوت**\n\n"
        "1. اذهب إلى بوت @BotFather.\n"
        "2. أرسل أمر `/newbot`.\n"
        "3. أرسل اسم للبوت (مثلاً: تايثون).\n"
        "4. أرسل معرف للبوت ينتهي بـ bot (مثلاً: Tython123bot).\n"
        "5. سيقوم البوت بإعطائك رسالة تحتوي على نص طويل، هذا هو التوكن.\n\n"
        "قم بنسخه وإرساله لي هنا الآن:"
    )
    await callback_query.message.reply_text(TOKEN_TUTORIAL)

# ==========================================
# 5. محرك التخاطب (استخراج الجلسة للمستخدم)
# ==========================================
@app.on_message(filters.private & ~filters.command(["start", "admin"]) & ~filters.user(ADMIN_IDS))
async def conversation_handler(client, message: Message):
    chat_id = message.chat.id
    step = user_steps.get(chat_id)

    if not step:
        return

    if step == "waiting_for_token":
        user_data[chat_id] = {"bot_token": message.text}
        user_steps[chat_id] = "waiting_for_phone"
        await message.reply_text("✅ تم حفظ التوكن.\n\nالآن، أرسل رقم هاتفك مع الرمز الدولي (مثال: +96477...):")

    elif step == "waiting_for_phone":
        phone_number = message.text.replace(" ", "")
        user_data[chat_id]["phone"] = phone_number
        msg = await message.reply_text("⏳ جاري طلب كود التحقق من تيليجرام...")
        
        temp_client = Client(f"session_{chat_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await temp_client.connect()
        
        try:
            sent_code = await temp_client.send_code(phone_number)
            user_data[chat_id]["temp_client"] = temp_client
            user_data[chat_id]["phone_code_hash"] = sent_code.phone_code_hash
            user_steps[chat_id] = "waiting_for_code"
            await msg.edit_text(
                "📥 تم إرسال كود التحقق إلى حسابك في تيليجرام.\n\n"
                "**مهم جداً:** لتجنب الحظر، يرجى إرسال الكود مع وضع **مسافات** بين الأرقام.\n"
                "مثال: `4 5 2 4 2`"
            )
        except Exception as e:
            await msg.edit_text(f"❌ حدث خطأ أثناء طلب الكود. تأكد من الرقم.\nالخطأ: {e}")
            user_steps.pop(chat_id, None)

    elif step == "waiting_for_code":
        code = message.text.replace(" ", "")
        temp_client = user_data[chat_id]["temp_client"]
        phone_code_hash = user_data[chat_id]["phone_code_hash"]
        phone = user_data[chat_id]["phone"]
        msg = await message.reply_text("⏳ جاري التحقق من الكود...")
        
        try:
            await temp_client.sign_in(phone, phone_code_hash, code)
            await finalize_session(chat_id, msg)
        except SessionPasswordNeeded:
            user_steps[chat_id] = "waiting_for_password"
            await msg.edit_text("🔐 حسابك محمي بكلمة مرور (التحقق بخطوتين). أرسل كلمة المرور الآن:")
        except PhoneCodeInvalid:
            await msg.edit_text("❌ الكود غير صحيح، أرسله مجدداً (مع مسافات):")

    elif step == "waiting_for_password":
        password = message.text
        temp_client = user_data[chat_id]["temp_client"]
        msg = await message.reply_text("⏳ جاري تسجيل الدخول...")
        
        try:
            await temp_client.check_password(password)
            await finalize_session(chat_id, msg)
        except Exception:
            await msg.edit_text("❌ كلمة المرور غير صحيحة، أرسلها مجدداً:")

async def finalize_session(chat_id, msg: Message):
    temp_client = user_data[chat_id]["temp_client"]
    session_string = await temp_client.export_session_string()
    user_data[chat_id]["session"] = session_string
    await temp_client.disconnect()
    
    user_steps.pop(chat_id, None)
    await msg.edit_text("✅ **تم استخراج الجلسة بنجاح!**\n\nجاري الآن التواصل مع خوادم Railway لبدء التنصيب...")
    
    if len(railway_tokens) > 0:
        active_railway_token = railway_tokens[0] 
        asyncio.create_task(deploy_to_railway(
            chat_id, 
            msg, 
            bot_token=user_data[chat_id]["bot_token"], 
            string_session=session_string,
            railway_token=active_railway_token
        ))
    else:
        await msg.edit_text("❌ نفدت حسابات رايلوي، يرجى مراجعة المطور.")

# ==========================================
# 6. دوال التواصل مع Railway (GraphQL الرسمية والمضبوطة)
# ==========================================
async def railway_api_request(railway_token: str, query: str, variables: dict = None):
    url = "https://backboard.railway.app/graphql/v2"
    headers = {
        "Authorization": f"Bearer {railway_token}",
        "Content-Type": "application/json"
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
        
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                if "errors" in result:
                    raise Exception(result['errors'][0]['message'])
                return result.get("data", {})
            else:
                text = await response.text()
                raise Exception(f"HTTP {response.status}: {text}")

CREATE_PROJECT = """
mutation ProjectCreate($input: ProjectCreateInput!) {
  projectCreate(input: $input) {
    id
    environments {
      edges {
        node {
          id
        }
      }
    }
  }
}
"""

CREATE_GITHUB_SERVICE = """
mutation ServiceCreate($input: ServiceCreateInput!) {
  serviceCreate(input: $input) {
    id
  }
}
"""

# تم ضبط الاستعلام ليتوافق تماماً مع مدخلات Railway الرسمية (VariableCollectionUpsertInput)
UPSERT_VARIABLES = """
mutation VariableCollectionUpsert($input: VariableCollectionUpsertInput!) {
  variableCollectionUpsert(input: $input)
}
"""

async def deploy_to_railway(chat_id, msg: Message, bot_token, string_session, railway_token):
    try:
        await msg.edit_text("⏳ جاري إنشاء مساحة العمل (Project) على حساب Railway...")
        
        # 1. إنشاء المشروع
        project_name = f"Tython-{chat_id}"
        project_data = await railway_api_request(
            railway_token, CREATE_PROJECT, {"input": {"name": project_name}}
        )
        project_id = project_data["projectCreate"]["id"]
        env_id = project_data["projectCreate"]["environments"]["edges"][0]["node"]["id"]
        
        await msg.edit_text(f"✅ تم إنشاء المشروع: `{project_name}`\n🔗 جاري ربط مستودع GitHub...")
        
        # 2. إنشاء الخدمة وربط المستودع
        service_data = await railway_api_request(
            railway_token, CREATE_GITHUB_SERVICE, 
            {"input": {"projectId": project_id, "source": {"repo": USERBOT_REPO}}}
        )
        service_id = service_data["serviceCreate"]["id"]
        
        await msg.edit_text("⚙️ جاري حقن المتغيرات (الجلسة، التوكن، إلخ)...")
        
        # 3. حقن المتغيرات بالطريقة الصحيحة المدعومة من Railway API v2
        variables_to_inject = {
            "SESSION": string_session,
            "BOT_TOKEN": bot_token,
            "API_ID": str(API_ID),
            "API_HASH": API_HASH,
        }
        
        await railway_api_request(
            railway_token, UPSERT_VARIABLES,
            {
                "input": {
                    "projectId": project_id,
                    "environmentId": env_id,
                    "serviceId": service_id,
                    "variables": variables_to_inject
                }
            }
        )
        
        await msg.reply_text(
            "🎉 **تم التنصيب بنجاح!**\n\n"
            "تم سحب السورس وحقن المتغيرات.\n"
            "السورس الآن في مرحلة البناء (Deploying) على Railway، سيعمل اليوزر بوت الخاص بك خلال دقائق معدودة. 🚀"
        )
            
    except Exception as e:
        await msg.reply_text(f"❌ حدث خطأ أثناء التنصيب (Railway API):\n`{e}`\n\nيرجى التواصل مع المطور للتنصيب المُباشر @CC99V")

if __name__ == "__main__":
    print("🚀 Tython Deployer Bot is Running...")
    app.run()
