# NoutBook — noutbuk do‘koni Telegram bot + Mini App

Loyiha `bot.py` ichida Telegram bot va zamonaviy responsive Mini App’ni birlashtiradi. Mahsulotlar va buyurtmalar SQLite’da saqlanadi. Dastlabki demo mahsulotlari va narxlari birinchi ishga tushishda avtomatik qo‘shiladi; ommaga chiqarishdan oldin ularni o‘zingizning haqiqiy mahsulot, narx va rasmlaringiz bilan yangilang.

## Nimalar bor?

- Zamonaviy Mini App: mahsulotlar katalogi, qidiruv, toifalar, saralash, tavsiya yorliqlari va mahsulot tafsilotlari.
- Savat, miqdorni o‘zgartirish, sevimlilar, buyurtma shakli va buyurtmalar tarixi.
- Buyurtma yaratilganda administratorlarga Telegram xabari.
- Admin panel: yangi buyurtmalar, holatni tasdiqlash/bekor qilish/yetkazilmoqda deb belgilash.
- `/addproduct` bilan bot ichidan mahsulot qo‘shish.
- Telegram Mini App `initData` imzosini tekshirish; narx va zaxira server tomonda qayta tekshiriladi.
- Lokal rejimda bot long polling orqali ishlaydi; Render’da webhook avtomatik sozlanadi.
- O‘zbek so‘mi (UZS) bilan narxlar. Onlayn to‘lov integratsiyasi qo‘shilmagan; to‘lov shartlari operator bilan kelishiladi.

## 1. Kompyuterda ishga tushirish (Windows)

Python 3.10 yoki undan yangisini o‘rnating: https://www.python.org/downloads/ . O‘rnatish paytida **Add Python to PATH** belgisini yoqing.

1. ZIP’ni oching va shu papkada terminal/PowerShell oching.
2. Kutubxonalarni o‘rnating:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. BotFather bergan tokenni o‘rnating (tokenni hech kimga yubormang):

   ```powershell
   $env:BOT_TOKEN="123456:ABC..."
   ```

4. O‘z Telegram ID’ingizni `ADMIN_IDS` sifatida kiriting. Bot ishga tushgach `/id` yuborib ID’ingizni ko‘rishingiz mumkin; birinchi ishga tushirish uchun avval token bilan botni yoqing va ID’ni olib, keyin botni qayta ishga tushiring:

   ```powershell
   $env:ADMIN_IDS="123456789"
   ```

5. Bot va Mini App preview’ni ishga tushiring:

   ```powershell
   python bot.py
   ```

6. Brauzerda `http://127.0.0.1:8000` manzilini ochib Mini App dizaynini tekshiring. Telegram’da botga `/start` yuboring.

**Eslatma:** Telegram ichidagi Mini App URL’i ommaviy HTTPS bo‘lishi kerak. `localhost` faqat o‘z kompyuteringizdagi brauzer preview’i uchun ishlaydi. Mini App’ni Telegram ichida sinash uchun Render’ga joylang yoki HTTPS tunnel (`ngrok` kabi) ishlatib, o‘sha HTTPS URL’ni `APP_URL` qilib o‘rnating (PowerShell’da, ishga tushirishdan oldin: `$env:APP_URL="https://sizning-tunnel-manzilingiz"`).

## 2. GitHub + Render’da ishga tushirish

1. GitHub’da yangi repository yarating.
2. ZIP ichidagi `bot.py`, `requirements.txt`, `render.yaml` va `README.md` fayllarini repository’ga yuklang. `shop.db`, `.venv` va tokenlarni repository’ga yuklamang.
3. Render’ga kiring: https://render.com/ . **New + → Blueprint** (yoki repository’dan Web Service) orqali shu repository’ni ulang. `render.yaml` build/start buyruqlarini oldindan beradi.
4. Render servisining Environment bo‘limida quyidagilarni kiriting:
   - `BOT_TOKEN` — BotFather tokeni.
   - `ADMIN_IDS` — administrator Telegram ID’lari. Bir nechtasi bo‘lsa vergul bilan, masalan `12345,67890`.
5. Deploy tugashini kuting. Render HTTPS URL beradi. Bot ishga tushganda shu URL’ni Mini App manzili va Telegram menu tugmasi sifatida avtomatik sozlaydi. Botga `/start` yuboring va **Do‘konni ochish** tugmasini bosing.

Bot tokenini kod ichiga yozmang va GitHub’ga joylamang. Agar token repository’ga tasodifan tushib qolsa, BotFather orqali uni almashtiring.

## 3. Admin ishlatishi

- `/id` — Telegram ID’ingizni ko‘rsatadi.
- `/admin` — mahsulot soni va oxirgi buyurtmalarni ko‘rsatadi.
- `/addproduct` — ketma-ket nom, toifa, narx, tavsif va rasm URL’ini so‘rab, mahsulot qo‘shadi. Rasm bo‘lmasa `-` yuboring.
- `/products` — mahsulot ID’lari va holatlarini ko‘rish.
- `/setprice ID NARX` — mahsulot narxini o‘zgartirish.
- `/setstock ID MIQDOR` — ombordagi qoldiqni o‘zgartirish.
- `/hideproduct ID` va `/showproduct ID` — mahsulotni katalogdan yashirish/qaytarish.
- Buyurtma tafsilotida tugmalar orqali holatni o‘zgartiring. Mijoz Telegram’da buyurtma bergan bo‘lsa, status xabari ham oladi.
- `/cancel` — mahsulot qo‘shish jarayonini bekor qiladi.

## 4. Ixtiyoriy sozlamalar

- `SHOP_NAME` — do‘kon nomi (default: `NoutBook`).
- `CONTACT_PHONE` — aloqa telefoni.
- `DELIVERY_TEXT` — yetkazib berish haqida botdagi matn.
- `APP_URL` — maxsus ommaviy HTTPS URL. Render’da bo‘sh qolsa, `RENDER_EXTERNAL_URL` ishlatiladi.
- `DATABASE_PATH` — SQLite fayl manzili.
- `LOCAL_WEB_PORT` — lokal Mini App preview porti (default `8000`).

## Ma’lumotlar saqlanishi haqida muhim eslatma

Lokal rejimda ma’lumotlar loyiha papkasidagi `shop.db` faylida saqlanadi. Render’ning bepul xizmatida fayl tizimi vaqtinchalik bo‘lishi mumkin; qayta deploy yoki restart bo‘lsa, buyurtmalar hamda admin kiritgan mahsulotlar yo‘qolishi ehtimoli bor. Haqiqiy do‘kon uchun Render’da pullik **persistent disk** qo‘shib, mount path’ni `/var/data` qilib, `DATABASE_PATH=/var/data/shop.db` o‘rnating. Muqobil yo‘l — PostgreSQL’ga ulash. Render bepul xizmati harakatsizlikda uxlab qolishi ham mumkin; 24/7 barqaror ishlash uchun doimiy ishlaydigan hosting rejasini tanlang.

## Qisqa diagnostika

- `BOT_TOKEN topilmadi`: terminalda `BOT_TOKEN` environment variable o‘rnatilmagan.
- Admin buyruqlari ishlamaydi: `ADMIN_IDS` qiymatiga o‘z Telegram ID’ingizni kiriting; Render’da environment qiymatini saqlab, servisingizni qayta ishga tushiring.
- Mini App Telegram’da ochilmaydi: Render service `Live` ekanini, URL `https://` bilan boshlanishini va botga `/start` yuborganingizni tekshiring.
- Bot lokalda javob bermasa: shu bot tokenidan boshqa jarayon foydalnayotgan bo‘lishi mumkin. Bir token bilan bir vaqtning o‘zida faqat bitta polling jarayoni ishlating; Render webhook rejimi va lokal polling rejimini bir vaqtda aralashtirmang.
- Rasm ko‘rinmasa: mahsulot uchun to‘g‘ridan-to‘g‘ri HTTPS rasm URL ishlating.
