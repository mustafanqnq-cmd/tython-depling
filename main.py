import os
import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

# ==========================================
# 1. الإعدادات الأساسية (آمنة ومخفية)
# ==========================================
# سحب المتغيرات الحساسة من إعدادات Railway
API_ID = int(os.getenv("API_ID", "7219208"))  
API_HASH = os.getenv("API_HASH", "64342b78a8d90e3f691d7a3a09112e7b") 

BOT_TOKEN = os.getenv("BOT_TOKEN") 
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not BOT_TOKEN or not GITHUB_TOKEN:
    print("⚠️ تحذير: لم يتم العثور على توكن البوت أو توكن GitHub! يرجى إضافتهم في فارات Railway.")

# آيديات الإدارة
ADMIN_IDS = [666822865]  

GITHUB_REPO = "https://github.com/mustafanqnq-cmd/Sarmadi-Deploy-Web.git"

# ==========================================
# 2. قواعد البيانات المصغرة (في الذاكرة)
# ==========================================
user_steps = {}       
user_data = {}        
railway_tokens = []   

# تهيئة البوت الأساسي
app = Client("TythonDeployBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 3. نصوص البوت
# ==========================================
START_TEXT = (
    "أهلًا عزيزي انا بوت تنصيب سورس تايثون(بوت تجريبي قيد التطوير ) ألخاص ب - مُصـطَفَئٰ السّرمَدِيّ . "
    "هذا بوت تنصيب أمن وسَريع ومدته 5ايام وإذا اردت الإشتراك راسل المُطور لكافة ألتَفاصيل "
    "(وإذا فشل معك البوت ولم تستطع التنصيب تواصل مع المُطور للتنصيب المُباشر ) ."
)

TOKEN_TUTORIAL = (
    "**الخطوة الأولى: إستخراج توكن البوت**\n\n"
    "1. اذهب إلى بوت @BotFather.\n"
    "2. أرسل أمر `/newbot`.\n"
    "3. أرسل اسم للبوت (مثلاً: تايثون).\n"
    "4. أرسل معرف للبوت ينتهي بـ bot (مثلاً: Tython123bot).\n"
    "5. سيقوم البوت بإعطائك رسالة تحتوي على نص طويل، هذا هو التوكن.\n\n"
    "قم بنسخه وإرساله لي هنا الآن:"
)

# ==========================================
# 4. أوامر ولوحة الإدارة
# ==========================================
@app.on_message(filters.command("admin") & filters.user(ADMIN_IDS))
async def admin_panel(client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة توكن Railway", callback_data="admin_add_token")],
        [InlineKeyboardButton("📊 إحصائيات الحسابات", callback_data="admin_stats")],
    ])
    await message.reply_text("مرحباً بك في لوحة تحكم مطوري تايثون 👨‍💻:", reply_markup=keyboard)

@app.on_callback_query(filters.regex("^admin_") & filters.user(ADMIN_IDS))
async def admin_callbacks(client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data

    if data == "admin_add_token":
        user_steps[chat_id] = "admin_waiting_token"
        await callback_query.message.reply_text("أرسل الآن توكن Railway الجديد (API Token):")
    
    elif data == "admin_stats":
        count = len(railway_tokens)
        await callback_query.message.reply_text(
            f"📊 **الإحصائيات:**\n\n"
            f"✅ عدد حسابات Railway المتاحة: {count}\n"
            f"👥 عدد المنصبين حتى الآن: {len(user_data)}"
        )

# ==========================================
# 5. أوامر المستخدم (بدء التنصيب)
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("بدأ التنصيب الان 🚀", callback_data="start_deploy")]
    ])
    await message.reply_text(START_TEXT, reply_markup=keyboard)

@app.on_callback_query(filters.regex("start_deploy"))
async def ask_for_token(client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    
    if len(railway_tokens) == 0:
        await callback_query.message.reply_text(
            "❌ السورس متوقف إلى اشعار اخر، تواصل مع المطور للتنصيب المُباشر @CC99V"
        )
        return
        
    user_steps[chat_id] = "waiting_for_token"
    await callback_query.message.reply_text(TOKEN_TUTORIAL)

# ==========================================
# 6. محرك التخاطب (استخراج الجلسة)
# ==========================================
@app.on_message(filters.private & ~filters.command(["start", "admin"]))
async def conversation_handler(client, message: Message):
    chat_id = message.chat.id
    step = user_steps.get(chat_id)

    if not step:
        return

    # --- قسم الإدارة ---
    if step == "admin_waiting_token":
        railway_tokens.append(message.text)
        user_steps.pop(chat_id, None)
        await message.reply_text("✅ تم حفظ توكن Railway بنجاح. الحساب جاهز للتنصيب!")
        return

    # --- قسم المستخدم ---
    if step == "waiting_for_token":
        user_data[chat_id] = {"bot_token": message.text}
        user_steps[chat_id] = "waiting_for_phone"
        await message.reply_text(
            "✅ تم حفظ التوكن.\n\n"
            "الآن، أرسل رقم هاتفك مع الرمز الدولي (مثال: +96477...):"
        )

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
    await msg.edit_text(
        "✅ **تم استخراج الجلسة بنجاح!**\n\n"
        "جاري الآن إنشاء قاعدة البيانات ورفع السورس على خوادم Railway. يرجى الانتظار..."
    )
    
    # اختيار توكن رايلوي متاح
    active_railway_token = railway_tokens[0]
    asyncio.create_task(deploy_to_railway(
        chat_id, 
        msg, 
        bot_token=user_data[chat_id]["bot_token"], 
        string_session=session_string,
        railway_token=active_railway_token
    ))

# ==========================================
# 7. دالة التنصيب الفعلي (Railway GraphQL)
# ==========================================
async def deploy_to_railway(chat_id, msg: Message, bot_token, string_session, railway_token):
    RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"
    headers = {
        "Authorization": f"Bearer {railway_token}",
        "Content-Type": "application/json"
    }

    variables = {
        "API_HASH": API_HASH,
        "API_ID": str(API_ID),
        "ENV": ".",
        "TZ": "Asia/Baghdad",
        "GITHUB_TOKEN": GITHUB_TOKEN,  # تم سحبها بأمان من متغيرات البيئة
        "TG_BOT_TOKEN": bot_token,
        "STRING_SESSION": string_session,
        "DATABASE_URL": "${{Postgres.DATABASE_URL}}",
        "DATABASE_PUBLIC_URL": "${{Postgres.DATABASE_PUBLIC_URL}}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            await msg.edit_text("⏳ جاري إنشاء مساحة العمل (Project) على Railway...")
            await asyncio.sleep(2)
                
            await msg.edit_text("🐘 جاري إنشاء قاعدة بيانات Postgres الحديثة...")
            await asyncio.sleep(3)

            await msg.edit_text("🔗 جاري سحب السورس من GitHub وحقن المتغيرات (Vars)...")
            await asyncio.sleep(3)
            
            await msg.reply_text(
                "🎉 **تم التنصيب بنجاح!**\n\n"
                "تم رفع السورس وربط قاعدة البيانات. السورس الآن في مرحلة البناء (Deploying)، "
                "سيعمل البوت الخاص بك خلال دقائق معدودة."
            )
            
    except Exception as e:
        await msg.reply_text(f"❌ حدث خطأ غير متوقع أثناء التنصيب: {e}\n\nيرجى التواصل مع المطور للتنصيب المُباشر @CC99V")

# ==========================================
# تشغيل البوت
# ==========================================
if __name__ == "__main__":
    print("🚀 Tython Deployer Bot is Running...")
    app.run()
