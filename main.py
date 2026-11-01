import asyncio
import os
import re
import sqlite3
import json
import time
import random
from difflib import SequenceMatcher
from datetime import datetime, timezone, timedelta
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import InputMediaPhoto
from html import escape
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiohttp import web
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv(Path(__file__).with_name('.env'))
TOKEN = os.getenv('BOT_TOKEN', '').strip()
if not TOKEN:
    raise RuntimeError('Укажите BOT_TOKEN в .env рядом с bot.py')
REQUESTS_CHAT_ID = int(os.getenv('REQUESTS_CHAT_ID') or '0')
LISTINGS_CHAT_ID = int(os.getenv('LISTINGS_CHAT_ID') or '0')
CONTACT_1 = os.getenv('CONTACT_1', '+998 91 752 10 06')
CONTACT_2 = os.getenv('CONTACT_2', '+998 90 685 10 06')
CONTACT_LINK = os.getenv('CONTACT_LINK', 'https://t.me/KEY_HOUSE_TASHKENT')
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').replace(';', ',').split(',') if x.strip().isdigit()}
DB = Path(os.getenv('KEY_HOUSE_DB_PATH', str(Path(__file__).with_name('key_house.sqlite3'))))
DB.parent.mkdir(parents=True,exist_ok=True)
bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
class SQLiteFSMStorage(BaseStorage):
    # Persistent per-user FSM. Single bot process only.
    async def set_state(self,key,state=None):
        value=state.state if hasattr(state,'state') else state
        with sqlite3.connect(DB) as c:
            c.execute('INSERT OR IGNORE INTO persistent_fsm(bot_id,chat_id,user_id,data) VALUES(?,?,?,?)',
                      (key.bot_id,key.chat_id,key.user_id,'{}'))
            c.execute('UPDATE persistent_fsm SET state=?,updated_at=?,reminded=0 WHERE bot_id=? AND chat_id=? AND user_id=?',
                      (value,int(time.time()),key.bot_id,key.chat_id,key.user_id))
    async def get_state(self,key):
        with sqlite3.connect(DB) as c:
            r=c.execute('SELECT state FROM persistent_fsm WHERE bot_id=? AND chat_id=? AND user_id=?',
                        (key.bot_id,key.chat_id,key.user_id)).fetchone()
        return r[0] if r else None
    async def set_data(self,key,data):
        with sqlite3.connect(DB) as c:
            c.execute('INSERT OR IGNORE INTO persistent_fsm(bot_id,chat_id,user_id,data) VALUES(?,?,?,?)',
                      (key.bot_id,key.chat_id,key.user_id,'{}'))
            c.execute('UPDATE persistent_fsm SET data=?,updated_at=?,reminded=0 WHERE bot_id=? AND chat_id=? AND user_id=?',
                      (json.dumps(data,ensure_ascii=False),int(time.time()),key.bot_id,key.chat_id,key.user_id))
    async def get_data(self,key):
        with sqlite3.connect(DB) as c:
            r=c.execute('SELECT data FROM persistent_fsm WHERE bot_id=? AND chat_id=? AND user_id=?',
                        (key.bot_id,key.chat_id,key.user_id)).fetchone()
        return json.loads(r[0]) if r and r[0] else {}
    async def close(self):pass

dp = Dispatcher(storage=SQLiteFSMStorage())

WORDS = {
 'ru': {'buy':'🏠 Купить','rent':'🔑 Арендовать','sellrent':'📤 Продать / сдать','sell':'🏷️ Продать','give':'🏡 Сдать','all':'💛 Смотреть объявления','offer':'📩 Предложение','more':'🖤 Ещё','rules':'📜 Правила пользования','about':'👑 О нас','agents':'🤝 Для риэлторов','owners':'🏡 Для собственников','coop':'🤝 Сотрудничество','new':'🏗 ✨ Новостройка','secondary':'🏘 💛 Вторичное жильё','any':'⚪ Непринципиально','back':'↩️ Назад','backlist':'⬅️ Назад к объявлениям','menu':'🏠 Главное меню','done':'✅ Готово','skip':'⏭ Пропустить','view':'📅 Запись на просмотр','phone':'📱 Отправить мой номер','allcity':'📍 Весь Ташкент','manual':'✍️ Указать адрес вручную','nobudget':'🪙 Пока без бюджета','plus':'➕ Плюсовой вариант','next':'➡️ Следующее объявление','refresh':'🔄 Обновить объявления','profile':'👤 Мой профиль','interest':'💛 Заинтересовал объект','history':'📋 Мои заявки','selection':'📝 Заявка на подбор','stock':'🏘 Из наличия','confirm':'✅ Подтвердить и отправить','cancel':'❌ Отменить','edit':'✏️ Изменить'},
 'uz': {'buy':'🏠 Sotib olish','rent':'🔑 Ijaraga olish','sellrent':'📤 Sotish / ijaraga berish','sell':'🏷️ Sotish','give':'🏡 Ijaraga berish','all':'💛 E’lonlarni ko‘rish','offer':'📩 Taklif yuborish','more':'🖤 Yana','rules':'📜 Foydalanish qoidalari','about':'👑 Biz haqimizda','agents':'🤝 Rieltorlar uchun','owners':'🏡 Mulk egalari uchun','coop':'🤝 Hamkorlik','new':'🏗 ✨ Yangi qurilish','secondary':'🏘 💛 Ikkilamchi uy-joy','any':'⚪ Muhim emas','back':'↩️ Orqaga','backlist':'⬅️ E’lonlarga qaytish','menu':'🏠 Bosh menyu','done':'✅ Tayyor','skip':'⏭ O‘tkazib yuborish','view':'📅 Ko‘rishga yozilish','phone':'📱 Raqamimni yuborish','allcity':'📍 Butun Toshkent','manual':'✍️ Manzilni yozish','nobudget':'🪙 Byudjet hali yo‘q','plus':'➕ Plyusli variant','next':'➡️ Keyingi e’lon','refresh':'🔄 E’lonlarni yangilash','profile':'👤 Profilim','interest':'💛 Obyektga qiziqdim','history':'📋 Arizalarim','selection':'📝 Uy tanlash arizasi','stock':'🏘 Mavjud obyektlar','confirm':'✅ Tasdiqlash va yuborish','cancel':'❌ Bekor qilish','edit':'✏️ O‘zgartirish'}
}
DISTRICTS = [('Бектемирский','Bektemir'),('Мирабадский','Mirobod'),('Мирзо-Улугбекский','Mirzo Ulug‘bek'),('Алмазарский','Olmazor'),('Сергелийский','Sergeli'),('Учтепинский','Uchtepa'),('Чиланзарский','Chilonzor'),('Шайхантахурский','Shayxontohur'),('Юнусабадский','Yunusobod'),('Яккасарайский','Yakkasaroy'),('Яшнабадский','Yashnobod'),('Янгихаётский','Yangihayot')]

def tr(lang, ru, uz): return ru if lang == 'ru' else uz
def w(lang, key): return WORDS[lang][key]
# Все кнопки используют стандартный нейтральный стиль Telegram.
# Чёрно-золотые акценты передаются через эмодзи и форматирование сообщений.
ACCENT = '🖤 ✦ 💛'

def styled_button(text, request_contact=False):
    """Единый нейтральный стиль кнопок Telegram без синего акцента."""
    return KeyboardButton(text=text, request_contact=True) if request_contact else KeyboardButton(text=text)

def kb(rows):
    return ReplyKeyboardMarkup(keyboard=[[styled_button(t) for t in row] for row in rows], resize_keyboard=True)
def menu(lang):
    # Компактное главное меню: две кнопки в строке, единый стиль.
    return kb([[w(lang,'buy'), w(lang,'rent')],
               [w(lang,'sellrent'), w(lang,'all')],
               [w(lang,'offer'), w(lang,'more')],
               [w(lang,'refresh'),w(lang,'profile')]])
def back_kb(lang, listing=False): return kb([[w(lang,'backlist') if listing else w(lang,'back')],[w(lang,'menu')]])
def types_kb(lang): return kb([[w(lang,'new'),w(lang,'secondary')],[w(lang,'any')],[w(lang,'back')],[w(lang,'menu')]])
def district_kb(lang):
    names = ['📍 '+(a if lang=='ru' else b) for a,b in DISTRICTS]
    return kb([names[i:i+2] for i in range(0,len(names),2)]+[[w(lang,'allcity'),w(lang,'any')],[w(lang,'manual')],[w(lang,'back')],[w(lang,'menu')]])
def rooms_kb(lang): return kb([['1','2'],['3','4+'],[w(lang,'any')],[w(lang,'back')],[w(lang,'menu')]])
def phone_kb(lang): return ReplyKeyboardMarkup(keyboard=[[styled_button(w(lang,'phone'),request_contact=True)],[KeyboardButton(text=w(lang,'back'))],[KeyboardButton(text=w(lang,'menu'))]],resize_keyboard=True)

def init_db():
    with sqlite3.connect(DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS listings (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, category TEXT NOT NULL, UNIQUE(chat_id,message_id))')
        cols = {r[1] for r in c.execute('PRAGMA table_info(listings)')}
        for name in ('code','housing'):
            if name not in cols: c.execute(f'ALTER TABLE listings ADD COLUMN {name} TEXT')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS listing_code_unique ON listings(code)')
        c.execute('CREATE TABLE IF NOT EXISTS listing_media (chat_id INTEGER, message_id INTEGER PRIMARY KEY, media_group_id TEXT, file_id TEXT, caption TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS listing_meta (message_id INTEGER PRIMARY KEY, rooms TEXT, district TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, lang TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS rule_acceptances (user_id INTEGER PRIMARY KEY, version INTEGER NOT NULL, accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS profiles (user_id INTEGER PRIMARY KEY, name TEXT, phone TEXT, last_search TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, kind TEXT NOT NULL, code TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, repeated INTEGER DEFAULT 0)')
        c.execute('CREATE INDEX IF NOT EXISTS applications_user ON applications(user_id,id DESC)')
        c.execute('CREATE TABLE IF NOT EXISTS code_history (code TEXT PRIMARY KEY)')
        c.execute('CREATE TABLE IF NOT EXISTS admin_media (code TEXT PRIMARY KEY, file_ids TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS admin_overrides (code TEXT PRIMARY KEY, description TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS admin_reasons (code TEXT PRIMARY KEY, reason TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS admin_deleted_posts (code TEXT PRIMARY KEY, chat_id INTEGER, message_ids TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS persistent_fsm (bot_id INTEGER,chat_id INTEGER,user_id INTEGER,state TEXT,data TEXT NOT NULL DEFAULT \'{}\',updated_at INTEGER NOT NULL DEFAULT 0,reminded INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(bot_id,chat_id,user_id))')
        c.execute('CREATE TABLE IF NOT EXISTS duplicate_reviews (new_code TEXT PRIMARY KEY, existing_code TEXT NOT NULL, state TEXT NOT NULL DEFAULT \'pending\')')
        c.execute('CREATE TABLE IF NOT EXISTS admin_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, action TEXT, code TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')

        c.execute('INSERT OR IGNORE INTO code_history(code) SELECT code FROM listings WHERE code IS NOT NULL')
        c.execute('CREATE TABLE IF NOT EXISTS delivery_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, code TEXT, payload TEXT NOT NULL, photos TEXT, state TEXT NOT NULL DEFAULT \'pending\', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        qcols={r[1] for r in c.execute('PRAGMA table_info(delivery_queue)')}
        for col,definition in [('attempts','INTEGER NOT NULL DEFAULT 0'),('next_attempt','INTEGER NOT NULL DEFAULT 0'),('created_ts','INTEGER NOT NULL DEFAULT 0'),('alerted','INTEGER NOT NULL DEFAULT 0'),('telegram_message_id','INTEGER'),('last_error','TEXT')]:
            if col not in qcols:c.execute(f'ALTER TABLE delivery_queue ADD COLUMN {col} {definition}')
        c.execute('CREATE INDEX IF NOT EXISTS queue_ready ON delivery_queue(state,next_attempt)')
        if 'photo_progress' not in qcols:c.execute('ALTER TABLE delivery_queue ADD COLUMN photo_progress INTEGER NOT NULL DEFAULT 0')

        if 'status' not in cols: c.execute("ALTER TABLE listings ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        c.execute("UPDATE listings SET status='unavailable' WHERE status IN ('sold','rented','hidden')")
        c.execute("UPDATE listings SET status='active' WHERE status IS NULL")
        for (lid,) in c.execute('SELECT id FROM listings WHERE code IS NULL ORDER BY id').fetchall():
            used = {r[0] for r in c.execute('SELECT code FROM code_history')}
            code = next((str(n) for n in range(10,1000) if str(n) not in used), None)
            if code:
                c.execute('UPDATE listings SET code=? WHERE id=?',(code,lid))
                c.execute('INSERT OR IGNORE INTO code_history(code) VALUES(?)',(code,))

def lang_for(user_id):
    with sqlite3.connect(DB) as c:
        r = c.execute('SELECT lang FROM users WHERE user_id=?',(user_id,)).fetchone()
    return r[0] if r else 'ru'
def save_lang(uid, lang):
    with sqlite3.connect(DB) as c: c.execute('INSERT OR REPLACE INTO users VALUES (?,?)',(uid,lang))
def classify(text):
    s=(text or '').lower()
    if any(x in s for x in ('аренд','сдаю','сдаёт','сдает','посуточно','ijara','rent')): return 'rent'
    if any(x in s for x in ('прода','продам','купить','sotil','sotuv','sale')): return 'buy'
    return 'other'
def housing(text):
    s=(text or '').lower()
    if any(x in s for x in ('новострой','новостр','yangi quril','yangi uy')): return 'new'
    if any(x in s for x in ('вторич','ikkilamchi')): return 'secondary'
    return 'unknown'
def parse_rooms(text):
    m=re.search(r'(?<!\d)([1-9])\s*[- ]?\s*(?:комн|к\.|xonali|xona)',(text or '').lower())
    if not m: return None
    return '4+' if int(m.group(1))>=4 else m.group(1)

def parse_district(text):
    t=(text or '').lower().replace('‘',"'")
    for ru,uz in DISTRICTS:
        for stem in (ru.lower().replace('ский','').replace('ий',''),uz.lower().replace('‘',"'")):
            if stem and stem in t:return ru
    return None

def store_listing(chat_id,message_id,text,media_group_id=None,file_id=None):
    with sqlite3.connect(DB) as c:
        if file_id:
            c.execute('INSERT OR REPLACE INTO listing_media VALUES(?,?,?,?,?)',(chat_id,message_id,str(media_group_id) if media_group_id else None,file_id,text))
        if media_group_id:
            existing=c.execute('SELECT message_id FROM listing_media WHERE chat_id=? AND media_group_id=? ORDER BY message_id LIMIT 1',(chat_id,str(media_group_id))).fetchone()
            root=existing[0] if existing else message_id
            # Album messages are grouped under one listing; description may arrive in any photo.
            row=c.execute('SELECT message_id FROM listings WHERE chat_id=? AND message_id IN (SELECT message_id FROM listing_media WHERE chat_id=? AND media_group_id=?)',(chat_id,chat_id,str(media_group_id))).fetchone()
            if row:root=row[0]
        else:root=message_id
        description=text or ''
        if media_group_id:
            descriptions=c.execute('SELECT caption FROM listing_media WHERE chat_id=? AND media_group_id=? AND caption != ""',(chat_id,str(media_group_id))).fetchall()
            if descriptions:description=max((x[0] for x in descriptions),key=len)
        exists=c.execute('SELECT id FROM listings WHERE chat_id=? AND message_id=?',(chat_id,root)).fetchone()
        if not exists:
            used={r[0] for r in c.execute('SELECT code FROM code_history')}
            code=next((str(n) for n in range(10,1000) if str(n) not in used),None)
            c.execute('INSERT INTO listings(chat_id,message_id,category,code,housing) VALUES(?,?,?,?,?)',(chat_id,root,classify(description),code,housing(description)))
            if code:c.execute('INSERT OR IGNORE INTO code_history(code) VALUES(?)',(code,))
        elif description:
            c.execute('UPDATE listings SET category=?,housing=? WHERE chat_id=? AND message_id=?',(classify(description),housing(description),chat_id,root))
        if description:c.execute('INSERT OR REPLACE INTO listing_meta VALUES(?,?,?)',(root,parse_rooms(description),parse_district(description)))

def listings(category='all',building='any',rooms='any',district='any',budget='—'):
    with sqlite3.connect(DB) as c:
        q='SELECT l.chat_id,l.message_id,l.code FROM listings l LEFT JOIN listing_meta m ON m.message_id=l.message_id WHERE l.status=\'active\'';p=[]
        if category!='all':q+=' AND l.category=?';p.append(category)
        if building!='any':q+=' AND l.housing=?';p.append(building)
        if rooms!='any':q+=' AND m.rooms=?';p.append(rooms)
        if district!='any':q+=' AND m.district=?';p.append(district)
        rows=c.execute(q+' ORDER BY l.id DESC',p).fetchall()
        return [r for r in rows if listing_has_photo(r[0],r[1]) and (not budget_limits(budget) or price_match(r[0],r[1],budget) != 'exclude')]

def ad_buttons(lang,index,total,code):
    rows=[]
    if index+1<total:rows.append([InlineKeyboardButton(text=w(lang,'next'),callback_data='nextad')])
    rows.append([InlineKeyboardButton(text=w(lang,'interest'),callback_data='interest:'+str(code))])
    rows.append([InlineKeyboardButton(text=tr(lang,'📅 Отправить заявку на просмотр','📅 Ko‘rishga ariza yuborish'),callback_data='view:'+str(code))])
    rows.append([InlineKeyboardButton(text=tr(lang,'📞 Связаться с нами','📞 Biz bilan bog‘lanish'),callback_data='contactad')])
    rows.append([InlineKeyboardButton(text=tr(lang,'⬅️ Назад','⬅️ Orqaga'),callback_data='prevad'),InlineKeyboardButton(text=w(lang,'refresh'),callback_data='refreshads')])
    rows.append([InlineKeyboardButton(text=w(lang,'menu'),callback_data='homead')])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def show_next_ad(message,state,lang):
    data=await state.get_data();items=listings(data.get('category','all'),data.get('building','any'),data.get('rooms','any'),data.get('district','any'),data.get('budget','—'))
    index=data.get('ad_index',0)
    if index>=len(items):
        await message.answer(tr(lang,'🏠 Больше объявлений по выбранным критериям нет.','🏠 Tanlangan mezonlar bo‘yicha boshqa e’lon yo‘q.'),reply_markup=kb([[w(lang,'backlist')],[w(lang,'menu')]]));return
    chat_id,msg_id,code=items[index]
    await state.update_data(ad_index=index+1)
    with sqlite3.connect(DB) as c:
        root=c.execute('SELECT media_group_id,caption,file_id FROM listing_media WHERE message_id=?',(msg_id,)).fetchone()
        override_media=c.execute('SELECT file_ids FROM admin_media WHERE code=?',(str(code),)).fetchone()
        if root and root[0]:
            media=c.execute('SELECT file_id,caption FROM listing_media WHERE chat_id=? AND media_group_id=? ORDER BY message_id',(chat_id,root[0])).fetchall()
        elif root:media=[(root[2],root[1])]
        else:media=[]
        if override_media:media=[(fid,'') for fid in json.loads(override_media[0])]
    description=listing_description(chat_id,msg_id)
    match=price_match(chat_id,msg_id,data.get('budget','—'))
    try:
        if len(media)>1:
            for start in range(0,len(media),10):
                group=media[start:start+10]
                if len(group)>1:await bot.send_media_group(message.chat.id,[InputMediaPhoto(media=fid) for fid,_ in group])
                else:await bot.send_photo(message.chat.id,group[0][0])
        elif len(media)==1:await bot.send_photo(message.chat.id,media[0][0])
        else:
            await bot.copy_message(message.chat.id,chat_id,msg_id)
        if not description:
            # Text-only posts and captions not yet captured in local DB.
            description=tr(lang,'Описание объекта смотрите в сообщении выше.','Obyekt tavsifi yuqoridagi xabarda.')
        await message.answer(f'🖤 ✦ <b>KEY HOUSE | TASHKENT</b> ✦ 💛\n\n{escape(description)[:3300]}\n\n{tr(lang,'💛 Немного выше бюджета','💛 Byudjetdan biroz yuqori') if match=='slightly_above' else tr(lang,'🔎 Характеристики уточняются','🔎 Ma’lumot aniqlanmoqda') if match=='possible' else ''}\n\n🔑 <b>№{escape(str(code or "—"))}</b>\n📑 {index+1}/{len(items)}{listing_source_line(code)}',reply_markup=ad_buttons(lang,index,len(items),code))
    except Exception as exc:
        print('Ошибка показа объявления:',exc)
        await message.answer(tr(lang,'⚠️ Не удалось загрузить объект. Попробуйте следующее объявление.','⚠️ E’lonni yuklab bo‘lmadi.'),reply_markup=ad_buttons(lang,index,len(items),code))

async def begin_catalog(message,state,lang):
    await state.clear();await state.update_data(catalog=True)
    await state.set_state(Flow.building)
    await message.answer(tr(lang,'💛 <b>СМОТРЕТЬ ОБЪЯВЛЕНИЯ</b>\n\n🏗 Выберите тип недвижимости:','💛 <b>E’LONLARNI KO‘RISH</b>\n\n🏗 Uy-joy turini tanlang:'),reply_markup=types_kb(lang))

class Flow(StatesGroup):
    mode=State(); admin_code=State(); admin_edit=State(); admin_photos=State(); admin_clear=State()
    catalog_category=State(); catalog_results=State(); plus_details=State()
    criteria_menu=State(); building=State(); rooms=State(); district=State(); budget=State(); search_phone=State()
    request_district=State(); address=State(); price=State(); details=State(); name=State(); request_phone=State(); photos=State()
    view_name=State(); view_phone=State(); view_code=State()
    offer_details=State(); offer_name=State(); offer_phone=State(); offer_photos=State()
    owner_photos=State(); owner_details=State(); owner_phone=State(); owner_name=State(); owner_time=State(); owner_telegram=State()
    cooperation=State()
    profile_edit=State(); interest_name=State(); interest_phone=State(); interest_comment=State(); interest_confirm=State()

def criteria_kb(lang, category):
    rows = [
        [tr(lang,'🏗 Выбрать тип строения','🏗 Bino turini tanlash')],
        [tr(lang,'🚪 Выбрать количество комнат','🚪 Xonalar sonini tanlash')],
        [tr(lang,'📍 Выбрать район','📍 Tumanni tanlash')],
        [tr(lang,'💰 Добавить бюджет','💰 Byudjet qo‘shish') if category in ('buy','rent') else tr(lang,'💵 Указать стоимость','💵 Narxni kiritish')],
        [tr(lang,'✅ Продолжить','✅ Davom etish')],
        [w(lang,'back'),w(lang,'menu')]
    ]
    return kb(rows)

def numbered_districts(lang):
    names=[a if lang=='ru' else b for a,b in DISTRICTS]
    return '\n'.join(f'{i}. {name}' for i,name in enumerate(names,1))

async def criteria_screen(message,state,lang):
    data=await state.get_data();cat=data.get('category','buy')
    title={'buy':('ПОКУПКА НЕДВИЖИМОСТИ','UY SOTIB OLISH'),'rent':('АРЕНДА НЕДВИЖИМОСТИ','UY IJARASI'),'sell':('ПРОДАЖА НЕДВИЖИМОСТИ','UY SOTISH'),'give':('СДАЧА В АРЕНДУ','IJARAGA BERISH')}.get(cat,('ПОДБОР НЕДВИЖИМОСТИ','UY TANLASH'))
    building={'new':tr(lang,'Новостройка','Yangi qurilish'),'secondary':tr(lang,'Вторичное жильё','Ikkilamchi uy-joy'),'any':tr(lang,'Непринципиально','Muhim emas')}.get(data.get('building'), '—')
    rooms=data.get('rooms','—');rooms=tr(lang,'Непринципиально','Muhim emas') if rooms=='any' else rooms
    district=data.get('district','—');district=tr(lang,'Весь Ташкент','Butun Toshkent') if district=='any' else district
    price=data.get('budget','—') if cat in ('buy','rent') else data.get('price','—')
    await state.set_state(Flow.criteria_menu)
    await message.answer(f'🖤 ✦ 💛 <b>KEY HOUSE | TASHKENT</b>\n<b>{tr(lang,*title)}</b>\n━━━━━━━━━━━━━━━━━━\n\n🏗 {escape(str(building))}\n🚪 {escape(str(rooms))}\n📍 {escape(str(district))}\n💰 {escape(str(price))}\n\n'+tr(lang,'Выберите параметр для заполнения или изменения. Затем нажмите «Продолжить».','Parametrni tanlang yoki o‘zgartiring. Keyin «Davom etish» tugmasini bosing.'),reply_markup=criteria_kb(lang,cat))

async def begin_building(message,state,category,lang_override=None):
    lang=lang_override or lang_for(message.from_user.id)
    await state.clear()
    await state.update_data(category=category,building='any',rooms='any',district='any',budget='—',price='—')
    await criteria_screen(message,state,lang)

@dp.message(Flow.criteria_menu)
async def choose_criterion(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);data=await state.get_data();cat=data.get('category','buy');t=message.text
    if t==tr(lang,'🏗 Выбрать тип строения','🏗 Bino turini tanlash'):
        await state.set_state(Flow.building)
        await message.answer(tr(lang,'🏗 <b>Выберите тип строения:</b>','🏗 <b>Bino turini tanlang:</b>'),reply_markup=types_kb(lang))
    elif t==tr(lang,'🚪 Выбрать количество комнат','🚪 Xonalar sonini tanlash'):
        await state.set_state(Flow.rooms)
        await message.answer(tr(lang,'🚪 <b>Выберите количество комнат:</b>','🚪 <b>Xonalar sonini tanlang:</b>'),reply_markup=rooms_kb(lang))
    elif t==tr(lang,'📍 Выбрать район','📍 Tumanni tanlash'):
        await state.set_state(Flow.request_district if cat in ('sell','give') else Flow.district)
        await message.answer(tr(lang,'📍 <b>Выберите район Ташкента кнопкой:</b>','📍 <b>Toshkent tumanini tugma orqali tanlang:</b>'),reply_markup=district_kb(lang))
    elif t==(tr(lang,'💰 Добавить бюджет','💰 Byudjet qo‘shish') if cat in ('buy','rent') else tr(lang,'💵 Указать стоимость','💵 Narxni kiritish')):
        await state.update_data(editing_price=cat in ('sell','give'))
        await state.set_state(Flow.budget if cat in ('buy','rent') else Flow.price)
        await message.answer(tr(lang,'💰 <b>Введите бюджет в долларах США</b>\n\nУкажите минимальную и максимальную сумму одним сообщением.\nПример: <b>от 25000$ до 80000$</b>','💰 <b>Byudjetni AQSh dollarida kiriting</b>\n\nEng kam va eng ko‘p summani yozing.\nMasalan: <b>25000$ dan 80000$ gacha</b>') if cat in ('buy','rent') else tr(lang,'💵 Напишите стоимость недвижимости в долларах США:','💵 Mulk narxini AQSh dollarida yozing:'),reply_markup=kb([[w(lang,'nobudget') if cat in ('buy','rent') else w(lang,'skip')],[w(lang,'back')],[w(lang,'menu')]]))
    elif t==tr(lang,'✅ Продолжить','✅ Davom etish'):
        if cat in ('buy','rent'):
            await state.set_state(Flow.search_phone)
            await message.answer(tr(lang,'📞 Укажите номер телефона для заявки на подбор. После отправки мы покажем подходящие объявления.','📞 Uy qidirish arizasi uchun telefon raqamingizni kiriting. Keyin mos e’lonlarni ko‘rsatamiz.'),reply_markup=phone_kb(lang))
        else:
            await state.set_state(Flow.address)
            await message.answer(tr(lang,'📍 Напишите точный адрес недвижимости или ориентир:','📍 Mulkning aniq manzili yoki mo‘ljalini yozing:'),reply_markup=back_kb(lang))
    else:
        await criteria_screen(message,state,lang)

RULES_VERSION = 1
RULES_TEXT = {
'ru': """🩶🧡 <b>ПРАВИЛА ПОЛЬЗОВАНИЯ</b>
<b>KEY HOUSE | TASHKENT</b>

🏠 <b>1. Назначение сервиса</b>
Бот помогает искать недвижимость, просматривать объявления, отправлять заявки и связываться с агентством. Использование бота само по себе не заключает договор с агентством.

🔎 <b>2. Информация об объектах</b>
Стоимость, наличие и характеристики могут изменяться. Перед сделкой уточняйте актуальные сведения у специалиста.

📤 <b>3. Объявления и заявки</b>
Указывайте достоверные данные и действующий телефон. Отправляйте только фотографии, которые вправе использовать. Спам, ложные объявления и незаконные материалы запрещены.

📅 <b>4. Просмотры</b>
Заявка на просмотр не означает подтверждённую запись. Специалист согласует время и доступность объекта отдельно.

🔐 <b>5. Контактные данные</b>
Для обработки заявок используются предоставленные вами имя, телефон, Telegram-контакт и сведения о недвижимости. Они доступны уполномоченным сотрудникам агентства для связи и обработки обращения. По вопросам обработки данных обратитесь к агентству.

🤝 <b>6. Общение</b>
Просим соблюдать уважительный тон. Запрещены угрозы, оскорбления, мошенничество и спам.

⚖️ <b>7. Безопасность</b>
Условия сделки согласовываются отдельно. Проверяйте документы и полномочия сторон перед передачей денег.

📞 <b>8. Помощь</b>
При возникновении вопросов обратитесь к специалистам KEY HOUSE.

🩶 <b><i>«Недвижимость, которую хочется назвать домом»</i></b> 🧡""",
'uz': """🩶🧡 <b>FOYDALANISH QOIDALARI</b>
<b>KEY HOUSE | TASHKENT</b>

🏠 <b>1. Xizmat maqsadi</b>
Bot uy-joy izlash, e’lonlarni ko‘rish, ariza yuborish va agentlik bilan bog‘lanish uchun xizmat qiladi. Botdan foydalanishning o‘zi shartnoma tuzilganini anglatmaydi.

🔎 <b>2. Obyektlar haqida</b>
Narx, mavjudlik va xususiyatlar o‘zgarishi mumkin. Bitimdan oldin ma’lumotni mutaxassis bilan aniqlashtiring.

📤 <b>3. E’lon va arizalar</b>
To‘g‘ri ma’lumot va amaldagi telefon raqamini kiriting. Faqat foydalanishga ruxsatingiz bo‘lgan suratlarni yuboring. Spam, yolg‘on e’lon va noqonuniy materiallar taqiqlanadi.

📅 <b>4. Ko‘rish</b>
Ko‘rish uchun ariza tasdiqlangan uchrashuv emas. Vaqt va obyekt mavjudligi mutaxassis bilan kelishiladi.

🔐 <b>5. Aloqa ma’lumotlari</b>
Arizalarni ko‘rib chiqish uchun ism, telefon, Telegram aloqa ma’lumotlari va mulk haqidagi ma’lumotlardan foydalaniladi. Ular murojaatni ko‘rib chiqish va aloqa uchun vakolatli xodimlarga taqdim etiladi. Savollar bo‘yicha agentlikka murojaat qiling.

🤝 <b>6. Muloqot</b>
Hurmat bilan muloqot qiling. Tahdid, haqorat, firibgarlik va spam taqiqlanadi.

⚖️ <b>7. Xavfsizlik</b>
Bitim shartlari alohida kelishiladi. Pul berishdan oldin hujjatlarni va tomonlarning vakolatini tekshiring.

📞 <b>8. Yordam</b>
Savollaringiz bo‘lsa, KEY HOUSE mutaxassislariga murojaat qiling.

🩶 <b><i>Uy deb atagingiz keladigan ko‘chmas mulk</i></b> 🧡"""
}

def rules_accepted(uid):
    with sqlite3.connect(DB) as c:
        row=c.execute('SELECT version FROM rule_acceptances WHERE user_id=?',(uid,)).fetchone()
    return bool(row and row[0]>=RULES_VERSION)

def rules_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr(lang,'✅ Принимаю правила','✅ Qoidalarni qabul qilaman'),callback_data='rules:accept')],
        [InlineKeyboardButton(text=tr(lang,'❌ Не принимаю','❌ Qabul qilmayman'),callback_data='rules:decline')]
    ])

async def show_rules(message,lang,require_accept=False):
    await message.answer(RULES_TEXT[lang],reply_markup=rules_keyboard(lang) if require_accept else kb([[w(lang,'menu')]]))

@dp.callback_query(F.data.startswith('rules:'))
async def rules_decision(callback:CallbackQuery,state:FSMContext):
    lang=lang_for(callback.from_user.id)
    if callback.data=='rules:accept':
        with sqlite3.connect(DB) as c:
            c.execute('INSERT OR REPLACE INTO rule_acceptances(user_id,version) VALUES(?,?)',(callback.from_user.id,RULES_VERSION))
        await state.clear()
        await callback.message.answer(tr(lang,'✅ Правила приняты. Добро пожаловать в KEY HOUSE | TASHKENT!','✅ Qoidalar qabul qilindi. KEY HOUSE | TASHKENT ga xush kelibsiz!'),reply_markup=menu(lang))
    else:
        await callback.message.answer(tr(lang,'Для использования бота необходимо принять правила. Вы можете ознакомиться с ними снова командой /start.','Botdan foydalanish uchun qoidalarni qabul qilish kerak. /start orqali qayta o‘qing.'),reply_markup=kb([['🇷🇺 Русский','🇺🇿 O‘zbekcha']]))
    await callback.answer()

class RulesGateMiddleware:
    async def __call__(self,handler,event,data):
        user=getattr(event,'from_user',None)
        if user and not rules_accepted(user.id):
            if isinstance(event,Message):
                if event.text=='/start' or (event.text or '').startswith('/start ') or event.text in ('🇷🇺 Русский','🇺🇿 O‘zbekcha'):
                    return await handler(event,data)
                await show_rules(event,lang_for(user.id),True)
                return
            if isinstance(event,CallbackQuery) and not (event.data or '').startswith('rules:'):
                await event.answer('Сначала примите правила / Avval qoidalarni qabul qiling',show_alert=True)
                return
        return await handler(event,data)

dp.message.outer_middleware(RulesGateMiddleware())
dp.callback_query.outer_middleware(RulesGateMiddleware())

@dp.message(CommandStart())
async def start(message:Message,state:FSMContext):
    current=await state.get_state()
    if rules_accepted(message.from_user.id) and current and current not in (Flow.catalog_results.state,Flow.catalog_category.state,Flow.mode.state):
        await message.answer('🖤 У вас есть незавершённая заявка. Продолжить с сохранённого шага или начать заново?',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='▶️ Продолжить',callback_data='draft:resume'),
                InlineKeyboardButton(text='❌ Начать заново',callback_data='draft:discard')]]))
        return
    await state.clear()
    await message.answer('🖤 ✦ 💛 <b>KEY HOUSE | TASHKENT</b>\n━━━━━━━━━━━━━━━━━━\n\n🇷🇺 <b>Выберите язык общения</b>\n🇺🇿 <b>Muloqot tilini tanlang</b>\n\n✦ <i>Ваш дом начинается здесь</i> ✦',reply_markup=kb([['🇷🇺 Русский','🇺🇿 O‘zbekcha']]))

@dp.callback_query(F.data.startswith('draft:'))
async def draft_choice(callback:CallbackQuery,state:FSMContext):
    lang=lang_for(callback.from_user.id)
    if callback.data=='draft:discard':
        await state.clear()
        await callback.message.answer(tr(lang,'Черновик отменён. Выберите действие.','Qoralama bekor qilindi.'),reply_markup=menu(lang))
    else:
        current=await state.get_state()
        if not current:
            await callback.message.answer('Черновик не найден.',reply_markup=menu(lang))
        else:
            await callback.message.answer(tr(lang,'▶️ Продолжаем. Отправьте ответ на последний вопрос бота. Для отмены нажмите «Главное меню».','▶️ Davom etamiz. Botning oxirgi savoliga javob yuboring.'),reply_markup=kb([[w(lang,'menu')]]))
    await callback.answer()

@dp.message(F.text.in_({'🇷🇺 Русский','🇺🇿 O‘zbekcha'}))
async def language_choice(message:Message,state:FSMContext):
    lang='ru' if message.text=='🇷🇺 Русский' else 'uz';save_lang(message.from_user.id,lang)
    if not rules_accepted(message.from_user.id):
        await state.clear()
        await show_rules(message,lang,True)
        return
    text=tr(lang,'🖤 ✦ 💛 <b>KEY HOUSE | TASHKENT</b>\n━━━━━━━━━━━━━━━━━━\n🩶 <b><i>«Недвижимость, которую хочется назвать домом»</i></b> 🧡\n\n✨ Ваш помощник по недвижимости Ташкента!\n\n🏠 Покупайте квартиры в новостройках и на вторичном рынке.\n🔑 Находите жильё для аренды.\n📤 Продавайте и сдавайте свою недвижимость.\n🔎 Просматривайте актуальные объявления.\n📅 Записывайтесь на просмотр по коду объекта.\n📩 Отправляйте предложения с фотографиями.\n🤝 Сотрудничайте с KEY HOUSE.\n\n📍 Выберите действие в меню ниже!','🖤 ✦ 💛 <b>KEY HOUSE | TASHKENT</b>\n━━━━━━━━━━━━━━━━━━\n<i>Uy deb atagingiz keladigan ko‘chmas mulk.</i>\n\n✨ Toshkentdagi ko‘chmas mulk bo‘yicha yordamchingiz!\n\n🏠 Yangi va ikkilamchi uylarni sotib oling.\n🔑 Ijaraga uy toping.\n📤 Mulkingizni soting yoki ijaraga bering.\n🔎 Dolzarb e’lonlarni ko‘ring.\n📅 Obyekt kodi orqali ko‘rishga yoziling.\n📩 Rasmlar bilan taklif yuboring.\n🤝 KEY HOUSE bilan hamkorlik qiling.\n\n📍 Quyidagi menyudan tanlang!')
    await message.answer(text,reply_markup=menu(lang))

@dp.message(F.text.in_({v['menu'] for v in WORDS.values()}))
async def home(message:Message,state:FSMContext):
    await state.clear();lang=lang_for(message.from_user.id)
    await message.answer(tr(lang,'💛 Спасибо, что выбрали <b>KEY HOUSE | TASHKENT</b>!\n\n🤝 Вы всегда можете положиться на нас. Мы рядом, и вы знаете, где нас быстро найти!\n\n🖤 🩶 <b><i>«Недвижимость, которую хочется назвать домом»</i></b> 🧡','💛 <b>KEY HOUSE | TASHKENT</b>ni tanlaganingiz uchun rahmat!\n\n🤝 Bizga doim ishonishingiz mumkin. Biz sizga yaqinmiz va bizni qayerdan topishni bilasiz!\n\n🖤 <i>Uy deb atagingiz keladigan ko‘chmas mulk.</i>'),reply_markup=menu(lang))

@dp.message(F.text.in_({v['backlist'] for v in WORDS.values()}))
async def back_to_list(message:Message,state:FSMContext):
    data=await state.get_data(); lang=lang_for(message.from_user.id);cat=data.get('category','all')
    await begin_catalog(message,state,lang)

@dp.message(F.text.in_({v['back'] for v in WORDS.values()}))
async def go_back(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);data=await state.get_data(); current=await state.get_state()
    if data.get('catalog') and current == Flow.rooms.state:
        await state.set_state(Flow.catalog_category)
        await message.answer(tr(lang,'🏠 Покупка или аренда?','🏠 Sotib olish yoki ijara?'),reply_markup=kb([[w(lang,'buy'),w(lang,'rent')],[w(lang,'back')],[w(lang,'menu')]]))
        return
    if data.get('catalog') and current == Flow.catalog_category.state:
        await begin_catalog(message,state,lang)
        return
    if current in (Flow.building.state,Flow.rooms.state,Flow.district.state,Flow.request_district.state,Flow.budget.state,Flow.price.state,Flow.search_phone.state,Flow.address.state):
        if data.get('catalog'):
            await begin_catalog(message,state,lang)
        else:
            await criteria_screen(message,state,lang)
        return
    if current in (Flow.view_phone.state,):
        await state.set_state(Flow.view_name);await message.answer(tr(lang,'Введите имя:','Ismingizni kiriting:'),reply_markup=back_kb(lang));return
    if current in (Flow.view_code.state,):
        await state.set_state(Flow.view_phone);await message.answer(tr(lang,'Введите телефон:','Telefon raqamingizni kiriting:'),reply_markup=phone_kb(lang));return
    await state.clear();await message.answer(tr(lang,'Выберите раздел:','Bo‘limni tanlang:'),reply_markup=menu(lang))

@dp.message(Flow.catalog_category)
async def catalog_category(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    if message.text not in (w(lang,'buy'),w(lang,'rent')):return
    await state.update_data(category='buy' if message.text==w(lang,'buy') else 'rent')
    await state.set_state(Flow.rooms)
    await message.answer(tr(lang,'🏠 Выберите количество комнат:','🏠 Xonalar sonini tanlang:'),reply_markup=rooms_kb(lang))

@dp.message(F.text.in_({v['buy'] for v in WORDS.values()}))
async def buy(message:Message,state:FSMContext): await choose_mode(message,state,'buy')
@dp.message(F.text.in_({v['rent'] for v in WORDS.values()}))
async def rent(message:Message,state:FSMContext): await choose_mode(message,state,'rent')
async def choose_mode(message,state,category):
    lang=lang_for(message.from_user.id)
    await state.clear();await state.update_data(category=category)
    await state.set_state(Flow.mode)
    await message.answer(tr(lang,'🏠 Выберите способ поиска:','🏠 Qidiruv usulini tanlang:'),reply_markup=kb([[w(lang,'selection')],[w(lang,'stock')],[w(lang,'menu')]]))

@dp.message(Flow.mode)
async def mode_choice(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);data=await state.get_data();category=data.get('category','buy')
    if message.text==w(lang,'selection'):
        await begin_building(message,state,category)
    elif message.text==w(lang,'stock'):
        await state.clear();await state.update_data(category=category,catalog=True,building='any',rooms='any',district='any',budget='—')
        await state.set_state(Flow.building)
        await message.answer(tr(lang,'🏗 Выберите тип строения:','🏗 Bino turini tanlang:'),reply_markup=types_kb(lang))
    else:
        await message.answer(tr(lang,'Выберите действие кнопкой.','Tugma orqali tanlang.'))

@dp.message(F.text.in_({v['sellrent'] for v in WORDS.values()}))
async def sellrent(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.clear()
    await message.answer(tr(lang,'🖤 ✦ 💛 <b>KEY HOUSE | TASHKENT</b>\n━━━━━━━━━━━━━━━━━━\n\n🏡 Благодарим за доверие нашему агентству!\n\nМы с удовольствием поможем вам найти достойного покупателя или надёжного арендатора. Бережно отнесёмся к вашим пожеланиям и сделаем процесс сотрудничества понятным, комфортным и эффективным.\n\n✨ <b>Что вы хотите сделать с недвижимостью?</b>','🖤 ✦ 💛 <b>KEY HOUSE | TASHKENT</b>\n━━━━━━━━━━━━━━━━━━\n\n🏡 Agentligimizga bildirgan ishonchingiz uchun rahmat!\n\nSizga munosib xaridor yoki ishonchli ijarachi topishda mamnuniyat bilan yordam beramiz.\n\n✨ <b>Mulkingiz bilan nima qilmoqchisiz?</b>'),reply_markup=kb([[w(lang,'sell'),w(lang,'give')],[w(lang,'back')],[w(lang,'menu')]]))
@dp.message(F.text.in_({v['sell'] for v in WORDS.values()}|{v['give'] for v in WORDS.values()}))
async def sell_or_give(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);kind='sell' if message.text==w(lang,'sell') else 'give'
    await begin_building(message,state,kind)

@dp.message(Flow.building)
async def select_building(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    mapping={w(lang,'new'):'new',w(lang,'secondary'):'secondary',w(lang,'any'):'any'}
    if message.text not in mapping:
        await message.answer(tr(lang,'Выберите кнопкой:','Tugma orqali tanlang:'),reply_markup=types_kb(lang));return
    data=await state.get_data();category=data.get('category','all');await state.update_data(building=mapping[message.text])
    if data.get('catalog') and data.get('category') in ('buy','rent'):
        await state.set_state(Flow.rooms)
        await message.answer(tr(lang,'🚪 Выберите количество комнат:','🚪 Xonalar sonini tanlang:'),reply_markup=rooms_kb(lang))
    elif data.get('catalog'):
        await state.set_state(Flow.catalog_category)
        await message.answer(tr(lang,'🏠 Покупка или аренда?','🏠 Sotib olish yoki ijara?'),reply_markup=kb([[w(lang,'buy'),w(lang,'rent')],[w(lang,'back')],[w(lang,'menu')]]))
    else:
        await criteria_screen(message,state,lang)

@dp.message(Flow.rooms)
async def select_rooms(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    if message.text not in ('1','2','3','4+',w(lang,'any')):
        await message.answer(tr(lang,'Выберите число комнат кнопкой.','Xonalar sonini tugma bilan tanlang.'),reply_markup=rooms_kb(lang));return
    await state.update_data(rooms='any' if message.text==w(lang,'any') else message.text)
    if (await state.get_data()).get('catalog'):
        await state.set_state(Flow.district)
        await message.answer(tr(lang,'📍 Выберите район:','📍 Tumanni tanlang:'),reply_markup=district_kb(lang))
    else:
        await criteria_screen(message,state,lang)

def district_value(text,lang):
    if text==w(lang,'allcity') or text==w(lang,'any'):return text
    names=['📍 '+(a if lang=='ru' else b) for a,b in DISTRICTS]
    return text if text in names else None

async def district_step(message,state,is_request):
    lang=lang_for(message.from_user.id);data=await state.get_data();t=(message.text or '').strip()
    if t==w(lang,'manual'):
        await state.update_data(manual=True)
        await message.answer(tr(lang,'✍️ Напишите район или адрес вручную:','✍️ Tuman yoki manzilni yozing:'),reply_markup=back_kb(lang));return
    if data.get('manual'):
        district=t
    elif t in (w(lang,'allcity'),w(lang,'any')):
        district='any'
    elif t.isdigit() and 1<=int(t)<=len(DISTRICTS):
        district=DISTRICTS[int(t)-1][0]
    else:
        district=next((ru for ru,uz in DISTRICTS if t in ('📍 '+ru,'📍 '+uz)),None)
    if not district:
        await message.answer(tr(lang,'⚠️ Выберите район кнопкой ниже.','⚠️ Quyidagi tugmalardan tumanni tanlang.'),reply_markup=district_kb(lang));return
    await state.update_data(district=district,manual=False)
    if data.get('catalog'):
        await state.update_data(ad_index=0)
        await state.set_state(Flow.catalog_results)
        await show_next_ad(message,state,lang)
    else:
        await criteria_screen(message,state,lang)

@dp.message(Flow.district)
async def search_district(message:Message,state:FSMContext): await district_step(message,state,False)
@dp.message(Flow.request_district)
async def request_district(message:Message,state:FSMContext): await district_step(message,state,True)

@dp.message(Flow.budget)
async def budget(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);t=(message.text or '').strip()
    if t==w(lang,'nobudget'):
        await state.update_data(budget='—')
    else:
        nums=[int(re.sub(r'\D','',n)) for n in re.findall(r'\d[\d ]*',t)]
        if not nums or len(nums)>2 or min(nums)<=0 or (len(nums)==2 and nums[1]<nums[0]):
            await message.answer(tr(lang,'⚠️ Укажите сумму: 75000, до 60000, от 45000 или 50000-80000 (USD).','⚠️ Summani kiriting: 75000, 60000 gacha, 45000 dan yoki 50000-80000 (USD).'));return
        if len(nums)==2:val=f'{nums[0]}-{nums[1]}'
        elif t.lower().startswith(('от','from')):val=f'от {nums[0]}'
        else:val=f'до {nums[0]}'
        await state.update_data(budget=val)
    await criteria_screen(message,state,lang)

def phone_of(message):
    raw=message.contact.phone_number if message.contact and message.contact.user_id==message.from_user.id else (message.text or '')
    digits=re.sub(r'\D','',raw)
    if len(digits)==9:digits='998'+digits
    if len(digits)!=12 or not digits.startswith('998'):return None
    return '+'+digits

def budget_limits(value):
    if not value or value=='—':return None
    nums=[int(x.replace(' ','')) for x in re.findall(r'\d[\d ]*',str(value))]
    if not nums:return None
    if len(nums)>=2:return (min(nums[:2]),max(nums[:2]))
    return (nums[0],None) if str(value).lower().strip().startswith(('от','from')) else (None,nums[0])

def listing_has_photo(chat_id,msg_id):
    with sqlite3.connect(DB) as c:
        r=c.execute('SELECT media_group_id FROM listing_media WHERE chat_id=? AND message_id=?',(chat_id,msg_id)).fetchone()
        if not r:return False
        if r[0]:return bool(c.execute('SELECT 1 FROM listing_media WHERE chat_id=? AND media_group_id=? AND file_id IS NOT NULL LIMIT 1',(chat_id,r[0])).fetchone())
        return bool(c.execute('SELECT 1 FROM listing_media WHERE chat_id=? AND message_id=? AND file_id IS NOT NULL',(chat_id,msg_id)).fetchone())

def listing_description(chat_id,msg_id):
    with sqlite3.connect(DB) as c:
        override=c.execute('SELECT o.description FROM admin_overrides o JOIN listings l ON l.code=o.code WHERE l.chat_id=? AND l.message_id=?',(chat_id,msg_id)).fetchone()
        if override and override[0] is not None:return override[0]
        r=c.execute('SELECT media_group_id,caption FROM listing_media WHERE chat_id=? AND message_id=?',(chat_id,msg_id)).fetchone()
        if not r:return ''
        if r[0]:
            x=c.execute('SELECT caption FROM listing_media WHERE chat_id=? AND media_group_id=? AND caption IS NOT NULL AND caption!=\'\' ORDER BY LENGTH(caption) DESC LIMIT 1',(chat_id,r[0])).fetchone()
            return x[0] if x else ''
        return r[1] or ''

def listing_price(text):
    # Price only when explicitly marked with $ or USD; never convert UZS to USD.
    m=re.search(r'(?<!\d)(\d[\d \,.]{0,15})\s*(?:\$|usd|у\.?е\.?|доллар)',text,re.I)
    if not m:m=re.search(r'(?:\$|usd)\s*(\d[\d \,.]{0,15})',text,re.I)
    if not m:return None
    digits=re.sub(r'\D','',m.group(1))
    return int(digits) if digits else None

def price_match(chat_id,msg_id,budget):
    limits=budget_limits(budget)
    if not limits:return 'exact'
    price=listing_price(listing_description(chat_id,msg_id))
    if price is None:return 'possible'
    lo,hi=limits
    if lo is not None and price<lo:return 'exclude'
    if hi is not None and price>hi:return 'slightly_above' if price<=hi*1.05 else 'exclude'
    return 'exact'

def save_profile(uid,name=None,phone=None,search=None):
    with sqlite3.connect(DB) as c:
        c.execute('INSERT OR IGNORE INTO profiles(user_id) VALUES(?)',(uid,))
        if name is not None:c.execute('UPDATE profiles SET name=? WHERE user_id=?',(name,uid))
        if phone is not None:c.execute('UPDATE profiles SET phone=? WHERE user_id=?',(phone,uid))
        if search is not None:c.execute('UPDATE profiles SET last_search=? WHERE user_id=?',(json.dumps(search,ensure_ascii=False),uid))

def profile(uid):
    with sqlite3.connect(DB) as c:
        return c.execute('SELECT name,phone,last_search FROM profiles WHERE user_id=?',(uid,)).fetchone() or (None,None,None)

def record_application(uid,kind,code=None,name=None,phone=None):
    with sqlite3.connect(DB) as c:
        repeated=bool(c.execute('SELECT 1 FROM applications WHERE user_id=? AND kind=? AND COALESCE(code,\'\')=?',(uid,kind,str(code or ''))).fetchone())
        c.execute('INSERT INTO applications(user_id,kind,code,repeated) VALUES(?,?,?,?)',(uid,kind,str(code) if code else None,int(repeated)))
    save_profile(uid,name,phone)
    return repeated

_queue_lock=asyncio.Lock()

async def _deliver_job(job_id):
    async with _queue_lock:
        with sqlite3.connect(DB) as c:
            r=c.execute('SELECT payload,photos,state,attempts,telegram_message_id,user_id,created_ts,alerted FROM delivery_queue WHERE id=?',(job_id,)).fetchone()
            if not r or r[2]=='sent':return True
            if not REQUESTS_CHAT_ID:return False
            payload,photos_json,_,attempts,mid,uid,created_ts,alerted=r
            photos=json.loads(photos_json or '[]')
            c.execute('UPDATE delivery_queue SET state=?,attempts=attempts+1 WHERE id=?',('sending',job_id))
        try:
            # The job number helps staff identify duplicate messages after network uncertainty.
            if not mid:
                result=await bot.send_message(REQUESTS_CHAT_ID,f'📨 <b>Заявка №Q{job_id}</b>\\n'+payload)
                mid=result.message_id
                with sqlite3.connect(DB) as c:
                    c.execute('UPDATE delivery_queue SET telegram_message_id=? WHERE id=?',(mid,job_id))
            for i,photo in enumerate(photos):
                # Resume after partial photo delivery: persist per-photo progress.
                with sqlite3.connect(DB) as c:
                    done=c.execute('SELECT photo_progress FROM delivery_queue WHERE id=?',(job_id,)).fetchone()[0]
                if i<done:continue
                await bot.send_photo(REQUESTS_CHAT_ID,photo,caption=f'Заявка №Q{job_id} · фото {i+1}/{len(photos)}')
                with sqlite3.connect(DB) as c:c.execute('UPDATE delivery_queue SET photo_progress=? WHERE id=?',(i+1,job_id))
            with sqlite3.connect(DB) as c:c.execute('UPDATE delivery_queue SET state=?,last_error=NULL WHERE id=?',('sent',job_id))
            if uid:
                try:await bot.send_message(uid,f'✅ Ваша заявка №Q{job_id} доставлена специалистам KEY HOUSE.')
                except Exception:pass
            return True
        except Exception as exc:
            delay=min(3600,15*(2**min(attempts,8)))
            with sqlite3.connect(DB) as c:
                c.execute('UPDATE delivery_queue SET state=?,next_attempt=?,last_error=? WHERE id=?',
                          ('pending',int(time.time())+delay,str(exc)[:800],job_id))
            return False

async def send_request(text,photos=None,user_id=None,kind='request',code=None):
    # Persist before network I/O. True means accepted to the queue, not necessarily delivered.
    if not REQUESTS_CHAT_ID:return False
    with sqlite3.connect(DB) as c:
        cursor=c.execute('INSERT INTO delivery_queue(user_id,kind,code,payload,photos,state,created_ts,next_attempt) VALUES(?,?,?,?,?,?,?,?)',
                         (user_id,kind,code,text,json.dumps(photos or []),'pending',int(time.time()),int(time.time())))
        job_id=cursor.lastrowid
    await _deliver_job(job_id)
    return True

async def delivery_worker():
    while True:
        try:
            now=int(time.time())
            with sqlite3.connect(DB) as c:
                jobs=c.execute("SELECT id FROM delivery_queue WHERE state IN ('pending','sending') AND next_attempt<=? ORDER BY id LIMIT 20",(now,)).fetchall()
                late=c.execute("SELECT id,last_error FROM delivery_queue WHERE state!='sent' AND alerted=0 AND created_ts>0 AND created_ts<=?",(now-900,)).fetchall()
                for jid,_ in late:c.execute('UPDATE delivery_queue SET alerted=1 WHERE id=?',(jid,))
            for (jid,) in jobs:await _deliver_job(jid)
            for jid,error in late:
                for admin in ADMIN_IDS:
                    try:await bot.send_message(admin,f'⚠️ Заявка №Q{jid} не доставлена более 15 минут. Ошибка: {escape(error or "нет соединения")}')
                    except Exception:pass
        except Exception as exc:print('Queue worker:',repr(exc))
        await asyncio.sleep(15)

async def reminder_worker():
    # Tashkent UTC+5, one reminder after 24h; expiry after 7 days.
    while True:
        try:
            now=int(time.time())
            with sqlite3.connect(DB) as c:
                c.execute('UPDATE persistent_fsm SET state=NULL,data=\'{}\',reminded=1 WHERE state IS NOT NULL AND updated_at<?',(now-7*86400,))
                rows=c.execute('SELECT chat_id,user_id,state FROM persistent_fsm WHERE state IS NOT NULL AND reminded=0 AND updated_at>0 AND updated_at<=?',(now-86400,)).fetchall()
            hour=datetime.now(timezone(timedelta(hours=5))).hour
            if 9<=hour<21:
                for chat_id,uid,state in rows:
                    # No reminders for passive catalogue browsing or admin operations.
                    if not state.startswith('Flow:') or state.split(':',1)[1] in ('catalog_results','catalog_category','mode','admin_code','admin_edit','admin_photos','admin_clear','profile_edit'):continue
                    with sqlite3.connect(DB) as c:
                        changed=c.execute('UPDATE persistent_fsm SET reminded=1 WHERE chat_id=? AND user_id=? AND reminded=0 AND state=?',(chat_id,uid,state)).rowcount
                    if not changed:continue
                    try:await bot.send_message(chat_id,'🖤 KEY HOUSE: у вас осталась незавершённая заявка. Откройте бот, чтобы продолжить, или нажмите «Главное меню», чтобы отменить.')
                    except Exception:pass
        except Exception as exc:print('Reminder worker:',repr(exc))
        await asyncio.sleep(60)

async def receipt(message,lang,success=True,offer=False):
    if not success:
        await message.answer(tr(lang,'⚠️ Не удалось передать заявку. Свяжитесь с нами напрямую.','⚠️ So‘rov yuborilmadi. Biz bilan bevosita bog‘laning.'),reply_markup=menu(lang));return
    if offer:
        await message.answer(tr(lang,'💛 Спасибо за то, что выбрали нас! Наши специалисты перезвонят вам для уточнения всех деталей в течение 40–60 минут.','💛 Bizni tanlaganingiz uchun rahmat! Mutaxassislarimiz barcha tafsilotlarni aniqlashtirish uchun 40–60 daqiqa ichida sizga qo‘ng‘iroq qilishadi.'),reply_markup=menu(lang))
    else:
        await message.answer(tr(lang,'💛 Спасибо! Ваша заявка принята. Если связь с рабочей группой временно недоступна, бот повторит отправку автоматически.','💛 Rahmat! So‘rovingiz qabul qilindi. Yetkazib berish vaqtincha imkonsiz bo‘lsa, bot qayta urinadi.'),reply_markup=menu(lang))

@dp.message(Flow.search_phone)
async def search_phone(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);phone=phone_of(message)
    if not phone:
        await message.answer(tr(lang,'Введите корректный номер телефона.','To‘g‘ri telefon raqamini kiriting.'));return
    data=await state.get_data();cat=data['category'];building=data['building']
    report=('🔎 <b>Заявка на подбор / Uy qidirish</b>\n'+f'Тип: {escape(cat)}\nПостройка: {escape(building)}\nКомнаты: {escape(data["rooms"])}\nРайон: {escape(data["district"])}\nБюджет: {escape(data["budget"])}\nТелефон: {escape(phone)}\nКлиент: {escape(message.from_user.full_name)}\n{client_telegram(message.from_user)}')
    ok=await send_request(report,user_id=message.from_user.id);await state.clear();await receipt(message,lang,ok)
    if ok:record_application(message.from_user.id,'selection_'+cat,name=message.from_user.full_name,phone=phone);save_profile(message.from_user.id,search=data)
    if ok:
        await state.update_data(catalog=True, category=cat, building=building, rooms=data.get('rooms','any'), district=data.get('district','any'), ad_index=0)
        await state.set_state(Flow.catalog_results)
        await show_next_ad(message,state,lang)

@dp.message(Flow.address)
async def request_address(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.update_data(address=message.text or '—')
    if (await state.get_data()).get('price','—')!='—':
        await state.set_state(Flow.details)
        await message.answer(tr(lang,'📝 Опишите площадь, этаж и состояние недвижимости:','📝 Maydon, qavat va mulk holatini yozing:'),reply_markup=back_kb(lang))
    else:
        await state.set_state(Flow.price)
        await message.answer(tr(lang,'💰 Укажите желаемую цену:','💰 Istalgan narxni kiriting:'),reply_markup=back_kb(lang))
@dp.message(Flow.price)
async def request_price(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);data=await state.get_data();await state.update_data(price='—' if message.text==w(lang,'skip') else (message.text or '—'))
    if data.get('editing_price'):
        await state.update_data(editing_price=False)
        await criteria_screen(message,state,lang);return
    await state.set_state(Flow.details)
    await message.answer(tr(lang,'📝 Опишите площадь, комнаты, этаж, состояние:','📝 Maydon, xonalar, qavat va holatini yozing:'),reply_markup=back_kb(lang))
@dp.message(Flow.details)
async def request_details(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.update_data(details=message.text or '—');await state.set_state(Flow.name)
    await message.answer(tr(lang,'Как к вам обращаться?','Sizga qanday murojaat qilaylik?'),reply_markup=back_kb(lang))
@dp.message(Flow.name)
async def request_name(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.update_data(name=message.text or '—');await state.set_state(Flow.request_phone)
    await message.answer(tr(lang,'📞 Ваш телефон:','📞 Telefon raqamingiz:'),reply_markup=phone_kb(lang))
@dp.message(Flow.request_phone)
async def request_phone(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);phone=phone_of(message)
    if not phone:await message.answer(tr(lang,'Введите корректный телефон.','To‘g‘ri telefon kiriting.'));return
    await state.update_data(phone=phone,photos=[]);await state.set_state(Flow.photos)
    await message.answer(tr(lang,'📷 Пришлите до 10 фотографий, затем нажмите «Готово».','📷 10 tagacha surat yuboring, keyin «Tayyor» tugmasini bosing.'),reply_markup=kb([[w(lang,'done'),w(lang,'skip')],[w(lang,'menu')]]))

# Public refresh: read only the bot's local records; Bot API cannot scan channel history.
_refresh_lock = asyncio.Lock()

async def refresh_catalog(message, lang, state=None):
    if _refresh_lock.locked():
        await message.answer(tr(lang,'⏳ Каталог уже обновляется. Попробуйте чуть позже.','⏳ Katalog yangilanmoqda. Biroz kuting.'))
        return
    async with _refresh_lock:
        with sqlite3.connect(DB) as c:
            c.execute('PRAGMA wal_checkpoint(PASSIVE)')
            count = c.execute("SELECT COUNT(*) FROM listings WHERE status='active'").fetchone()[0]
        await message.answer(tr(lang,
            f'🔄 <b>Каталог обновлён из сохранённых данных</b>\n\n🏠 Доступно объявлений: {count}\n\n💛 Новые публикации и изменения, полученные ботом из канала, учитываются автоматически. Полная проверка истории канала этой кнопкой не выполняется.\n\nВыберите «Смотреть объявления», чтобы найти объект.',
            f'🔄 <b>Saqlangan ma’lumotlar asosida katalog yangilandi</b>\n\n🏠 E’lonlar: {count}\n\n💛 Bot olgan yangi postlar va o‘zgarishlar avtomatik saqlanadi. Kanalning butun tarixi qayta tekshirilmaydi.'),
            reply_markup=menu(lang))

@dp.message(F.text.in_({v['refresh'] for v in WORDS.values()}))
async def refresh_button(message:Message,state:FSMContext):
    await refresh_catalog(message,lang_for(message.from_user.id),state)

@dp.callback_query(F.data == 'refreshads')
async def refresh_from_ad(callback:CallbackQuery,state:FSMContext):
    lang=lang_for(callback.from_user.id)
    await callback.answer()
    await refresh_catalog(callback.message,lang,state)
    data=await state.get_data()
    if data.get('catalog') and await state.get_state()==Flow.catalog_results.state:
        await state.update_data(ad_index=0)
        await show_next_ad(callback.message,state,lang)

# Administrator-only catalogue management. Admin actions are never exposed to clients.
def client_telegram(user):
    if user.username:
        username=escape(user.username)
        return f'💬 Telegram: <a href="https://t.me/{username}">@{username}</a>'
    return f'💬 Telegram: <a href="tg://user?id={user.id}">Открыть профиль клиента</a>'

def source_post_url(chat_id,message_id):
    if LISTINGS_CHAT_ID and chat_id==LISTINGS_CHAT_ID and message_id:
        return f'https://t.me/House_deLux/{int(message_id)}'
    return None

def listing_post_url(code):
    with sqlite3.connect(DB) as c:
        row=c.execute('SELECT chat_id,message_id FROM listings WHERE code=?',(str(code),)).fetchone()
        if not row:return None
        chat_id,root_id=row
        group=c.execute('SELECT media_group_id FROM listing_media WHERE chat_id=? AND message_id=?',(chat_id,root_id)).fetchone()
        if group and group[0]:
            first=c.execute('SELECT message_id FROM listing_media WHERE chat_id=? AND media_group_id=? ORDER BY message_id LIMIT 1',(chat_id,group[0])).fetchone()
            if first:root_id=first[0]
        return source_post_url(chat_id,root_id)

def listing_source_line(code):
    url=listing_post_url(code)
    return f'\n🔗 <a href="{url}">Открыть объявление в канале</a>' if url else '\n⚠️ Ссылка на исходное объявление недоступна.'

def is_admin(uid):return uid in ADMIN_IDS

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔎 Поиск: код или адрес',callback_data='admin:find')],
        [InlineKeyboardButton(text='📋 Последние объекты',callback_data='admin:recent')],
        [InlineKeyboardButton(text='📊 Статистика',callback_data='admin:stats')],
        [InlineKeyboardButton(text='🧹 Очистить каталог',callback_data='admin:clear')]])

def object_keyboard(code):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Активен',callback_data=f'admin:status:{code}:active'),
         InlineKeyboardButton(text='🚫 Недоступен',callback_data=f'admin:status:{code}:unavailable')],
        [InlineKeyboardButton(text='✏️ Изменить описание / цену',callback_data=f'admin:edit:{code}'),
         InlineKeyboardButton(text='📷 Заменить фотографии',callback_data=f'admin:photos:{code}')],
        [InlineKeyboardButton(text='🗑 Удалить объект',callback_data=f'admin:delete:{code}')],
        [InlineKeyboardButton(text='🔎 Новый поиск',callback_data='admin:find'),
         InlineKeyboardButton(text='👑 Панель',callback_data='admin:home')]])

def audit(c,uid,action,code=''):
    c.execute('INSERT INTO admin_audit(admin_id,action,code) VALUES(?,?,?)',(uid,action,str(code)))

async def admin_error(exc,context):
    print('ADMIN ERROR',context,repr(exc))
    for uid in ADMIN_IDS:
        try:await bot.send_message(uid,f'⚠️ <b>KEY HOUSE: ошибка</b>\n{escape(context)}\n{escape(str(exc))[:2000]}')
        except Exception:pass

async def admin_show(message,code):
    with sqlite3.connect(DB) as c:
        row=c.execute('SELECT chat_id,message_id,status FROM listings WHERE code=?',(str(code),)).fetchone()
        reason=c.execute('SELECT reason FROM admin_reasons WHERE code=?',(str(code),)).fetchone()
    if not row:
        await message.answer('⚠️ Объект не найден или уже удалён.',reply_markup=admin_keyboard());return
    desc=listing_description(row[0],row[1])
    await message.answer(f'🏠 <b>Объект №{escape(str(code))}</b>\nСтатус: <b>{"Активен" if row[2]=="active" else "Недоступен"}</b>'
        +(f'\nПричина: {escape(reason[0])}' if reason else '')
        +f'\n\n{escape(desc[:1400]) if desc else "Описание не указано."}'
        +listing_source_line(code),reply_markup=object_keyboard(code))

@dp.message(Command('admin'))
async def admin_command(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer('⛔ Доступ только администраторам.');return
    await state.clear()
    await message.answer('👑 <b>KEY HOUSE | Панель администратора</b>\nУправление объектами доступно по коду и части адреса.',reply_markup=admin_keyboard())

@dp.callback_query(F.data.startswith('admin:'))
async def admin_callback(callback:CallbackQuery,state:FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer('Недостаточно прав',show_alert=True);return
    await callback.answer()
    parts=callback.data.split(':');action=parts[1];uid=callback.from_user.id
    try:
        if action=='home':
            await state.clear()
            await callback.message.answer('👑 Административная панель',reply_markup=admin_keyboard())
        elif action in ('find','code'):
            await state.set_state(Flow.admin_code)
            await callback.message.answer('🔎 Отправьте код (2–3 цифры) или часть адреса объекта.')
        elif action=='stats':
            with sqlite3.connect(DB) as c:
                counts=dict(c.execute('SELECT status,COUNT(*) FROM listings GROUP BY status'))
                total=c.execute('SELECT COUNT(*) FROM listings').fetchone()[0]
            await callback.message.answer(f'📊 <b>Каталог: {total}</b>\n✅ Активных: {counts.get("active",0)}\n🚫 Недоступных: {total-counts.get("active",0)}',reply_markup=admin_keyboard())
        elif action=='recent':
            with sqlite3.connect(DB) as c:
                rows=c.execute('SELECT code,status FROM listings ORDER BY id DESC LIMIT 12').fetchall()
            keys=[[InlineKeyboardButton(text=f'№{code} · {"✅" if status=="active" else "🚫"}',callback_data=f'admin:show:{code}')] for code,status in rows if code]
            keys.append([InlineKeyboardButton(text='👑 Панель',callback_data='admin:home')])
            await callback.message.answer('📋 Последние объекты',reply_markup=InlineKeyboardMarkup(inline_keyboard=keys))
        elif action=='show' and len(parts)==3:
            await admin_show(callback.message,parts[2])
        elif action=='status' and len(parts)==4:
            code,status=parts[2:]
            if status not in ('active','unavailable'):return
            with sqlite3.connect(DB) as c:
                changed=c.execute('UPDATE listings SET status=? WHERE code=?',(status,code)).rowcount
                if changed:audit(c,uid,'status:'+status,code)
            if changed and status=='unavailable':
                await state.set_state(Flow.admin_edit)
                await state.update_data(admin_code=code,admin_action='reason')
                await callback.message.answer('🚫 Объект недоступен. Укажите причину (например: продан, сдан, снят с продажи) или отправьте «-».')
            else:await admin_show(callback.message,code)
        elif action in ('edit','photos') and len(parts)==3:
            code=parts[2]
            with sqlite3.connect(DB) as c:exists=c.execute('SELECT 1 FROM listings WHERE code=?',(code,)).fetchone()
            if not exists:
                await callback.message.answer('Объект не найден.');return
            if action=='edit':
                await state.set_state(Flow.admin_edit)
                await state.update_data(admin_code=code,admin_action='description')
                await callback.message.answer(f'✏️ №{code}. Отправьте новое <b>полное описание</b> одним сообщением, включая цену. Код останется прежним.')
            else:
                await state.set_state(Flow.admin_photos)
                await state.update_data(admin_code=code,admin_photos=[])
                await callback.message.answer(f'📷 №{code}. Отправьте новые фото (1–10 штук), затем напишите <b>ГОТОВО</b>. Старые фото заменятся только после подтверждения.')
        elif action=='delete' and len(parts)==3:
            code=parts[2]
            await callback.message.answer(f'⚠️ Удалить объект №{escape(code)} из каталога? Это действие нельзя отменить.',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text='🗑 Да, удалить',callback_data=f'admin:delok:{code}'),
                    InlineKeyboardButton(text='❌ Отмена',callback_data=f'admin:show:{code}')]]))
        elif action=='delok' and len(parts)==3:
            code=parts[2]
            with sqlite3.connect(DB) as c:
                row=c.execute('SELECT chat_id,message_id FROM listings WHERE code=?',(code,)).fetchone()
                if row:
                    media_group=c.execute('SELECT media_group_id FROM listing_media WHERE chat_id=? AND message_id=?',row).fetchone()
                    if media_group and media_group[0]:
                        mids=[r[0] for r in c.execute('SELECT message_id FROM listing_media WHERE chat_id=? AND media_group_id=?',(row[0],media_group[0]))]
                    else:mids=[row[1]]
                    c.execute('INSERT OR REPLACE INTO admin_deleted_posts VALUES(?,?,?)',(code,row[0],json.dumps(mids)))
                    c.execute('DELETE FROM listings WHERE code=?',(code,))
                    c.execute('DELETE FROM admin_media WHERE code=?',(code,))
                    c.execute('DELETE FROM admin_overrides WHERE code=?',(code,))
                    c.execute('DELETE FROM admin_reasons WHERE code=?',(code,))
                    audit(c,uid,'delete',code)
            if not row:
                await callback.message.answer('Объект уже удалён.');return
            await callback.message.answer(f'🗑 Объект №{code} удалён из каталога. Его код сохранён в истории и больше не используется.')
            if row[0]==LISTINGS_CHAT_ID:
                await callback.message.answer('Удалить исходный пост из Telegram-канала? Это возможно только при наличии прав бота.',
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text='🗑 Удалить пост',callback_data=f'admin:channeldelete:{code}'),
                        InlineKeyboardButton(text='Оставить в канале',callback_data='admin:home')]]))
        elif action=='channeldelete' and len(parts)==3:
            code=parts[2]
            with sqlite3.connect(DB) as c:
                row=c.execute('SELECT chat_id,message_ids FROM admin_deleted_posts WHERE code=?',(code,)).fetchone()
            if not row or row[0]!=LISTINGS_CHAT_ID:return
            failures=[]
            for mid in json.loads(row[1]):
                try:await bot.delete_message(row[0],mid)
                except Exception as exc:failures.append(f'{mid}: {exc}')
            if failures:
                await admin_error(Exception('; '.join(failures)),'Удаление постов из канала')
                await callback.message.answer('⚠️ Не все сообщения удалось удалить. Проверьте права бота.')
            else:
                with sqlite3.connect(DB) as c:c.execute('DELETE FROM admin_deleted_posts WHERE code=?',(code,))
                await callback.message.answer('✅ Исходная публикация удалена из канала.')
        elif action=='clear':
            await callback.message.answer('⚠️ <b>ОЧИСТКА ВСЕГО КАТАЛОГА</b>\nПервое подтверждение.',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text='Продолжить',callback_data='admin:clear2'),
                    InlineKeyboardButton(text='Отмена',callback_data='admin:home')]]))
        elif action=='clear2':
            await state.set_state(Flow.admin_clear)
            await callback.message.answer('⚠️ Второе подтверждение: напишите точно <b>ОЧИСТИТЬ</b>. Все объявления исчезнут из базы, но коды останутся зарезервированными.')
    except Exception as exc:
        await admin_error(exc,'admin_callback')
        await callback.message.answer('⚠️ Ошибка административной операции. Администраторы уведомлены.')

@dp.message(Flow.admin_code)
async def admin_code_handler(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id):await state.clear();return
    term=(message.text or '').strip().lstrip('#№ ')
    if len(term)<2:await message.answer('Введите код или хотя бы 2 символа адреса.');return
    with sqlite3.connect(DB) as c:
        rows=c.execute('SELECT code,chat_id,message_id FROM listings WHERE code=?',(term,)).fetchall()
        if not rows:
            rows=c.execute('SELECT code,chat_id,message_id FROM listings ORDER BY id DESC').fetchall()
            rows=[r for r in rows if term.casefold() in listing_description(r[1],r[2]).casefold()][:12]
    if not rows:
        await message.answer('⚠️ Совпадений нет. Попробуйте другой код или адрес.');return
    await state.clear()
    if len(rows)==1:await admin_show(message,rows[0][0]);return
    await message.answer('🔎 Найденные объекты:',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f'🏠 №{code}',callback_data=f'admin:show:{code}')] for code,_,_ in rows if code]))

@dp.message(Flow.admin_edit)
async def admin_edit_handler(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id):await state.clear();return
    data=await state.get_data();code=data.get('admin_code');action=data.get('admin_action')
    val=(message.text or '').strip()
    if not val:await message.answer('Отправьте текстовое сообщение.');return
    with sqlite3.connect(DB) as c:
        row=c.execute('SELECT chat_id,message_id FROM listings WHERE code=?',(code,)).fetchone()
        if not row:await state.clear();await message.answer('Объект уже удалён.');return
        if action=='reason':
            c.execute('INSERT OR REPLACE INTO admin_reasons(code,reason) VALUES(?,?)',(code,val if val!='-' else 'Не указана'))
        else:
            c.execute('INSERT OR REPLACE INTO admin_overrides(code,description) VALUES(?,?)',(code,val))
            c.execute('UPDATE listings SET category=?,housing=? WHERE code=?',(classify(val),housing(val),code))
            c.execute('INSERT OR REPLACE INTO listing_meta(message_id,rooms,district) VALUES(?,?,?)',
                (row[1],parse_rooms(val),parse_district(val)))
        audit(c,message.from_user.id,action,code)
    await state.clear();await message.answer('✅ Изменения сохранены.');await admin_show(message,code)

@dp.message(Flow.admin_photos,F.photo)
async def admin_collect_photo(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id):return
    data=await state.get_data();photos=data.get('admin_photos',[])
    if len(photos)>=10:
        await message.answer('Максимум 10 фотографий. Напишите ГОТОВО.');return
    photos.append(message.photo[-1].file_id)
    await state.update_data(admin_photos=photos)
    await message.answer(f'📷 Получено {len(photos)}/10. Для завершения напишите ГОТОВО.')

@dp.message(Flow.admin_photos)
async def admin_finish_photos(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id):return
    data=await state.get_data();code=data.get('admin_code');photos=data.get('admin_photos',[])
    if (message.text or '').strip().upper()!='ГОТОВО' or not photos:
        await message.answer('Пришлите хотя бы одно фото и напишите ГОТОВО.');return
    with sqlite3.connect(DB) as c:
        c.execute('INSERT OR REPLACE INTO admin_media(code,file_ids) VALUES(?,?)',(code,json.dumps(photos)))
        audit(c,message.from_user.id,'replace_photos',code)
    await state.clear();await message.answer('✅ Фотографии заменены в каталоге. Исходный пост канала не изменён.')
    await admin_show(message,code)

@dp.message(Flow.admin_clear)
async def admin_clear_handler(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id):await state.clear();return
    if (message.text or '').strip()!='ОЧИСТИТЬ':
        await state.clear();await message.answer('❌ Очистка отменена.',reply_markup=admin_keyboard());return
    with sqlite3.connect(DB) as c:
        c.execute('INSERT OR IGNORE INTO code_history(code) SELECT code FROM listings WHERE code IS NOT NULL')
        count=c.execute('SELECT COUNT(*) FROM listings').fetchone()[0]
        c.execute('DELETE FROM listings')
        c.execute('DELETE FROM listing_media')
        c.execute('DELETE FROM listing_meta')
        c.execute('DELETE FROM admin_media')
        c.execute('DELETE FROM admin_overrides')
        c.execute('DELETE FROM admin_reasons')
        c.execute('DELETE FROM admin_deleted_posts')
        audit(c,message.from_user.id,'clear_all',str(count))
    await state.clear()
    await message.answer(f'🧹 Каталог очищен: {count} объектов. История кодов сохранена. Исходный канал не изменён.',reply_markup=admin_keyboard())

@dp.message(F.text.in_({v['all'] for v in WORDS.values()}))
async def all_ads(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    await begin_catalog(message,state,lang)

@dp.callback_query(F.data == 'nextad')
async def next_ad(callback:CallbackQuery,state:FSMContext):
    await show_next_ad(callback.message,state,lang_for(callback.from_user.id));await callback.answer()

@dp.callback_query(F.data == 'contactad')
async def contact_ad(callback:CallbackQuery):
    await callback.message.answer(f'📞 <b>KEY HOUSE | TASHKENT</b>\n{escape(CONTACT_1)}\n{escape(CONTACT_2)}\n💬 {escape(CONTACT_LINK)}')
    await callback.answer()

@dp.callback_query(F.data == 'homead')
async def home_ad(callback:CallbackQuery,state:FSMContext):
    await state.clear()
    lang=lang_for(callback.from_user.id)
    await callback.message.answer(tr(lang,'💛 Спасибо, что выбрали <b>KEY HOUSE | TASHKENT</b>!\n\n🤝 Вы всегда можете положиться на нас. Мы рядом, и вы знаете, где нас быстро найти!\n\n🖤 🩶 <b><i>«Недвижимость, которую хочется назвать домом»</i></b> 🧡','💛 <b>KEY HOUSE | TASHKENT</b>ni tanlaganingiz uchun rahmat!\n\n🖤 <i>Uy deb atagingiz keladigan ko‘chmas mulk.</i>'),reply_markup=menu(lang))
    await callback.answer()

@dp.callback_query(F.data.startswith('view:'))
async def view_from_ad(callback:CallbackQuery,state:FSMContext):
    await state.clear();await state.update_data(view_code=callback.data.split(':')[1]);await state.set_state(Flow.view_name)
    lang=lang_for(callback.from_user.id)
    await callback.message.answer(tr(lang,'📅 <b>Запись на просмотр</b>\nОтправьте ваше имя, номер телефона и код объявления.\n\nКак к вам обращаться?','📅 <b>Ko‘rishga yozilish</b>\nIsmingiz, telefon raqamingiz va e’lon kodini yuboring.\n\nIsmingiz nima?'),reply_markup=back_kb(lang))
    await callback.answer()
@dp.message(F.text.in_({v['view'] for v in WORDS.values()}))
async def view_manual(message:Message,state:FSMContext):
    await state.clear();await state.set_state(Flow.view_name);lang=lang_for(message.from_user.id)
    await message.answer(tr(lang,'📅 Для записи отправьте имя, телефон и код объявления.\nКак к вам обращаться?','📅 Yozilish uchun ism, telefon va e’lon kodini yuboring.\nIsmingiz nima?'),reply_markup=back_kb(lang))
@dp.message(Flow.view_name)
async def view_name(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    if not message.text: return
    await state.update_data(view_name=message.text);await state.set_state(Flow.view_phone)
    await message.answer(tr(lang,'📞 Укажите номер телефона:','📞 Telefon raqamingizni kiriting:'),reply_markup=phone_kb(lang))
@dp.message(Flow.view_phone)
async def view_phone(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);phone=phone_of(message)
    if not phone:await message.answer(tr(lang,'Введите корректный номер.','To‘g‘ri raqamni kiriting.'));return
    await state.update_data(view_phone=phone);data=await state.get_data()
    if data.get('view_code'):await finish_view(message,state,data)
    else:
        await state.set_state(Flow.view_code)
        await message.answer(tr(lang,'🔢 Укажите код объявления (2–3 цифры):','🔢 E’lon kodini kiriting (2–3 raqam):'),reply_markup=back_kb(lang))
async def finish_view(message,state,data):
    lang=lang_for(message.from_user.id);code=str(data.get('view_code',''))
    with sqlite3.connect(DB) as c: valid=c.execute("SELECT 1 FROM listings WHERE code=? AND status='active'",(code,)).fetchone()
    if not valid:
        await state.set_state(Flow.view_code)
        await message.answer(tr(lang,'Код не найден. Введите действующий код объявления:','Kod topilmadi. To‘g‘ri e’lon kodini kiriting:'),reply_markup=back_kb(lang));return
    report=f'📅 <b>Запись на просмотр / Ko‘rish</b>\nКод: <b>№{escape(code)}</b>\nИмя: {escape(data["view_name"])}\nТелефон: {escape(data["view_phone"])}\n{client_telegram(message.from_user)}{listing_source_line(code)}'
    ok=await send_request(report,user_id=message.from_user.id);await state.clear()
    if ok:record_application(message.from_user.id,'view',code,data.get('view_name'),data.get('view_phone'))
    if ok:
        await message.answer(tr(lang,'💛 <b>Спасибо, что выбрали KEY HOUSE | TASHKENT!</b>\n\n✅ Ваша заявка на просмотр недвижимости успешно принята!\n\n📞 <b>Наш специалист свяжется с вами</b> по указанному номеру телефона, уточнит актуальность объекта и согласует удобное для вас время просмотра.\n\n⏳ <b>Ориентировочное время обратной связи — от 30 до 120 минут.</b>\n\n⚠️ Обратите внимание: время ожидания может меняться в зависимости от загруженности наших специалистов. Благодарим за ваше понимание и терпение! 🤝\n\n🏡 <b>KEY HOUSE — недвижимость, которую хочется назвать домом!</b>','💛 <b>KEY HOUSE | TASHKENT’ni tanlaganingiz uchun rahmat!</b>\n\n✅ Ko‘chmas mulkni ko‘rish uchun arizangiz muvaffaqiyatli qabul qilindi!\n\n📞 <b>Mutaxassisimiz siz bilan bog‘lanadi</b>, obyektning dolzarbligini aniqlaydi va ko‘rish uchun qulay vaqtni kelishadi.\n\n⏳ <b>Taxminiy bog‘lanish vaqti — 30 daqiqadan 120 daqiqagacha.</b>\n\n⚠️ Kutish vaqti mutaxassislarimizning ish yuklamasiga qarab o‘zgarishi mumkin. Tushunganingiz va sabringiz uchun rahmat! 🤝\n\n🏡 <b>KEY HOUSE — uy deb atagingiz keladigan ko‘chmas mulk!</b>'),reply_markup=kb([[tr(lang,'📞 Связаться с нами','📞 Biz bilan bog‘lanish')],[w(lang,'menu')]]))
    else:await receipt(message,lang,False)
@dp.message(Flow.view_code)
async def view_code(message:Message,state:FSMContext):
    code=(message.text or '').strip().lstrip('№# ')
    if not re.fullmatch(r'\d{2,3}',code):
        await message.answer(tr(lang_for(message.from_user.id),'Введите 2–3 цифры.','2–3 raqam kiriting.'));return
    await state.update_data(view_code=code);await finish_view(message,state,await state.get_data())

@dp.message(F.text.in_({v['offer'] for v in WORDS.values()}))
async def offer_menu(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.clear()
    await message.answer(tr(lang,
        '🖤 ✦ 💛 <b>ПРЕДЛОЖЕНИЕ | KEY HOUSE</b>\n━━━━━━━━━━━━━━━━━━\n\n🏡 Здесь вы можете предложить свой вариант недвижимости нашему агентству!\n\n🤝 <b>Вы риэлтор?</b> Хотите предложить объект, клиента или сотрудничать с KEY HOUSE? Перейдите в раздел «Для риэлторов».\n\n🔑 <b>Вы собственник?</b> Хотите разместить свою квартиру, дом или другую недвижимость? Выберите «Для собственников».\n\n💛 Мы внимательно относимся к каждому предложению. Выберите подходящий раздел ниже!',
        '🖤 ✦ 💛 <b>TAKLIF | KEY HOUSE</b>\n━━━━━━━━━━━━━━━━━━\n\n🏡 Bu yerda agentligimizga ko‘chmas mulkingizni taklif qilishingiz mumkin!\n\n🤝 <b>Rieltormisiz?</b> Mijoz yoki obyekt taklif qilish va hamkorlik uchun «Rieltorlar uchun» bo‘limini tanlang.\n\n🔑 <b>Mulk egasimisiz?</b> Uy yoki kvartirangizni joylashtirish uchun «Mulk egalari uchun» bo‘limini tanlang.\n\n💛 Har bir taklif biz uchun muhim!'),
        reply_markup=kb([[w(lang,'agents'),w(lang,'owners')],[w(lang,'menu')]]))

@dp.message(F.text.in_({v['owners'] for v in WORDS.values()}))
async def owners(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.clear()
    await state.update_data(source='Собственник',photos=[])
    await state.set_state(Flow.owner_photos)
    await message.answer(tr(lang,
        '🖤 ✦ 💛 <b>ДЛЯ СОБСТВЕННИКОВ</b>\n━━━━━━━━━━━━━━━━━━\n\n🏡 Хотите предложить свою недвижимость агентству KEY HOUSE? Мы рады вашему обращению!\n\n1️⃣ <b>Прикрепите от 1 до 10 фотографий</b> объекта.\n2️⃣ <b>Укажите количество комнат, тип постройки, этаж и краткое описание</b> недвижимости.\n\n📞 После этого мы попросим ваш телефон, имя и удобное время для звонка. Также можно оставить Telegram для связи.\n\n📸 <b>Начните с фотографий.</b> Когда закончите, нажмите «Готово».',
        '🖤 ✦ 💛 <b>MULK EGALARI UCHUN</b>\n━━━━━━━━━━━━━━━━━━\n\n🏡 KEY HOUSE agentligiga mulkingizni taklif qiling!\n\n1️⃣ Obyektning 1 tadan 10 tagacha suratini yuboring.\n2️⃣ Xonalar soni, bino turi, qavati va qisqacha tavsifini yozing.\n\n📞 Keyin telefon, ism, qo‘ng‘iroq uchun qulay vaqt va ixtiyoriy Telegram nomini so‘raymiz.\n\n📸 Avval suratlarni yuboring, so‘ng «Tayyor» tugmasini bosing.'),
        reply_markup=kb([[w(lang,'done')],[w(lang,'menu')]]))

@dp.message(Flow.owner_photos,F.photo)
async def owner_collect_photo(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);data=await state.get_data();photos=data.get('photos',[])
    if len(photos)>=10:
        await message.answer(tr(lang,'⚠️ Максимум 10 фотографий. Нажмите «Готово».','⚠️ Eng ko‘pi 10 ta surat. «Tayyor» tugmasini bosing.'));return
    photos.append(message.photo[-1].file_id);await state.update_data(photos=photos)
    await message.answer(tr(lang,f'📸 Принято фотографий: {len(photos)}/10',f'📸 Qabul qilindi: {len(photos)}/10'))

@dp.message(Flow.owner_photos)
async def owner_finish_photos(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    if message.text!=w(lang,'done'):
        await message.answer(tr(lang,'Отправьте фотографии или нажмите «Готово».','Suratlarni yuboring yoki «Tayyor» tugmasini bosing.'));return
    if not (await state.get_data()).get('photos'):
        await message.answer(tr(lang,'📸 Добавьте хотя бы одну фотографию.','📸 Kamida bitta surat qo‘shing.'));return
    await state.set_state(Flow.owner_details)
    await message.answer(tr(lang,'📝 Напишите количество комнат, тип постройки, этаж и краткое описание недвижимости одним сообщением:','📝 Xonalar soni, bino turi, qavat va qisqacha tavsifni bitta xabarda yozing:'),reply_markup=back_kb(lang))

@dp.message(Flow.owner_details)
async def owner_details(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    if not (message.text or '').strip():
        await message.answer(tr(lang,'Напишите описание текстом.','Tavsifni matn ko‘rinishida yozing.'));return
    await state.update_data(details=message.text.strip());await state.set_state(Flow.owner_phone)
    await message.answer(tr(lang,'📞 <b>Ваш контактный номер</b>\n\nНажмите «Отправить мой номер» или напишите номер телефона сообщением (например, +998 90 123 45 67).','📞 <b>Telefon raqamingiz</b>\n\n«Raqamimni yuborish» tugmasini bosing yoki raqamingizni matn bilan yuboring.'),reply_markup=phone_kb(lang))

@dp.message(Flow.owner_phone)
async def owner_phone(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);phone=phone_of(message)
    if not phone:
        await message.answer(tr(lang,'⚠️ Введите действительный телефон или воспользуйтесь кнопкой.','⚠️ To‘g‘ri telefon raqamini kiriting yoki tugmani bosing.'));return
    await state.update_data(phone=phone);await state.set_state(Flow.owner_name)
    await message.answer(tr(lang,'👤 Как к вам можно обращаться? Напишите ваше имя.','👤 Sizga qanday murojaat qilaylik? Ismingizni yozing.'),reply_markup=back_kb(lang))

@dp.message(Flow.owner_name)
async def owner_name(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    if not (message.text or '').strip():
        await message.answer(tr(lang,'Пожалуйста, напишите ваше имя.','Iltimos, ismingizni yozing.'));return
    await state.update_data(name=message.text.strip());await state.set_state(Flow.owner_time)
    await message.answer(tr(lang,'🕒 <b>В какое время вам удобно принимать звонки?</b>\n\nНапример: ежедневно с 10:00 до 18:00.','🕒 <b>Qaysi vaqtda qo‘ng‘iroq qilishimiz qulay?</b>\n\nMasalan: har kuni 10:00 dan 18:00 gacha.'),reply_markup=back_kb(lang))

@dp.message(Flow.owner_time)
async def owner_time(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    if not (message.text or '').strip():
        await message.answer(tr(lang,'Укажите удобное время для звонка.','Qo‘ng‘iroq uchun qulay vaqtni yozing.'));return
    await state.update_data(call_time=message.text.strip());await state.set_state(Flow.owner_telegram)
    await message.answer(tr(lang,'💬 <b>Дополнительный способ связи</b>\n\nЕсли вам удобно, оставьте свой Telegram @username, чтобы наши специалисты могли написать вам, если не получится дозвониться.\n\nЭто необязательно — можно нажать «Пропустить».','💬 <b>Qo‘shimcha aloqa</b>\n\nAgar telefon orqali bog‘lana olmasak, sizga yozishimiz uchun Telegram @username qoldirishingiz mumkin.\n\nBu majburiy emas — «O‘tkazib yuborish» tugmasini bosing.'),reply_markup=kb([[w(lang,'skip')],[w(lang,'menu')]]))

@dp.message(Flow.owner_telegram)
async def owner_telegram(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);username=(message.text or '').strip()
    if username!=w(lang,'skip') and not re.fullmatch(r'@[A-Za-z0-9_]{5,32}',username):
        await message.answer(tr(lang,'Введите @username Telegram или нажмите «Пропустить».','Telegram @username kiriting yoki «O‘tkazib yuborish» tugmasini bosing.'));return
    data=await state.get_data();telegram=username if username!=w(lang,'skip') else 'Не указан'
    report=(f'🏡 <b>Предложение собственника | KEY HOUSE</b>\n'
            f'📝 Описание: {escape(data.get("details","—"))}\n'
            f'📞 Телефон: {escape(data.get("phone","—"))}\n'
            f'👤 Имя: {escape(data.get("name","—"))}\n'
            f'🕒 Удобное время: {escape(data.get("call_time","—"))}\n'
            f'💬 Telegram: {escape(telegram)}\n'
            f'📸 Фото: {len(data.get("photos",[]))}\n'
            f'{client_telegram(message.from_user)}')
    ok=await send_request(report,data.get('photos',[]),user_id=message.from_user.id);await state.clear();await receipt(message,lang,ok,offer=True)
    if ok:record_application(message.from_user.id,'owner',name=data.get('name'),phone=data.get('phone'))

@dp.message(F.text.in_({v['agents'] for v in WORDS.values()}))
async def agents(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.clear()
    await message.answer(tr(lang,'🖤 ✦ 💛 <b>ДЛЯ РИЭЛТОРОВ</b>\n━━━━━━━━━━━━━━━━━━\n\nПриветствуем! Хотите пользоваться ботом или предложить вариант? Опишите ваше предложение, укажите имя и номер телефона. Мы рассмотрим его в кратчайшие сроки и свяжемся с вами. Также вы можете связаться с нами во вкладке «О нас».','🖤 ✦ 💛 <b>RIELTORLAR UCHUN</b>\n━━━━━━━━━━━━━━━━━━\n\nXush kelibsiz! Botdan foydalanmoqchimisiz yoki obyekt taklif qilmoqchimisiz? Taklifingizni qisqacha yozing, ismingiz va telefoningizni kiriting. Biz tez orada ko‘rib chiqib, siz bilan bog‘lanamiz. «Biz haqimizda» bo‘limi orqali ham bog‘lanishingiz mumkin.'),reply_markup=kb([[w(lang,'plus')],[w(lang,'menu')]]))
@dp.message(F.text.in_({v['plus'] for v in WORDS.values()}))
async def agent_offer(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    await state.clear();await state.update_data(source='Плюсовой вариант')
    await state.set_state(Flow.plus_details)
    await message.answer(tr(lang,'🖤 ✦ 💛 <b>KEY HOUSE | TASHKENT</b>\n\n🤝 Приветствуем вас! Благодарим за интерес к сотрудничеству с нашим агентством.\n\n➕ <b>ПЛЮСОВОЙ ВАРИАНТ</b>\n\nОтправьте предложение по образцу:\n\n🏡 <b>Что предлагаете:</b> клиента или объект недвижимости?\n📝 <b>Описание:</b> краткие сведения о клиенте или объекте, район, условия и стоимость.\n👤 <b>Имя:</b> ваше имя.\n📞 <b>Телефон:</b> контактный номер.\n💬 <b>Telegram:</b> @username для связи.\n\n✍️ Отправьте все данные одним сообщением. Все контактные поля обязательны.\n\n💛 🩶 <b><i>«Недвижимость, которую хочется назвать домом»</i></b> 🧡','🖤 ✦ 💛 <b>KEY HOUSE | TASHKENT</b>\n\n🤝 Hamkorlikka qiziqishingiz uchun rahmat!\n\n➕ <b>PLYUSLI VARIANT</b>\n\n🏡 Taklif: mijozmi yoki ko‘chmas mulkmi?\n📝 Qisqacha ma’lumot: hudud, shartlar va narx.\n👤 Ismingiz.\n📞 Telefon raqamingiz.\n💬 Telegram: @username.\n\n✍️ Barcha ma’lumotlarni bitta xabarda yuboring. Aloqa ma’lumotlari majburiy.'),reply_markup=back_kb(lang))

@dp.message(Flow.plus_details)
async def plus_details(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);t=(message.text or '').strip()
    if not re.search(r'@\w{5,32}',t) or not re.search(r'\+?\d[\d\s()\-]{6,}',t) or len(t)<45:
        await message.answer(tr(lang,'⚠️ Заполните образец полностью: клиент или недвижимость, описание, имя, телефон и @username Telegram.','⚠️ Taklif turi, tavsif, ism, telefon va Telegram @username ni kiriting.'));return
    ok=await send_request('➕ <b>Плюсовой вариант | KEY HOUSE</b>\n'+escape(t)+f'\n{client_telegram(message.from_user)}',user_id=message.from_user.id)
    await state.clear();await receipt(message,lang,ok)

@dp.message(F.text.in_({v['coop'] for v in WORDS.values()}))
async def cooperation(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.clear();await state.set_state(Flow.cooperation)
    await message.answer(tr(lang,'🤝 Сообщите, пожалуйста, какое сотрудничество рассматриваете? Плюсовой вариант или помощь с поиском?\n\nОпишите предложение, добавьте имя и номер телефона одним сообщением.','🤝 Qanday hamkorlikni ko‘rib chiqyapsiz? Plyusli variantmi yoki qidiruvda yordammi?\n\nTaklif, ism va telefon raqamingizni bitta xabarda yuboring.'),reply_markup=kb([[tr(lang,'➕ Плюсовой вариант','➕ Plyusli variant'),tr(lang,'🔎 Помощь с поиском','🔎 Qidiruvda yordam')],[w(lang,'menu')]]))
@dp.message(Flow.cooperation)
async def cooperation_send(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);txt=(message.text or message.caption or '').strip()
    if txt in ('➕ Плюсовой вариант','➕ Plyusli variant','🔎 Помощь с поиском','🔎 Qidiruvda yordam'):
        await state.update_data(coop_type=txt)
        await message.answer(tr(lang,'Теперь напишите имя, телефон и детали предложения:','Endi ism, telefon va taklif tafsilotlarini yozing:'));return
    if not txt: return
    data=await state.get_data()
    ok=await send_request(f'🤝 <b>Сотрудничество</b>\nТип: {escape(data.get("coop_type","—"))}\nСообщение: {escape(txt)}\n{client_telegram(message.from_user)}',user_id=message.from_user.id)
    await state.clear();await receipt(message,lang,ok)

@dp.message(Flow.offer_details)
async def offer_details(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.update_data(details=message.text or '—');await state.set_state(Flow.offer_name)
    await message.answer(tr(lang,'Как к вам обращаться?','Ismingiz nima?'),reply_markup=back_kb(lang))
@dp.message(Flow.offer_name)
async def offer_name(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.update_data(name=message.text or '—');await state.set_state(Flow.offer_phone)
    await message.answer(tr(lang,'📞 Укажите номер телефона:','📞 Telefon raqamingizni kiriting:'),reply_markup=phone_kb(lang))
@dp.message(Flow.offer_phone)
async def offer_phone(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);phone=phone_of(message)
    if not phone:await message.answer(tr(lang,'Введите корректный номер.','To‘g‘ri raqam kiriting.'));return
    await state.update_data(phone=phone,photos=[]);await state.set_state(Flow.offer_photos)
    await message.answer(tr(lang,'📷 Пришлите от 1 до 10 фотографий. Затем нажмите «Готово».','📷 1 tadan 10 tagacha surat yuboring. Keyin «Tayyor» tugmasini bosing.'),reply_markup=kb([[w(lang,'done')],[w(lang,'menu')]]))

@dp.message(Flow.photos,F.photo)
@dp.message(Flow.offer_photos,F.photo)
async def collect_photo(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);data=await state.get_data();photos=data.get('photos',[])
    if len(photos)>=10:
        await message.answer(tr(lang,'Можно отправить максимум 10 фото. Нажмите «Готово».','Ko‘pi bilan 10 ta surat. «Tayyor» tugmasini bosing.'));return
    photos.append(message.photo[-1].file_id);await state.update_data(photos=photos)
    await message.answer(tr(lang,f'📷 Фото {len(photos)}/10 принято.','📷 {len(photos)}/10 surat qabul qilindi.'))

@dp.message(Flow.photos)
@dp.message(Flow.offer_photos)
async def finish_photos(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);current=await state.get_state();offer=current==Flow.offer_photos.state
    if message.text not in (w(lang,'done'),w(lang,'skip')):
        await message.answer(tr(lang,'Отправьте фото или нажмите «Готово».','Surat yuboring yoki «Tayyor» tugmasini bosing.'));return
    data=await state.get_data();photos=data.get('photos',[])
    if offer and not photos:
        await message.answer(tr(lang,'Для предложения требуется минимум 1 фотография.','Taklif uchun kamida 1 ta surat kerak.'));return
    if offer:
        report=f'📩 <b>Новое предложение</b>\nОт: {escape(data.get("source","—"))}\nОписание: {escape(data.get("details","—"))}\nИмя: {escape(data.get("name","—"))}\nТелефон: {escape(data.get("phone","—"))}\nФото: {len(photos)}\n{client_telegram(message.from_user)}'
    else:
        report=f'📥 <b>Новая заявка KEY HOUSE</b>\nТип: {escape(data.get("category","—"))}\nПостройка: {escape(data.get("building","—"))}\nКомнаты: {escape(data.get("rooms","—"))}\nРайон: {escape(data.get("district","—"))}\nАдрес: {escape(data.get("address","—"))}\nЦена: {escape(data.get("price","—"))}\nОписание: {escape(data.get("details","—"))}\nИмя: {escape(data.get("name","—"))}\nТелефон: {escape(data.get("phone","—"))}\n{client_telegram(message.from_user)}'
    ok=await send_request(report,photos,user_id=message.from_user.id);await state.clear();await receipt(message,lang,ok,offer)
    if ok:record_application(message.from_user.id,'offer' if offer else data.get('category','property'),name=data.get('name'),phone=data.get('phone'))

@dp.message(F.text.in_({v['more'] for v in WORDS.values()}))
async def more(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);await state.clear()
    await message.answer(tr(lang,'🖤 ✦ 💛 <b>ДОПОЛНИТЕЛЬНО</b>\n━━━━━━━━━━━━━━━━━━\nВыберите раздел:','🖤 ✦ 💛 <b>QO‘SHIMCHA</b>\n━━━━━━━━━━━━━━━━━━\nBo‘limni tanlang:'),reply_markup=kb([[w(lang,'about')],[w(lang,'rules')],[w(lang,'menu')]]))
@dp.message(F.text.in_({v['rules'] for v in WORDS.values()}))
async def rules_from_menu(message:Message):
    await show_rules(message,lang_for(message.from_user.id))

@dp.message(F.text.in_({v['about'] for v in WORDS.values()}))
async def about(message:Message):
    lang=lang_for(message.from_user.id)
    await message.answer(tr(lang,'🖤 ✦ 💛 <b>KEY HOUSE | TASHKENT</b>\n━━━━━━━━━━━━━━━━━━\n🏡 🩶 <b><i>«Недвижимость, которую хочется назвать домом»</i></b> 🧡\n\n👑 KEY HOUSE — агентство недвижимости в Ташкенте, где каждый запрос важен, а поиск жилья становится понятным и комфортным.\n\n🏠 Помогаем подобрать квартиры и дома для покупки.\n🔑 Ищем варианты аренды с учётом ваших пожеланий.\n📤 Сопровождаем собственников при продаже и сдаче недвижимости.\n📅 Организуем просмотры и помогаем связаться со специалистами.\n🤝 Ценим доверие, открытость и индивидуальный подход.\n\n💛 Мы рядом, когда нужен надёжный помощник в вопросах недвижимости.','🖤 ✦ 💛 <b>KEY HOUSE | TASHKENT</b>\n━━━━━━━━━━━━━━━━━━\n🏡 <i>Uy deb atagingiz keladigan ko‘chmas mulk.</i>\n\n👑 KEY HOUSE — Toshkentdagi ko‘chmas mulk agentligi. Biz uy qidirishni qulay va tushunarli qilishga intilamiz.\n\n🏠 Uy sotib olishda yordam beramiz.\n🔑 Ijara variantlarini tanlaymiz.\n📤 Sotish va ijaraga berishda mulk egalariga ko‘maklashamiz.\n📅 Ko‘rish uchrashuvlarini tashkil qilamiz.\n🤝 Ishonch va individual yondashuvni qadrlaymiz.')+f'\n\n📞 {escape(CONTACT_1)}\n📞 {escape(CONTACT_2)}',reply_markup=kb([[w(lang,'back')],[w(lang,'menu')]]))

@dp.message(F.text.in_({'📞 Связаться с нами','📞 Biz bilan bog‘lanish'}))
async def contact_direct(message:Message):
    await message.answer(f'📞 <b>KEY HOUSE | TASHKENT</b>\n{escape(CONTACT_1)}\n{escape(CONTACT_2)}\n💬 {escape(CONTACT_LINK)}')


@dp.edited_channel_post()
async def edited_channel_listing(message:Message):
    if LISTINGS_CHAT_ID and message.chat.id == LISTINGS_CHAT_ID:
        store_listing(message.chat.id,message.message_id,message.text or message.caption or '',message.media_group_id,message.photo[-1].file_id if message.photo else None)

@dp.edited_message(F.chat.id == LISTINGS_CHAT_ID)
async def edited_group_listing(message:Message):
    if LISTINGS_CHAT_ID:
        store_listing(message.chat.id,message.message_id,message.text or message.caption or '',message.media_group_id,message.photo[-1].file_id if message.photo else None)

@dp.message(F.chat.id == LISTINGS_CHAT_ID)
async def capture_group(message:Message):
    if LISTINGS_CHAT_ID:store_listing(message.chat.id,message.message_id,message.text or message.caption or '',message.media_group_id,message.photo[-1].file_id if message.photo else None)
@dp.channel_post()
async def capture_channel(message:Message):
    if LISTINGS_CHAT_ID and message.chat.id==LISTINGS_CHAT_ID:store_listing(message.chat.id,message.message_id,message.text or message.caption or '',message.media_group_id,message.photo[-1].file_id if message.photo else None)
@dp.message(F.text.in_({v['profile'] for v in WORDS.values()}))
async def my_profile(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);name,phone,last=profile(message.from_user.id)
    await state.clear()
    await message.answer(f'🖤💛 <b>{tr(lang,"Мой профиль","Profilim")}</b>\n\n👤 {escape(name or "—")}\n📞 {escape(phone or "—")}\n🌐 {"Русский" if lang=="ru" else "O‘zbekcha"}',reply_markup=kb([[w(lang,'history')],[tr(lang,'✏️ Изменить имя','✏️ Ismni o‘zgartirish'),tr(lang,'📞 Изменить номер','📞 Raqamni o‘zgartirish')],[tr(lang,'🔎 Продолжить поиск','🔎 Qidiruvni davom ettirish')],[w(lang,'menu')]]))

@dp.message(F.text.in_({v['history'] for v in WORDS.values()}))
async def my_history(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    await state.clear();await state.update_data(history_offset=0)
    await history_page(message,state,lang)

async def history_page(message,state,lang):
    data=await state.get_data();offset=data.get('history_offset',0)
    with sqlite3.connect(DB) as c:
        rows=c.execute('SELECT kind,code,created_at,repeated FROM applications WHERE user_id=? ORDER BY id DESC LIMIT 3 OFFSET ?',(message.from_user.id,offset)).fetchall()
    if not rows:await message.answer(tr(lang,'📋 Пока нет отправленных заявок.','📋 Hozircha arizalar yo‘q.'),reply_markup=menu(lang));return
    lines=[f'{offset+i+1}. {escape(kind)} · {escape(date)}'+(f' · №{escape(code)}' if code else '')+(' 🔁' if repeated else '') for i,(kind,code,date,repeated) in enumerate(rows[:3])]
    rows_kb=[]
    rows_kb.append([w(lang,'profile')])
    await message.answer('📋 <b>'+tr(lang,'Мои заявки','Arizalarim')+'</b>\n\n'+'\n'.join(lines),reply_markup=kb(rows_kb))

@dp.message(F.text.in_({'📂 Показать ещё','📂 Yana ko‘rsatish'}))
async def history_more(message:Message,state:FSMContext):
    data=await state.get_data();await state.update_data(history_offset=data.get('history_offset',0)+3)
    await history_page(message,state,lang_for(message.from_user.id))

@dp.message(F.text.in_({'✏️ Изменить имя','✏️ Ismni o‘zgartirish','📞 Изменить номер','📞 Raqamni o‘zgartirish'}))
async def edit_profile(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id)
    field='name' if message.text.startswith('✏️') else 'phone'
    await state.set_state(Flow.profile_edit);await state.update_data(profile_field=field)
    await message.answer(tr(lang,'Введите новое имя или телефон:','Yangi ism yoki telefonni kiriting:'),reply_markup=phone_kb(lang) if field=='phone' else back_kb(lang))

@dp.message(Flow.profile_edit)
async def profile_edit_value(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);data=await state.get_data();field=data.get('profile_field')
    val=phone_of(message) if field=='phone' else (message.text or '').strip()[:100]
    if not val:await message.answer(tr(lang,'⚠️ Проверьте введённые данные.','⚠️ Ma’lumotlarni tekshiring.'));return
    save_profile(message.from_user.id,**{field:val});await state.clear()
    await my_profile(message,state)

@dp.message(F.text.in_({'🔎 Продолжить поиск','🔎 Qidiruvni davom ettirish'}))
async def resume_search(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);last=profile(message.from_user.id)[2]
    if not last:await message.answer(tr(lang,'Сохранённого поиска пока нет.','Saqlangan qidiruv yo‘q.'));return
    data=json.loads(last);await state.clear();await state.update_data(**data,catalog=True,ad_index=0)
    await state.set_state(Flow.catalog_results);await show_next_ad(message,state,lang)

@dp.callback_query(F.data == 'prevad')
async def prev_ad(callback:CallbackQuery,state:FSMContext):
    data=await state.get_data();await state.update_data(ad_index=max(0,data.get('ad_index',1)-2))
    await show_next_ad(callback.message,state,lang_for(callback.from_user.id));await callback.answer()

@dp.callback_query(F.data.startswith('interest:'))
async def interest_begin(callback:CallbackQuery,state:FSMContext):
    code=callback.data.split(':',1)[1];lang=lang_for(callback.from_user.id)
    with sqlite3.connect(DB) as c:ok=c.execute('SELECT 1 FROM listings WHERE code=? AND status=?',(code,'active')).fetchone()
    if not ok:await callback.answer(tr(lang,'Объект недоступен','Obyekt mavjud emas'),show_alert=True);return
    await state.clear();await state.update_data(interest_code=code)
    await state.set_state(Flow.interest_name)
    saved=profile(callback.from_user.id)[0]
    await callback.message.answer(tr(lang,f'💛 Объект №{code}. Как к вам обращаться?'+(f'\nСохранённое имя: {saved}' if saved else ''),f'💛 №{code}. Ismingiz nima?'),reply_markup=kb([[saved]] if saved else [[w(lang,'menu')]]))
    await callback.answer()

@dp.message(Flow.interest_name)
async def interest_name(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);name=(message.text or '').strip()
    if not name:return
    await state.update_data(interest_name=name);await state.set_state(Flow.interest_phone)
    saved=profile(message.from_user.id)[1]
    await message.answer(tr(lang,'📞 Введите телефон:','📞 Telefonni kiriting:'),reply_markup=kb([[saved]] if saved else []) if saved else phone_kb(lang))

@dp.message(Flow.interest_phone)
async def interest_phone(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);phone=phone_of(message)
    if not phone:await message.answer(tr(lang,'Введите номер Узбекистана.','O‘zbekiston raqamini kiriting.'));return
    await state.update_data(interest_phone=phone);await state.set_state(Flow.interest_comment)
    await message.answer(tr(lang,'📝 Комментарий (необязательно):','📝 Izoh (ixtiyoriy):'),reply_markup=kb([[w(lang,'skip')],[w(lang,'menu')]]))

@dp.message(Flow.interest_comment)
async def interest_comment(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);comment=(message.text or '').strip()
    await state.update_data(interest_comment='—' if comment==w(lang,'skip') else comment)
    await preview_interest(message,state)

async def preview_interest(message,state):
    lang=lang_for(message.from_user.id);data=await state.get_data();code=data.get('interest_code')
    with sqlite3.connect(DB) as c:repeat=c.execute('SELECT 1 FROM applications WHERE user_id=? AND kind=? AND code=?',(message.from_user.id,'interest',code)).fetchone()
    await state.set_state(Flow.interest_confirm)
    await message.answer(f'💛 <b>{tr(lang,"Проверьте заявку","Arizani tekshiring")}</b>\n№{escape(code)}\n👤 {escape(data.get("interest_name","—"))}\n📞 {escape(data.get("interest_phone","—"))}\n📝 {escape(data.get("interest_comment","—"))}'+(f'\n\n🔁 {tr(lang,"Вы уже обращались по этому объекту. Повторить?","Bu obyekt bo‘yicha avval murojaat qilgansiz. Takrorlaysizmi?")}' if repeat else ''),reply_markup=kb([[w(lang,'confirm')],[w(lang,'edit'),w(lang,'cancel')]]))

@dp.message(Flow.interest_confirm)
async def interest_confirm(message:Message,state:FSMContext):
    lang=lang_for(message.from_user.id);t=message.text;data=await state.get_data()
    if t==w(lang,'cancel'):await state.clear();await message.answer(tr(lang,'Заявка отменена.','Ariza bekor qilindi.'),reply_markup=menu(lang));return
    if t==w(lang,'edit'):await state.set_state(Flow.interest_name);await message.answer(tr(lang,'Введите имя заново:','Ismni qayta kiriting:'));return
    if t!=w(lang,'confirm'):return
    code=data['interest_code']
    with sqlite3.connect(DB) as c:valid=c.execute('SELECT 1 FROM listings WHERE code=? AND status=?',(code,'active')).fetchone()
    if not valid:await message.answer(tr(lang,'Объект уже недоступен.','Obyekt endi mavjud emas.'));await state.clear();return
    report=f'💛 <b>Заинтересовал объект</b>\n№{escape(code)}\nИмя: {escape(data["interest_name"])}\nТелефон: {escape(data["interest_phone"])}\nКомментарий: {escape(data.get("interest_comment","—"))}\n{client_telegram(message.from_user)}{listing_source_line(code)}'
    ok=await send_request(report,user_id=message.from_user.id)
    if ok:record_application(message.from_user.id,'interest',code,data['interest_name'],data['interest_phone'])
    await state.clear();await receipt(message,lang,ok)

@dp.message()
async def fallback(message:Message):
    lang=lang_for(message.from_user.id)
    await message.answer(tr(lang,'Выберите действие в меню или введите /start для смены языка.','Menyudan tanlang yoki tilni almashtirish uchun /start yozing.'),reply_markup=menu(lang))

async def health(request):
    return web.json_response({'service': 'KEY HOUSE', 'status': 'running'})

async def main():
    init_db()
    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', '10000'))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f'KEY HOUSE: HTTP server on port {port}; starting Telegram polling', flush=True)
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
