import telebot
from telebot import types
import requests
import sqlite3
import random
import html
import yt_dlp
import os

# 🔑 البيانات المضمنة
BOT_TOKEN = "8866783597:AAFnY9q0EY9QynpWAPRwE3JgBcS1QSa5ypU"
TMDB_API_KEY = "901e0d7267520343d8141db3d734267f"
ADMIN_ID = 8562738250

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== 🗄️ إدارة قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        first_name TEXT,
                        username TEXT,
                        verified INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
                        channel_username TEXT PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS movie_stats (
                        movie_title TEXT PRIMARY KEY,
                        search_count INTEGER DEFAULT 1)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT)''')
    
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('forced_sub', 'ON')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('welcome_msg', '✨ أهلاً بك في عالم الأفلام والمسلسلات السينمائي!\n\nابحث عن أي فيلم أو مسلسل لمشاهدة التفاصيل والإعلان المباشر.')")
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect('bot_data.db')

def is_verified(user_id):
    conn = get_db_connection()
    res = conn.execute("SELECT verified FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return res and res[0] == 1

def add_user(user_id, first_name, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("INSERT INTO users (user_id, first_name, username, verified) VALUES (?, ?, ?, 0)",
                       (user_id, first_name, username))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def set_verified(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET verified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def log_movie_search(title):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO movie_stats (movie_title, search_count) VALUES (?, 1) ON CONFLICT(movie_title) DO UPDATE SET search_count = search_count + 1", (title,))
    conn.commit()
    conn.close()

def check_subscription(user_id):
    conn = get_db_connection()
    forced_status = conn.execute("SELECT value FROM settings WHERE key = 'forced_sub'").fetchone()[0]
    if forced_status == 'OFF':
        conn.close()
        return True, []
        
    channels = conn.execute("SELECT channel_username FROM channels").fetchall()
    conn.close()
    
    not_subscribed = []
    for ch in channels:
        ch_name = ch[0].replace('@', '')
        try:
            member = bot.get_chat_member(f"@{ch_name}", user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed.append(f"@{ch_name}")
        except Exception:
            pass
            
    return len(not_subscribed) == 0, not_subscribed

# ==================== 🤖 التعامل مع الأوامر ====================
user_captcha = {}

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "مستخدم"
    username = message.from_user.username or "بدون يوزر"

    is_new = add_user(user_id, first_name, username)

    if is_new:
        bot.send_message(
            ADMIN_ID,
            f"🔔 <b>عضو جديد انضم للبوت!</b>\n\n"
            f"👤 <b>الاسم:</b> {html.escape(first_name)}\n"
            f"🆔 <b>الأيدي:</b> <code>{user_id}</code>\n"
            f"🔗 <b>اليوزر:</b> @{username if username != 'بدون يوزر' else 'لا يوجد'}",
            parse_mode="HTML"
        )

    if not is_verified(user_id):
        num1, num2 = random.randint(1, 10), random.randint(1, 10)
        user_captcha[user_id] = num1 + num2
        bot.send_message(
            user_id,
            f"🧠 <b>اختبار الأمان للتحقق:</b>\n\nيرجى حل المعادلة التالية للبدء:\n<code>{num1} + {num2} = ?</code>",
            parse_mode="HTML"
        )
        return

    is_subbed, unsubbed_channels = check_subscription(user_id)
    if not is_subbed:
        markup = types.InlineKeyboardMarkup()
        for ch in unsubbed_channels:
            markup.add(types.InlineKeyboardButton.de_json({
                'text': f"📢 اشترك في {ch}",
                'url': f"https://t.me/{ch.replace('@', '')}",
                'style': 'primary'
            }))
        markup.add(types.InlineKeyboardButton.de_json({
            'text': "🔄 تحقق من الاشتراك",
            'callback_data': 'check_sub',
            'style': 'success'
        }))
        
        bot.send_message(user_id, "⚠️ <b>عذراً عزيزي، يرجى الاشتراك في القنوات التالية لاستخدام البوت:</b>", reply_markup=markup, parse_mode="HTML")
        return

    conn = get_db_connection()
    welcome_text = conn.execute("SELECT value FROM settings WHERE key = 'welcome_msg'").fetchone()[0]
    conn.close()

    markup = types.InlineKeyboardMarkup()
    
    btn_trending = types.InlineKeyboardButton.de_json({'text': '🔥 الأفلام الشائعة اليوم', 'callback_data': 'get_trending', 'style': 'primary'})
    btn_contact = types.InlineKeyboardButton.de_json({'text': '💬 تواصل مع الدعم', 'url': f'tg://user?id={ADMIN_ID}', 'style': 'success'})
    
    markup.row(btn_trending)
    markup.row(btn_contact)
    
    bot.send_message(user_id, f"{welcome_text}\n\n🔍 <b>أرسل اسم أي فيلم أو مسلسل للبحث الفوري:</b>", reply_markup=markup, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.from_user.id in user_captcha)
def handle_captcha(message):
    user_id = message.from_user.id
    try:
        ans = int(message.text.strip())
        if ans == user_captcha[user_id]:
            set_verified(user_id)
            del user_captcha[user_id]
            bot.reply_to(message, "✅ <b>تم التحقق بنجاح!</b> أرسل /start للبدء.", parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ <b>إجابة خاطئة!</b> أرسل /start والمحاولة مجدداً.", parse_mode="HTML")
    except ValueError:
        bot.reply_to(message, "⚠️ يرجى كتابة الأرقام فقط.")

# ==================== 🛠️ لوحة تحكم الأدمن ====================

@bot.message_handler(commands=['add'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = get_db_connection()
    forced_status = conn.execute("SELECT value FROM settings WHERE key = 'forced_sub'").fetchone()[0]
    conn.close()

    status_str = "مفعل 🟢" if forced_status == "ON" else "معطل 🔴"
    sub_style = "success" if forced_status == "ON" else "danger"

    markup = types.InlineKeyboardMarkup()
    
    btn_broadcast = types.InlineKeyboardButton.de_json({'text': '📢 إذاعة للأعضاء', 'callback_data': 'admin_broadcast', 'style': 'primary'})
    btn_stats = types.InlineKeyboardButton.de_json({'text': '📊 الإحصائيات الشاملة', 'callback_data': 'admin_stats', 'style': 'primary'})
    markup.row(btn_broadcast, btn_stats)

    btn_sub = types.InlineKeyboardButton.de_json({'text': f'⚙️ الاشتراك الإجباري ( {status_str} )', 'callback_data': 'toggle_forced_sub', 'style': sub_style})
    markup.row(btn_sub)

    btn_add_ch = types.InlineKeyboardButton.de_json({'text': '➕ إضافة قناة', 'callback_data': 'add_channel', 'style': 'success'})
    btn_del_ch = types.InlineKeyboardButton.de_json({'text': '➖ حذف قناة', 'callback_data': 'del_channel', 'style': 'danger'})
    markup.row(btn_add_ch, btn_del_ch)

    btn_welcome = types.InlineKeyboardButton.de_json({'text': '✏️ تعديل رسالة الترحيب', 'callback_data': 'change_welcome', 'style': 'primary'})
    markup.row(btn_welcome)

    btn_close = types.InlineKeyboardButton.de_json({'text': '❌ إغلاق', 'callback_data': 'close_admin', 'style': 'danger'})
    markup.row(btn_close)

    bot.send_message(message.chat.id, "⚙️ <b>لوحة تحكم أدمن البوت الاحترافية:</b>", reply_markup=markup, parse_mode="HTML")

# ==================== 🔘 معالج الضغط على الأزرار ====================

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    user_id = call.from_user.id

    if call.data == "check_sub":
        is_subbed, _ = check_subscription(user_id)
        if is_subbed:
            bot.answer_callback_query(call.id, "✅ تم التحقق، مرحباً بك!")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            start_cmd(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك في كامل القنوات بعد!", show_alert=True)

    # 🎬 تنزيل المقطع كفيديو وإرساله
    elif call.data.startswith("tr_"):
        _, media_type, item_id = call.data.split("_")
        
        bot.answer_callback_query(call.id, "⏳ جاري تنزيل الفيديو وتجهيزه...")

        trailer_url = f"https://api.themoviedb.org/3/{media_type}/{item_id}/videos"
        videos_res = requests.get(trailer_url, params={'api_key': TMDB_API_KEY, 'language': 'en-US'}).json().get('results', [])
        
        yt_key = None
        for vid in videos_res:
            if vid.get('type') == 'Trailer' and vid.get('site') == 'YouTube':
                yt_key = vid.get('key')
                break
        if not yt_key and videos_res:
            yt_key = videos_res[0].get('key')

        if not yt_key:
            bot.answer_callback_query(call.id, "⚠️ عذراً، لا يوجد فيديو إعلان متوفر لهذا العمل.", show_alert=True)
            return

        url = f"https://www.youtube.com/watch?v={yt_key}"
        filename = f"trailer_{item_id}.mp4"

        ydl_opts = {
            'format': 'b[ext=mp4]/w[ext=mp4]/best',
            'outtmpl': filename,
            'quiet': True,
            'max_filesize': 50 * 1024 * 1024
        }

        try:
            # 1. التنزيل باستخدام yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton.de_json({
                'text': '🔙 العودة لتفاصيل العمل',
                'callback_data': f'info_{media_type}_{item_id}',
                'style': 'primary'
            }))

            # 2. إرسال الفيديو المحمل
            with open(filename, "rb") as video_file:
                bot.send_video(
                    chat_id=call.message.chat.id,
                    video=video_file,
                    caption="🎥 <b>الإعلان الرسمي للعمل</b>",
                    parse_mode="HTML",
                    reply_markup=markup
                )

            # 3. حذف الملف بعد الإرسال
            if os.path.exists(filename):
                os.remove(filename)

        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"⚠️ تعذر تنزيل الفيديو تلقائياً بسبب قيود السيرفر.\nيمكنك مشاهدته مباشرة عبر الرابط:\n{url}"
            )
            if os.path.exists(filename):
                os.remove(filename)

    # 🔙 العودة لتفاصيل الفيلم/المسلسل
    elif call.data.startswith("info_"):
        _, media_type, item_id = call.data.split("_")
        
        info_url = f"https://api.themoviedb.org/3/{media_type}/{item_id}"
        item = requests.get(info_url, params={'api_key': TMDB_API_KEY, 'language': 'ar-SA'}).json()
        
        title = html.escape(item.get('title') or item.get('name', 'غير معروف'))
        release_date = item.get('release_date') or item.get('first_air_date', 'غير معلن')
        rating = item.get('vote_average', 'لا يوجد')
        overview = html.escape(item.get('overview', 'لا يوجد وصف متاح حالياً.'))
        type_label = "الفيلم" if media_type == 'movie' else "المسلسل"

        providers_url = f"https://api.themoviedb.org/3/{media_type}/{item_id}/watch/providers"
        providers_res = requests.get(providers_url, params={'api_key': TMDB_API_KEY}).json().get('results', {})
        region_data = providers_res.get('SA') or providers_res.get('EG') or providers_res.get('AE') or {}
        platforms = [p.get('provider_name') for p in region_data.get('flatrate', [])]
        providers_str = "، ".join(platforms) if platforms else "غير محدد / بحث منصات"

        caption = (
            f"🎬 <b>{title}</b> ({type_label})\n\n"
            f"📅 <b>تاريخ الإنتاج:</b> {release_date}\n"
            f"⭐ <b>التقييم:</b> {rating} / 10\n"
            f"📺 <b>المنصات المتاحة:</b> {providers_str}\n\n"
            f"📝 <b>القصة:</b>\n{overview}"
        )

        item_link = f"https://www.themoviedb.org/{media_type}/{item_id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton.de_json({
            'text': f'🎬 تفاصيل أكثر عن {type_label}',
            'url': item_link,
            'style': 'primary'
        }))
        markup.add(types.InlineKeyboardButton.de_json({
            'text': f'▶️ تشغيل فيديو الإعلان',
            'callback_data': f'tr_{media_type}_{item_id}',
            'style': 'danger'
        }))

        try:
            if call.message.content_type == 'photo':
                bot.edit_message_caption(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=markup
                )
        except Exception:
            pass

    # 🔥 قسم العروض الشائعة (Trending)
    elif call.data == "get_trending":
        trending_url = f"https://api.themoviedb.org/3/trending/movie/day"
        res = requests.get(trending_url, params={'api_key': TMDB_API_KEY, 'language': 'ar-SA'}).json().get('results', [])[:5]
        
        msg_text = "🔥 <b>أحدث الأفلام الأكثر شيوعاً اليوم:</b>\n\n"
        markup = types.InlineKeyboardMarkup()
        
        for idx, item in enumerate(res, 1):
            title = item.get('title', 'غير معروف')
            rating = item.get('vote_average', 'N/A')
            msg_text += f"{idx}. <b>{html.escape(title)}</b> ⭐ <code>{rating}</code>\n"
            markup.add(types.InlineKeyboardButton.de_json({
                'text': f'🎬 {title}',
                'callback_data': f'info_movie_{item.get("id")}',
                'style': 'primary'
            }))
            
        bot.send_message(call.message.chat.id, msg_text, reply_markup=markup, parse_mode="HTML")

    # أزرار تحكم الأدمن
    if user_id == ADMIN_ID:
        if call.data == "close_admin":
            bot.delete_message(call.message.chat.id, call.message.message_id)

        elif call.data == "toggle_forced_sub":
            conn = get_db_connection()
            curr = conn.execute("SELECT value FROM settings WHERE key = 'forced_sub'").fetchone()[0]
            new_val = "OFF" if curr == "ON" else "ON"
            conn.execute("UPDATE settings SET value = ? WHERE key = 'forced_sub'", (new_val,))
            conn.commit()
            conn.close()
            bot.answer_callback_query(call.id, f"تم تغيير حالة الاشتراك إلى {new_val}")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            admin_panel(call.message)

        elif call.data == "admin_stats":
            conn = get_db_connection()
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            top_movies = conn.execute("SELECT movie_title, search_count FROM movie_stats ORDER BY search_count DESC LIMIT 5").fetchall()
            conn.close()

            movies_text = "\n".join([f"• {m[0]}: ({m[1]} مرة)" for m in top_movies]) if top_movies else "لا توجد عمليات بحث بعد."
            
            stats_msg = (
                f"📊 <b>إحصائيات البوت الشاملة:</b>\n\n"
                f"👥 <b>إجمالي المشتركين:</b> <code>{total_users}</code>\n\n"
                f"🎬 <b>الأعمال الأكثر طلباً:</b>\n{movies_text}"
            )
            bot.send_message(call.message.chat.id, stats_msg, parse_mode="HTML")

        elif call.data == "admin_broadcast":
            msg = bot.send_message(call.message.chat.id, "ارسل النص أو الرسالة المُراد إذاعتها للجميع:")
            bot.register_next_step_handler(msg, process_broadcast)

        elif call.data == "add_channel":
            msg = bot.send_message(call.message.chat.id, "أرسل معرف القناة (مثال: `@channel_name`):")
            bot.register_next_step_handler(msg, process_add_channel)

        elif call.data == "change_welcome":
            msg = bot.send_message(call.message.chat.id, "أرسل نص رسالة الترحيب الجديدة:")
            bot.register_next_step_handler(msg, process_change_welcome)

def process_broadcast(message):
    conn = get_db_connection()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()

    success, failed = 0, 0
    bot.send_message(message.chat.id, "⏳ جاري تنفيذ الإذاعة...")
    for user in users:
        try:
            bot.copy_message(chat_id=user[0], from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
        except Exception:
            failed += 1

    bot.send_message(message.chat.id, f"✅ <b>اكتمال الإذاعة!</b>\n\n🟢 تم التسليم: {success}\n🔴 تعذر التسليم: {failed}", parse_mode="HTML")

def process_add_channel(message):
    ch_name = message.text.strip()
    if not ch_name.startswith("@"):
        ch_name = "@" + ch_name
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO channels (channel_username) VALUES (?)", (ch_name,))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"✅ تم حفظ القناة {ch_name} بنجاح.")

def process_change_welcome(message):
    new_msg = message.text.strip()
    conn = get_db_connection()
    conn.execute("UPDATE settings SET value = ? WHERE key = 'welcome_msg'", (new_msg,))
    conn.commit()
    conn.close()
    bot.reply_to(message, "✅ تم حفظ التحديثات لرسالة الترحيب!")

# ==================== 🎬 محرك البحث والنتائج ====================

@bot.message_handler(func=lambda message: True)
def search_movie(message):
    user_id = message.from_user.id

    if not is_verified(user_id):
        bot.reply_to(message, "⚠️ يرجى استخدام الأمر /start لتأكيد الحساب.")
        return

    is_subbed, _ = check_subscription(user_id)
    if not is_subbed:
        start_cmd(message)
        return

    query = message.text.strip()
    
    search_url = "https://api.themoviedb.org/3/search/multi"
    search_params = {'api_key': TMDB_API_KEY, 'query': query, 'language': 'ar-SA'}
    
    try:
        response = requests.get(search_url, params=search_params).json()
        results = response.get('results', [])
        
        if not results:
            bot.reply_to(message, "❌ لم يتم العثور على أي نتائج مطابقة.")
            return

        item = results[0]
        media_type = item.get('media_type', 'movie')
        if media_type not in ['movie', 'tv']:
            media_type = 'movie'

        item_id = item.get('id')
        title = html.escape(item.get('title') or item.get('name', 'غير معروف'))
        release_date = item.get('release_date') or item.get('first_air_date', 'غير معلن')
        rating = item.get('vote_average', 'لا يوجد')
        overview = html.escape(item.get('overview', 'لا يوجد وصف متاح حالياً.'))
        poster_path = item.get('poster_path')

        type_label = "الفيلم" if media_type == 'movie' else "المسلسل"

        log_movie_search(title)

        providers_url = f"https://api.themoviedb.org/3/{media_type}/{item_id}/watch/providers"
        providers_res = requests.get(providers_url, params={'api_key': TMDB_API_KEY}).json().get('results', {})
        region_data = providers_res.get('SA') or providers_res.get('EG') or providers_res.get('AE') or {}
        platforms = [p.get('provider_name') for p in region_data.get('flatrate', [])]
        providers_str = "، ".join(platforms) if platforms else "غير محدد / بحث منصات"

        caption = (
            f"🎬 <b>{title}</b> ({type_label})\n\n"
            f"📅 <b>تاريخ الإنتاج:</b> {release_date}\n"
            f"⭐ <b>التقييم:</b> {rating} / 10\n"
            f"📺 <b>المنصات المتاحة:</b> {providers_str}\n\n"
            f"📝 <b>القصة:</b>\n{overview}"
        )

        item_link = f"https://www.themoviedb.org/{media_type}/{item_id}"
        markup = types.InlineKeyboardMarkup()
        
        markup.add(types.InlineKeyboardButton.de_json({
            'text': f'🎬 تفاصيل أكثر عن {type_label}',
            'url': item_link,
            'style': 'primary'
        }))

        markup.add(types.InlineKeyboardButton.de_json({
            'text': f'▶️ تشغيل فيديو الإعلان',
            'callback_data': f'tr_{media_type}_{item_id}',
            'style': 'danger'
        }))

        if poster_path:
            bot.send_photo(message.chat.id, photo=f"https://image.tmdb.org/t/p/w500{poster_path}", caption=caption, parse_mode="HTML", reply_markup=markup)
        else:
            bot.reply_to(message, caption, parse_mode="HTML", reply_markup=markup)

    except Exception:
        bot.reply_to(message, "⚠️ حدث خطأ غير متوقع أثناء معالجة الطلب.")

if __name__ == '__main__':
    print("🚀 البوت جاهز ويعمل بكفاءة عالية...")
    bot.infinity_polling()