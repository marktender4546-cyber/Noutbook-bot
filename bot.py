"""NoutBook — Telegram laptop shop bot + Mini App.

Local: BOT_TOKEN=... python bot.py
Render: set BOT_TOKEN and ADMIN_IDS; the service automatically uses webhook mode.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import json
import logging
import os
import secrets
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    Message,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
    BotCommand,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

# ------------------------------- Configuration ------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SHOP_NAME = os.getenv("SHOP_NAME", "NoutBook").strip() or "NoutBook"
APP_URL = (os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}
CONTACT_PHONE = os.getenv("CONTACT_PHONE", "").strip()
DELIVERY_TEXT = os.getenv(
    "DELIVERY_TEXT",
    "Toshkent bo‘ylab yetkazib berish odatda 1 ish kuni ichida. Boshqa hududlarga yetkazish muddati operator tomonidan aniqlashtiriladi. Buyurtma tasdiqlangach, siz bilan bog‘lanamiz.",
)
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "shop.db")))
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip() or secrets.token_urlsafe(24)
LOCAL_WEB_PORT = int(os.getenv("LOCAL_WEB_PORT", "8000"))
IS_RENDER = os.getenv("RENDER", "").lower() == "true"
WEBHOOK_PATH = "/webhook"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("noutbook")

bot: Bot | None = None
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI(title=f"{SHOP_NAME} Mini App", docs_url=None, redoc_url=None)

# ------------------------------- Product data -------------------------------

SEED_PRODUCTS = [
    {
        "title": "Lenovo IdeaPad Slim 3",
        "category": "O‘qish va ofis",
        "price": 6_499_000,
        "description": "Kundalik ishlar, o‘qish va videodarslar uchun qulay noutbuk. 15.6\" ekran, tezkor SSD va ixcham korpus.",
        "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=1000&q=85",
        "badge": "Ommabop",
        "stock": 12,
    },
    {
        "title": "ASUS VivoBook 15",
        "category": "O‘qish va ofis",
        "price": 7_299_000,
        "description": "Yengil va zamonaviy dizayn. Ofis dasturlari, masofaviy ta’lim va kundalik vazifalar uchun mos.",
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=1000&q=85",
        "badge": "Yangi",
        "stock": 8,
    },
    {
        "title": "Apple MacBook Air",
        "category": "Premium",
        "price": 14_999_000,
        "description": "Yupqa, jim va ixcham premium noutbuk. Safar, ijodiy ish va samarali kundalik foydalanish uchun.",
        "image_url": "https://images.unsplash.com/photo-1511385348-a52b4a160dc2?auto=format&fit=crop&w=1000&q=85",
        "badge": "Premium",
        "stock": 5,
    },
    {
        "title": "HP 15s",
        "category": "O‘qish va ofis",
        "price": 6_899_000,
        "description": "Katta ekran va qulay klaviatura bilan uy va ofisdagi kundalik vazifalar uchun amaliy tanlov.",
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?auto=format&fit=crop&w=1000&q=85",
        "badge": "Yaxshi narx",
        "stock": 10,
    },
    {
        "title": "Acer Aspire 5",
        "category": "O‘qish va ofis",
        "price": 7_799_000,
        "description": "Ko‘p vazifali ishlash uchun muvozanatli model. Ish, ta’lim va uy foydalanishiga mos.",
        "image_url": "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?auto=format&fit=crop&w=1000&q=85",
        "badge": "Tavsiya",
        "stock": 7,
    },
    {
        "title": "Lenovo LOQ Gaming",
        "category": "Gaming",
        "price": 12_499_000,
        "description": "O‘yinlar, grafik ishlar va yuqori yuklamali vazifalar uchun mo‘ljallangan kuchli noutbuk.",
        "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?auto=format&fit=crop&w=1000&q=85",
        "badge": "Gaming",
        "stock": 4,
    },
    {
        "title": "Dell Inspiron 14",
        "category": "Premium",
        "price": 8_999_000,
        "description": "Kundalik ish uchun ishonchli va ixcham format. Uydan yoki ofisdan ishlaydiganlar uchun.",
        "image_url": "https://images.unsplash.com/photo-1593642634367-d91a135587b5?auto=format&fit=crop&w=1000&q=85",
        "badge": "Ixcham",
        "stock": 6,
    },
    {
        "title": "ASUS TUF Gaming F15",
        "category": "Gaming",
        "price": 13_499_000,
        "description": "O‘yin va resurs talab qiladigan dasturlar uchun mo‘ljallangan mustahkam seriya.",
        "image_url": "https://images.unsplash.com/photo-1593642702821-c8da6771f0c6?auto=format&fit=crop&w=1000&q=85",
        "badge": "Kuchli",
        "stock": 3,
    },
]

# -------------------------------- Mini App ----------------------------------

MINI_APP_HTML = r'''<!doctype html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#f7f9fc">
  <title>__SHOP_NAME__ — Noutbuklar do‘koni</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root{--blue:#2563eb;--blue2:#1d4ed8;--ink:#101828;--muted:#667085;--line:#e6eaf0;--bg:#f7f9fc;--card:#fff;--green:#16a34a;--radius:20px;--shadow:0 8px 30px rgba(20,40,80,.07)}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;-webkit-font-smoothing:antialiased}button,input,textarea,select{font:inherit}button{cursor:pointer}button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #93c5fd;outline-offset:2px}.app{max-width:1100px;margin:0 auto;padding:0 16px 112px}.topbar{display:flex;align-items:center;justify-content:space-between;padding:18px 0 14px}.brand{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:850;letter-spacing:-.7px}.logo{width:40px;height:40px;background:linear-gradient(145deg,#3377ff,#1744bd);color:#fff;display:grid;place-items:center;border-radius:13px;box-shadow:0 7px 16px #2563eb35}.logo svg{width:23px}.location{background:#fff;border:1px solid var(--line);border-radius:999px;padding:9px 12px;color:#475467;font-size:12px;font-weight:650}.hero{position:relative;overflow:hidden;border-radius:26px;padding:25px 23px 21px;min-height:230px;background:linear-gradient(120deg,#102c68 0%,#1d4ed8 60%,#5c8cf7 100%);color:white;box-shadow:0 18px 35px #1d4ed826}.hero:after{content:"";position:absolute;width:240px;height:240px;right:-60px;top:-80px;border-radius:50%;border:1px solid #ffffff30;box-shadow:0 0 0 22px #ffffff0b,0 0 0 50px #ffffff08}.eyebrow{font-size:11px;font-weight:800;letter-spacing:1.7px;text-transform:uppercase;color:#c7d9ff}.hero h1{font-size:30px;line-height:1.12;letter-spacing:-1.3px;max-width:420px;margin:12px 0 10px}.hero p{margin:0;color:#d9e6ff;font-size:13px;max-width:310px;line-height:1.5}.hero-bottom{display:flex;align-items:center;justify-content:space-between;margin-top:20px;gap:10px}.hero-btn{border:0;border-radius:12px;background:#fff;color:#1744bd;font-weight:800;padding:12px 16px;font-size:12px}.hero-note{font-size:11px;color:#dce7ff}.hero-laptop{position:absolute;right:4%;bottom:8px;width:42%;max-width:300px;filter:drop-shadow(0 14px 12px #00143b50);transform:rotate(-4deg);z-index:1;opacity:.94}.search{margin:19px 0 15px;position:relative}.search input{width:100%;height:49px;border:1px solid #e3e8f0;background:#fff;border-radius:15px;padding:0 48px 0 44px;color:var(--ink);box-shadow:0 3px 12px #14213d05}.search .s-icon{position:absolute;left:15px;top:14px;color:#98a2b3}.search .clear{position:absolute;right:9px;top:8px;border:0;border-radius:10px;width:32px;height:32px;background:#f1f5f9;color:#64748b;display:none}.section-head{display:flex;align-items:end;justify-content:space-between;margin:24px 0 13px}.section-head h2{font-size:19px;letter-spacing:-.5px;margin:0}.section-head span{font-size:11px;color:#98a2b3}.chips{display:flex;gap:8px;overflow:auto;padding:1px 0 8px;scrollbar-width:none}.chips::-webkit-scrollbar{display:none}.chip{white-space:nowrap;border:1px solid var(--line);border-radius:999px;background:#fff;color:#475467;padding:9px 13px;font-size:12px;font-weight:700}.chip.active{background:#e9f0ff;border-color:#c9d9ff;color:#1d4ed8}.sortline{display:flex;align-items:center;justify-content:space-between;margin:8px 0 12px}.sortline small{color:var(--muted);font-size:12px}.sortline select{border:1px solid var(--line);background:white;color:#344054;padding:8px 10px;border-radius:11px;font-size:12px}.products{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.product{background:#fff;border:1px solid #edf0f5;border-radius:18px;overflow:hidden;min-width:0;position:relative;box-shadow:0 4px 18px #0b1d3907;transition:transform .15s}.product:active{transform:scale(.985)}.photo{height:145px;background:#f1f4f9;position:relative;display:grid;place-items:center;overflow:hidden}.photo img{width:100%;height:100%;object-fit:cover;mix-blend-mode:multiply}.badge{position:absolute;left:9px;top:9px;background:#fff;border:1px solid #edf0f5;border-radius:8px;padding:5px 7px;color:#344054;font-size:9px;font-weight:800}.heart{position:absolute;right:8px;top:8px;width:31px;height:31px;border:0;background:#ffffffed;border-radius:50%;font-size:17px;display:grid;place-items:center;color:#98a2b3}.heart.on{color:#ef476f}.product-info{padding:12px 11px 13px}.category{color:#8490a2;font-size:10px;font-weight:700}.product h3{font-size:13px;line-height:1.3;min-height:34px;margin:5px 0 8px;letter-spacing:-.2px}.price{font-size:14px;font-weight:850;letter-spacing:-.3px}.price-caption{font-size:10px;color:#98a2b3;margin-top:2px}.card-bottom{display:flex;gap:7px;align-items:center;margin-top:11px}.details{border:1px solid #e5eaf2;background:white;color:#344054;border-radius:10px;padding:9px 10px;font-size:11px;font-weight:750;flex:1}.add{width:38px;height:36px;border:0;background:var(--blue);color:white;border-radius:11px;font-size:20px;font-weight:400;box-shadow:0 5px 12px #2563eb30}.add:active{background:var(--blue2)}.empty{grid-column:1/-1;text-align:center;padding:38px 20px;color:var(--muted);background:#fff;border:1px dashed #d6deea;border-radius:18px}.empty strong{display:block;font-size:15px;color:var(--ink);margin-bottom:5px}.trust{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:24px}.trustbox{border:1px solid var(--line);border-radius:15px;background:#fff;padding:13px 10px;text-align:center}.trustbox .emoji{font-size:21px}.trustbox b{display:block;font-size:11px;margin-top:7px}.trustbox small{color:var(--muted);font-size:9px;display:block;margin-top:4px;line-height:1.4}.footer{margin:24px 0 0;text-align:center;color:#98a2b3;font-size:11px;line-height:1.6}.bottomnav{position:fixed;z-index:10;bottom:0;left:0;right:0;padding:9px 12px calc(9px + env(safe-area-inset-bottom));background:#fffffff2;border-top:1px solid #e8edf4;backdrop-filter:blur(16px)}.navinner{max-width:650px;margin:auto;display:grid;grid-template-columns:repeat(4,1fr);gap:5px}.navbtn{border:0;background:transparent;color:#98a2b3;border-radius:13px;padding:7px 2px 5px;display:flex;align-items:center;justify-content:center;gap:4px;flex-direction:column;font-size:10px;font-weight:700;position:relative}.navbtn .navicon{font-size:19px;line-height:1.1}.navbtn.active{color:var(--blue);background:#eef4ff}.count{position:absolute;top:1px;left:calc(50% + 4px);background:#ef4444;color:white;border-radius:10px;min-width:16px;height:16px;padding:0 4px;font-size:9px;display:none;align-items:center;justify-content:center}.screen{display:none}.screen.active{display:block}.cart-list{display:grid;gap:10px}.cartrow{display:flex;gap:12px;background:#fff;border:1px solid var(--line);padding:10px;border-radius:16px;align-items:center}.cartrow img{width:78px;height:72px;object-fit:cover;border-radius:12px;background:#f2f5f9}.cartmain{flex:1;min-width:0}.cartmain b{display:block;font-size:13px;line-height:1.3}.cartmain small{display:block;margin-top:5px;color:var(--muted);font-size:11px}.qty{display:flex;align-items:center;gap:8px;margin-top:8px}.qty button{width:26px;height:25px;border:1px solid var(--line);border-radius:8px;background:#fff;color:#344054}.qty span{font-size:12px;font-weight:800}.summary{background:#fff;border:1px solid var(--line);border-radius:17px;margin-top:13px;padding:16px}.sumline{display:flex;justify-content:space-between;gap:10px;color:var(--muted);font-size:12px;margin:7px 0}.sumline.total{font-size:15px;font-weight:850;color:var(--ink);padding-top:11px;border-top:1px solid var(--line);margin-top:12px}.primary{width:100%;margin-top:14px;border:0;border-radius:13px;background:var(--blue);color:#fff;padding:14px 16px;font-weight:800;font-size:13px;box-shadow:0 7px 15px #2563eb24}.secondary{border:1px solid var(--line);background:#fff;color:#344054;border-radius:12px;padding:11px 14px;font-weight:750}.formgrid{display:grid;gap:12px}.field label{display:block;font-size:12px;font-weight:750;margin:0 0 6px;color:#344054}.field input,.field textarea,.field select{width:100%;border:1px solid #dce3ed;border-radius:12px;background:#fff;padding:12px 13px;font-size:13px;color:var(--ink)}.field textarea{resize:vertical;min-height:76px}.modalback{display:none;position:fixed;inset:0;background:#0f172a75;z-index:30;align-items:flex-end;justify-content:center;padding:0}.modalback.show{display:flex}.modal{background:#f8fafc;width:100%;max-width:650px;max-height:92dvh;overflow:auto;border-radius:24px 24px 0 0;padding:16px 18px calc(24px + env(safe-area-inset-bottom));box-shadow:0 -20px 60px #0f172a30;animation:slide .18s ease-out}.modaltop{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:15px}.modaltop h2{font-size:18px;margin:0;letter-spacing:-.5px}.xbtn{border:0;background:#e8edf5;color:#475467;width:34px;height:34px;border-radius:50%;font-size:20px}.detailpic{width:100%;max-height:230px;object-fit:contain;background:#fff;border:1px solid var(--line);border-radius:16px;margin-bottom:14px}.detaildesc{font-size:13px;color:#667085;line-height:1.6}.detailprice{font-size:22px;font-weight:900;margin:12px 0}.status{display:inline-flex;border-radius:20px;padding:6px 9px;font-size:10px;font-weight:800;background:#eef4ff;color:#2456c4}.ordercard{background:#fff;border:1px solid var(--line);padding:15px;border-radius:16px;margin-bottom:10px}.orderhead{display:flex;align-items:start;justify-content:space-between;gap:8px}.orderhead b{font-size:13px}.ordercard p{color:var(--muted);font-size:11px;line-height:1.6;margin:10px 0 0}.toast{position:fixed;z-index:60;left:50%;bottom:94px;transform:translate(-50%,20px);opacity:0;pointer-events:none;background:#101828;color:white;padding:12px 16px;border-radius:12px;font-size:12px;font-weight:750;max-width:90%;text-align:center;transition:.2s;box-shadow:var(--shadow)}.toast.show{opacity:1;transform:translate(-50%,0)}.spinner{width:25px;height:25px;border:3px solid #dbeafe;border-top-color:var(--blue);border-radius:50%;animation:spin .7s linear infinite;margin:20px auto}.hint{font-size:11px;line-height:1.5;color:#98a2b3;margin-top:10px}.homeall{display:flex;justify-content:space-between;align-items:center;gap:12px}.textlink{color:var(--blue);font-size:12px;font-weight:800;border:0;background:transparent;padding:0}@keyframes spin{to{transform:rotate(360deg)}}@keyframes slide{from{transform:translateY(18px);opacity:.5}to{transform:translateY(0);opacity:1}}
    @media(min-width:620px){.app{padding:0 24px 120px}.hero{padding:34px;min-height:260px}.hero h1{font-size:39px}.hero p{font-size:14px}.hero-laptop{width:40%;right:5%;bottom:10px}.products{grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.photo{height:180px}.product-info{padding:15px}.product h3{font-size:14px}.price{font-size:15px}.trustbox{padding:17px}.modalback{align-items:center;padding:16px}.modal{border-radius:24px}}
    @media(min-width:900px){.products{grid-template-columns:repeat(4,minmax(0,1fr))}.photo{height:175px}.hero{min-height:285px}.hero-laptop{width:35%;max-width:380px}}
    @media(max-width:380px){.app{padding-left:12px;padding-right:12px}.hero h1{font-size:26px}.hero-laptop{right:-7%;width:44%;opacity:.78}.hero-note{max-width:105px}.photo{height:122px}.product-info{padding:10px 9px}.product h3{font-size:12px}.price{font-size:13px}}
  </style>
</head>
<body>
<div class="app">
  <header class="topbar"><div class="brand"><div class="logo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="12" rx="2"/><path d="M2 19h20M9 16l-1 3m7-3 1 3"/></svg></div><span>__SHOP_NAME__</span></div><div class="location">📍 O‘zbekiston</div></header>
  <main id="homeScreen" class="screen active">
    <section class="hero"><div class="eyebrow">TEXNOLOGIYA SIZGA YAQIN</div><h1>Yangi noutbukingiz shu yerda.</h1><p>O‘qish, ish va o‘yin uchun noutbuklar — qulay xarid, ishonchli xizmat.</p><div class="hero-bottom"><button class="hero-btn" onclick="goTo('catalog')">Katalogni ko‘rish <span>↗</span></button><span class="hero-note">✓ Buyurtma berish oson</span></div><img class="hero-laptop" src="https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=850&q=85" alt="Noutbuk rasmi" onerror="this.style.display='none'"></section>
    <div class="search"><span class="s-icon">⌕</span><input id="searchHome" placeholder="Noutbuk nomini qidiring..." autocomplete="off"><button id="clearSearch" class="clear" onclick="clearSearch()">×</button></div>
    <div class="section-head"><h2>Toifalar</h2><span>O‘zingizga mosini tanlang</span></div>
    <div class="chips" id="homeChips"></div>
    <div class="section-head"><h2>Tavsiya etilganlar</h2><button class="textlink" onclick="goTo('catalog')">Barchasi →</button></div>
    <div class="products" id="featuredProducts"><div class="spinner"></div></div>
    <div class="trust"><div class="trustbox"><div class="emoji">🚚</div><b>Yetkazib berish</b><small>Kelishilgan manzilga</small></div><div class="trustbox"><div class="emoji">📋</div><b>Buyurtma nazorati</b><small>Holatni botda kuzating</small></div><div class="trustbox"><div class="emoji">💬</div><b>Yordam</b><small>Savollaringizga javob</small></div></div>
    <div class="footer">__SHOP_NAME__ · Noutbuklar do‘koni<br>To‘lov buyurtma tasdiqlangandan so‘ng kelishiladi.</div>
  </main>
  <main id="catalogScreen" class="screen"><div class="section-head"><h2>Katalog</h2><span id="catalogCount">Yuklanmoqda...</span></div><div class="search"><span class="s-icon">⌕</span><input id="searchCatalog" placeholder="Model, brend yoki toifa..." autocomplete="off"><button id="clearCatalog" class="clear" onclick="clearCatalogSearch()">×</button></div><div class="chips" id="catalogChips"></div><div class="sortline"><small id="catalogResults">Noutbuklar</small><select id="sortSelect" aria-label="Saralash"><option value="popular">Tavsiya etilgan</option><option value="priceAsc">Narx: arzon → qimmat</option><option value="priceDesc">Narx: qimmat → arzon</option><option value="name">Nomi bo‘yicha</option></select></div><div class="products" id="allProducts"><div class="spinner"></div></div></main>
  <main id="cartScreen" class="screen"><div class="section-head"><h2>Savatim</h2><span id="cartCountText">0 ta mahsulot</span></div><div id="cartContent"></div></main>
  <main id="ordersScreen" class="screen"><div class="section-head"><h2>Buyurtmalarim</h2><span>Buyurtma holati</span></div><div id="ordersContent"><div class="empty"><strong>Buyurtmalarni ko‘rish</strong>Telegram ichida ochilganda buyurtmalaringiz shu yerda ko‘rinadi.</div></div><button class="secondary" onclick="loadOrders()">↻ Yangilash</button></main>
</div>
<nav class="bottomnav"><div class="navinner"><button class="navbtn active" data-screen="home" onclick="goTo('home')"><span class="navicon">⌂</span><span>Bosh sahifa</span></button><button class="navbtn" data-screen="catalog" onclick="goTo('catalog')"><span class="navicon">▦</span><span>Katalog</span></button><button class="navbtn" data-screen="cart" onclick="goTo('cart')"><span class="navicon">🛒</span><span>Savat</span><span id="cartBadge" class="count">0</span></button><button class="navbtn" data-screen="orders" onclick="goTo('orders')"><span class="navicon">▤</span><span>Buyurtmalar</span></button></div></nav>
<div class="modalback" id="modalBack" onclick="backdropClose(event)"><div class="modal" id="modal"><div class="modaltop"><h2 id="modalTitle">Mahsulot</h2><button class="xbtn" onclick="closeModal()">×</button></div><div id="modalBody"></div></div></div><div id="toast" class="toast"></div>
<script>
const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
if(tg){tg.ready();tg.expand();try{tg.setHeaderColor('#f7f9fc');tg.setBackgroundColor('#f7f9fc');}catch(e){}}
const money = n => new Intl.NumberFormat('uz-UZ').format(Number(n||0)).replace(/\u00a0/g,' ') + " so‘m";
const esc = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtDate = s => {try{return new Date(s.replace(' ','T')+'Z').toLocaleString('uz-UZ',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})}catch(e){return s}};
let products=[],cart={},favorites=new Set(JSON.parse(localStorage.getItem('noutbook-favs')||'[]')),category='Barchasi',catalogQuery='',homeQuery='',sort='popular',toastTimer;
const initData = tg && tg.initData ? tg.initData : '';
function toast(t){const el=document.getElementById('toast');el.textContent=t;el.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),2600);if(tg&&tg.HapticFeedback)try{tg.HapticFeedback.notificationOccurred('success')}catch(e){}}
function goTo(name){document.querySelectorAll('.screen').forEach(e=>e.classList.remove('active'));document.getElementById(name+'Screen').classList.add('active');document.querySelectorAll('.navbtn').forEach(e=>e.classList.toggle('active',e.dataset.screen===name));if(name==='cart')renderCart();if(name==='orders')loadOrders();if(name==='catalog')renderCatalog();window.scrollTo({top:0,behavior:'smooth'});}
function categories(){return ['Barchasi',...new Set(products.map(p=>p.category).filter(Boolean))]}
function drawChips(target,selected,onPick){document.getElementById(target).innerHTML=categories().map(c=>{const arg=esc(JSON.stringify(c));return `<button class="chip ${c===selected?'active':''}" onclick="${onPick}(${arg})">${esc(c)}</button>`}).join('')}
function productCard(p){return `<article class="product"><div class="photo" onclick="showProduct(${p.id})"><img src="${esc(p.image_url||'')}" alt="${esc(p.title)}" loading="lazy" onerror="this.style.display='none'"><span class="badge">${esc(p.badge||'Noutbuk')}</span><button class="heart ${favorites.has(p.id)?'on':''}" aria-label="Sevimlilar" onclick="event.stopPropagation();toggleFavorite(${p.id})">${favorites.has(p.id)?'♥':'♡'}</button></div><div class="product-info"><div class="category">${esc(p.category)}</div><h3>${esc(p.title)}</h3><div class="price">${money(p.price)}</div><div class="price-caption">${p.stock>0?'Omborda: '+p.stock+' dona':'Hozir mavjud emas'}</div><div class="card-bottom"><button class="details" onclick="showProduct(${p.id})">Batafsil</button><button class="add" aria-label="Savatga qo‘shish" ${p.stock>0?'':'disabled'} onclick="addToCart(${p.id})">${p.stock>0?'+':'×'}</button></div></div></article>`}
function filtered(){let list=products.filter(p=>category==='Barchasi'||p.category===category);const q=(catalogQuery||homeQuery).trim().toLowerCase();if(q)list=list.filter(p=>(p.title+' '+p.category+' '+p.description).toLowerCase().includes(q));if(sort==='priceAsc')list.sort((a,b)=>a.price-b.price);if(sort==='priceDesc')list.sort((a,b)=>b.price-a.price);if(sort==='name')list.sort((a,b)=>a.title.localeCompare(b.title));return list}
function renderHome(){drawChips('homeChips',category,'pickCategory');let items=products.filter(p=>p.stock>0).slice(0,4);if(homeQuery)items=products.filter(p=>(p.title+' '+p.category).toLowerCase().includes(homeQuery.toLowerCase())).slice(0,4);document.getElementById('featuredProducts').innerHTML=items.length?items.map(productCard).join(''):'<div class="empty"><strong>Mahsulot topilmadi</strong>Boshqa so‘z bilan qidirib ko‘ring.</div>';}
function renderCatalog(){drawChips('catalogChips',category,'pickCategory');const list=filtered();document.getElementById('catalogCount').textContent=products.length+' ta mahsulot';document.getElementById('catalogResults').textContent=list.length+' ta natija';document.getElementById('allProducts').innerHTML=list.length?list.map(productCard).join(''):'<div class="empty"><strong>Hech narsa topilmadi</strong>Qidiruv yoki toifa tanlovini o‘zgartirib ko‘ring.</div>';}
function pickCategory(c){category=c;renderHome();renderCatalog();goTo('catalog')}
function toggleFavorite(id){if(favorites.has(id))favorites.delete(id);else favorites.add(id);localStorage.setItem('noutbook-favs',JSON.stringify([...favorites]));renderHome();renderCatalog();toast(favorites.has(id)?'Sevimlilarga qo‘shildi':'Sevimlilardan olindi')}
function addToCart(id){cart[id]=(cart[id]||0)+1;updateBadge();toast('Savatga qo‘shildi');if(tg&&tg.HapticFeedback)try{tg.HapticFeedback.impactOccurred('light')}catch(e){}}
function updateBadge(){let n=Object.values(cart).reduce((a,b)=>a+b,0),el=document.getElementById('cartBadge');el.textContent=n;el.style.display=n?'flex':'none';document.getElementById('cartCountText').textContent=n+' ta mahsulot'}
function showProduct(id){let p=products.find(x=>x.id===id);if(!p)return;document.getElementById('modalTitle').textContent=p.title;document.getElementById('modalBody').innerHTML=`<img class="detailpic" src="${esc(p.image_url||'')}" alt="${esc(p.title)}" onerror="this.style.display='none'"><span class="status">${esc(p.badge||p.category)}</span><div class="detailprice">${money(p.price)}</div><div class="detaildesc">${esc(p.description)}</div><p class="hint">Toifasi: ${esc(p.category)} · Mavjud: ${p.stock} dona</p><button class="primary" onclick="addToCart(${p.id});closeModal()">🛒 Savatga qo‘shish</button>`;openModal()}
function openModal(){document.getElementById('modalBack').classList.add('show');document.body.style.overflow='hidden'}function closeModal(){document.getElementById('modalBack').classList.remove('show');document.body.style.overflow=''}function backdropClose(e){if(e.target.id==='modalBack')closeModal()}
function clearCartItem(id){delete cart[id];updateBadge();renderCart()}
function changeQty(id,d){cart[id]=(cart[id]||0)+d;if(cart[id]<=0)delete cart[id];updateBadge();renderCart()}
function renderCart(){updateBadge();const keys=Object.keys(cart).filter(id=>cart[id]>0),root=document.getElementById('cartContent');if(!keys.length){root.innerHTML='<div class="empty"><div style="font-size:30px;margin-bottom:8px">🛒</div><strong>Savatingiz hozircha bo‘sh</strong>Katalogdan o‘zingizga yoqqan noutbukni tanlang.<br><button class="primary" onclick="goTo(\'catalog\')">Katalogga o‘tish</button></div>';return}let total=0;const rows=keys.map(k=>{const p=products.find(x=>x.id===Number(k));if(!p)return '';total+=p.price*cart[k];return `<div class="cartrow"><img src="${esc(p.image_url||'')}" alt="" onerror="this.style.display='none'"><div class="cartmain"><b>${esc(p.title)}</b><small>${money(p.price)}</small><div class="qty"><button onclick="changeQty(${p.id},-1)">−</button><span>${cart[k]}</span><button onclick="changeQty(${p.id},1)">+</button></div></div></div>`}).join('');root.innerHTML=`<div class="cart-list">${rows}</div><div class="summary"><div class="sumline"><span>Mahsulotlar</span><span>${keys.reduce((n,k)=>n+cart[k],0)} dona</span></div><div class="sumline"><span>Yetkazib berish</span><span>Kelishiladi</span></div><div class="sumline total"><span>Jami</span><span>${money(total)}</span></div><button class="primary" onclick="checkout()">Buyurtmani rasmiylashtirish →</button><div class="hint">To‘lov va yetkazib berish shartlarini operator buyurtma tasdiqlanganda kelishadi.</div></div>`}
function checkout(){if(!Object.keys(cart).length){toast('Savatingiz bo‘sh');return}document.getElementById('modalTitle').textContent='Buyurtma rasmiylashtirish';document.getElementById('modalBody').innerHTML=`<form id="checkoutForm" class="formgrid"><div class="field"><label for="customerName">Ism familiya *</label><input id="customerName" name="customerName" autocomplete="name" required maxlength="100" placeholder="Ismingiz" value="${esc(tg?.initDataUnsafe?.user?.first_name||'')}"></div><div class="field"><label for="phone">Telefon raqami *</label><input id="phone" name="phone" type="tel" autocomplete="tel" required maxlength="30" placeholder="+998 90 123 45 67"></div><div class="field"><label for="address">Yetkazib berish manzili *</label><textarea id="address" name="address" required maxlength="500" placeholder="Viloyat, shahar, ko‘cha, uy"></textarea></div><div class="field"><label for="notes">Izoh (ixtiyoriy)</label><textarea id="notes" name="notes" maxlength="500" placeholder="Qo‘shimcha ma’lumot"></textarea></div><div class="summary"><div class="sumline"><span>Jami</span><strong>${money(Object.keys(cart).reduce((s,k)=>s+(products.find(p=>p.id===Number(k))?.price||0)*cart[k],0))}</strong></div><div class="hint">Hozircha to‘lov integratsiyasi yo‘q. Buyurtma operator tomonidan tasdiqlanadi.</div></div><button class="primary" id="submitOrder" type="submit">✓ Buyurtmani yuborish</button></form>`;openModal();document.getElementById('checkoutForm').addEventListener('submit',submitOrder)}
async function submitOrder(e){e.preventDefault();const btn=document.getElementById('submitOrder');btn.disabled=true;btn.textContent='Yuborilmoqda...';const form=new FormData(e.target);const payload={initData,customerName:form.get('customerName').trim(),phone:form.get('phone').trim(),address:form.get('address').trim(),notes:form.get('notes').trim(),items:Object.entries(cart).map(([id,quantity])=>({id:Number(id),quantity}))};try{const r=await fetch('/api/order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await r.json();if(!r.ok)throw new Error(data.detail||'Buyurtma yuborilmadi');cart={};updateBadge();closeModal();document.getElementById('modalTitle').textContent='Buyurtma qabul qilindi';document.getElementById('modalBody').innerHTML=`<div style="text-align:center;padding:15px 4px 5px"><div style="font-size:52px">✅</div><h3>Rahmat, buyurtmangiz qabul qilindi!</h3><p class="detaildesc">Buyurtma raqami: <b>#${data.order_id}</b><br>Operatorimiz tez orada siz bilan bog‘lanadi.</p><button class="primary" onclick="closeModal();goTo('orders')">Buyurtmalarim</button></div>`;openModal();toast('Buyurtma yuborildi');if(tg&&tg.HapticFeedback)try{tg.HapticFeedback.notificationOccurred('success')}catch(e){}}catch(err){toast(err.message||'Xatolik yuz berdi');btn.disabled=false;btn.textContent='✓ Buyurtmani yuborish'}}
async function loadOrders(){const root=document.getElementById('ordersContent');if(!initData){root.innerHTML='<div class="empty"><strong>Telegram ichidan oching</strong>Buyurtma tarixini ko‘rish uchun Mini App’ni Telegram bot menyusidan oching.</div>';return}root.innerHTML='<div class="spinner"></div>';try{const r=await fetch('/api/orders?initData='+encodeURIComponent(initData));const data=await r.json();if(!r.ok)throw new Error(data.detail||'Ma’lumot olinmadi');if(!data.length){root.innerHTML='<div class="empty"><strong>Hali buyurtma yo‘q</strong>Birinchi noutbukingizni tanlab buyurtma bering.</div>';return}root.innerHTML=data.map(o=>`<article class="ordercard"><div class="orderhead"><b>Buyurtma #${o.id}</b><span class="status">${esc(o.status_label)}</span></div><p>${fmtDate(o.created_at)}<br>${o.items.map(i=>esc(i.title)+' × '+i.quantity).join('<br>')}<br><b style="color:#101828">Jami: ${money(o.total)}</b></p></article>`).join('')}catch(e){root.innerHTML='<div class="empty"><strong>Yuklab bo‘lmadi</strong>Internetni tekshirib, qaytadan urinib ko‘ring.</div>'}}
function clearSearch(){homeQuery='';document.getElementById('searchHome').value='';document.getElementById('clearSearch').style.display='none';renderHome()}
function clearCatalogSearch(){catalogQuery='';document.getElementById('searchCatalog').value='';document.getElementById('clearCatalog').style.display='none';renderCatalog()}
document.getElementById('searchHome').addEventListener('input',e=>{homeQuery=e.target.value;document.getElementById('clearSearch').style.display=homeQuery?'block':'none';renderHome()});
document.getElementById('searchCatalog').addEventListener('input',e=>{catalogQuery=e.target.value;document.getElementById('clearCatalog').style.display=catalogQuery?'block':'none';renderCatalog()});
document.getElementById('sortSelect').addEventListener('change',e=>{sort=e.target.value;renderCatalog()});
async function init(){try{const r=await fetch('/api/products');products=await r.json();renderHome();renderCatalog();updateBadge()}catch(e){document.getElementById('featuredProducts').innerHTML='<div class="empty"><strong>Ulanish amalga oshmadi</strong>Sahifani yangilang.</div>';document.getElementById('allProducts').innerHTML=''}}
init();
</script>
</body></html>'''

# --------------------------------- Database ---------------------------------

def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 20000")
    return conn


def init_db() -> None:
    conn = connect_db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                price INTEGER NOT NULL CHECK(price > 0),
                description TEXT NOT NULL DEFAULT '',
                image_url TEXT NOT NULL DEFAULT '',
                badge TEXT NOT NULL DEFAULT '',
                stock INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                items_json TEXT NOT NULL,
                total INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_orders_telegram_id ON orders(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            conn.executemany(
                """INSERT INTO products(title,category,price,description,image_url,badge,stock)
                   VALUES(:title,:category,:price,:description,:image_url,:badge,:stock)""",
                SEED_PRODUCTS,
            )
        conn.commit()
    finally:
        conn.close()


def price_text(value: int | float) -> str:
    return f"{int(value):,}".replace(",", " ") + " so‘m"


def status_label(status: str) -> str:
    return {
        "new": "Yangi",
        "confirmed": "Tasdiqlandi",
        "shipped": "Yetkazilmoqda",
        "cancelled": "Bekor qilindi",
    }.get(status, status)


def all_products(active_only: bool = True) -> list[dict[str, Any]]:
    conn = connect_db()
    try:
        query = "SELECT * FROM products" + (" WHERE active=1" if active_only else "") + " ORDER BY id DESC"
        return [dict(row) for row in conn.execute(query).fetchall()]
    finally:
        conn.close()


def product_count() -> int:
    conn = connect_db()
    try:
        return int(conn.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0])
    finally:
        conn.close()


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in ADMIN_IDS


def validate_init_data(init_data: str) -> dict[str, Any] | None:
    """Validate Telegram Web App initData; returns its user payload if trusted."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        values = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = values.pop("hash", "")
        if not received_hash:
            return None
        auth_date = int(values.get("auth_date", "0"))
        if auth_date <= 0 or time.time() - auth_date > 24 * 60 * 60 or auth_date > time.time() + 60:
            return None
        data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            return None
        user_json = values.get("user")
        return json.loads(user_json) if user_json else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


async def notify_admins(text: str) -> None:
    if bot is None:
        return
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as exc:  # admin may not have started the bot yet
            log.warning("Admin notification failed for %s: %s", admin_id, exc)


def order_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    buttons = []
    if status == "new":
        buttons.append(InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"adm_status:{order_id}:confirmed"))
        buttons.append(InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"adm_status:{order_id}:cancelled"))
    elif status == "confirmed":
        buttons.append(InlineKeyboardButton(text="🚚 Yetkazilmoqda", callback_data=f"adm_status:{order_id}:shipped"))
        buttons.append(InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"adm_status:{order_id}:cancelled"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [])


# -------------------------------- Bot UI ------------------------------------

class ProductAdd(StatesGroup):
    title = State()
    category = State()
    price = State()
    description = State()
    image_url = State()


def main_keyboard() -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    if APP_URL.startswith("https://"):
        rows.append([KeyboardButton(text="🛍 Do‘konni ochish", web_app=WebAppInfo(url=APP_URL))])
    rows.extend(
        [
            [KeyboardButton(text="📦 Buyurtmalarim"), KeyboardButton(text="🚚 Yetkazib berish")],
            [KeyboardButton(text="☎️ Aloqa"), KeyboardButton(text="ℹ️ Biz haqimizda")],
        ]
    )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    name = html.escape(message.from_user.first_name if message.from_user else "do‘st")
    text = (
        f"<b>Assalomu alaykum, {name}! 👋</b>\n\n"
        f"<b>{html.escape(SHOP_NAME)}</b> — noutbuklar do‘koni. O‘qish, ish va o‘yin uchun mos modelni tanlang.\n\n"
        "🛍 Katalogni ko‘ring\n🔎 Mahsulotlarni qidiring\n🛒 Savatga qo‘shing\n📦 Buyurtmani kuzating\n\n"
    )
    if APP_URL.startswith("https://"):
        text += "Quyidagi <b>Do‘konni ochish</b> tugmasini bosing."
    else:
        text += "Mini App’ni Telegram ichida ochish uchun loyihani HTTPS manzilga joylang (Render’da avtomatik sozlanadi). Lokal ko‘rish: <code>http://127.0.0.1:8000</code>."
    await message.answer(text, reply_markup=main_keyboard())


@dp.message(Command("id"))
async def id_handler(message: Message) -> None:
    await message.answer(f"Telegram ID: <code>{message.from_user.id}</code>\nAdmin qilish uchun shu ID’ni <code>ADMIN_IDS</code> sozlamasiga kiriting.")


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "<b>Bot buyruqlari</b>\n/start — bosh menyu\n/id — Telegram ID\n/help — yordam\n\n"
        "Adminlar uchun:\n/admin — buyurtmalar va statistika\n/addproduct — yangi mahsulot qo‘shish\n/cancel — joriy amalni bekor qilish",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Amal bekor qilindi.", reply_markup=main_keyboard())


@dp.message(F.text == "🚚 Yetkazib berish")
async def delivery_handler(message: Message) -> None:
    await message.answer(f"<b>🚚 Yetkazib berish</b>\n\n{html.escape(DELIVERY_TEXT)}")


@dp.message(F.text == "☎️ Aloqa")
async def contact_handler(message: Message) -> None:
    contact = f"\nTelefon: {html.escape(CONTACT_PHONE)}" if CONTACT_PHONE else "\nTelefon raqami do‘kon administratorining sozlamasiga bog‘liq."
    await message.answer(f"<b>☎️ Aloqa</b>\n\nSavollaringiz bo‘lsa shu bot orqali yozing. Admin buyurtmangiz bo‘yicha siz bilan bog‘lanadi.{contact}")


@dp.message(F.text == "ℹ️ Biz haqimizda")
async def about_handler(message: Message) -> None:
    await message.answer(
        f"<b>{html.escape(SHOP_NAME)} haqida</b>\n\n"
        "Biz turli ehtiyojlar uchun noutbuklarni bir joyda tanlashga yordam beramiz. Katalogdan model va narxni ko‘ring, savatga qo‘shing va buyurtma qoldiring.\n\n"
        "To‘lov onlayn amalga oshirilmaydi; to‘lov va yetkazib berish shartlari operator bilan kelishiladi."
    )


@dp.message(F.text == "📦 Buyurtmalarim")
async def my_orders_handler(message: Message) -> None:
    user_id = message.from_user.id
    conn = connect_db()
    try:
        rows = conn.execute(
            "SELECT * FROM orders WHERE telegram_id=? ORDER BY id DESC LIMIT 10", (user_id,)
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        await message.answer("Sizda hozircha buyurtmalar yo‘q. Mini App katalogidan noutbuk tanlab, buyurtma berishingiz mumkin.", reply_markup=main_keyboard())
        return
    chunks = ["<b>📦 Buyurtmalaringiz</b>"]
    for row in rows:
        items = json.loads(row["items_json"])
        names = ", ".join(f"{html.escape(i['title'])} × {i['quantity']}" for i in items)
        chunks.append(
            f"\n<b>#{row['id']}</b> · {status_label(row['status'])}\n{names}\n"
            f"Jami: <b>{price_text(row['total'])}</b>\nSana: {html.escape(row['created_at'])}"
        )
    await message.answer("\n".join(chunks), reply_markup=main_keyboard())


@dp.message(Command("admin"))
async def admin_handler(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("Bu bo‘lim faqat administratorlar uchun. O‘z Telegram ID’ingizni /id orqali ko‘ring.")
        return
    conn = connect_db()
    try:
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        new_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='new'").fetchone()[0]
        rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10").fetchall()
    finally:
        conn.close()
    builder_rows = []
    for row in rows:
        label = f"#{row['id']} · {status_label(row['status'])} · {price_text(row['total'])}"
        builder_rows.append([InlineKeyboardButton(text=label[:60], callback_data=f"adm_order:{row['id']}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=builder_rows) if builder_rows else None
    await message.answer(
        f"<b>🛠 {html.escape(SHOP_NAME)} — Admin panel</b>\n\n"
        f"Faol mahsulotlar: <b>{product_count()}</b>\nJami buyurtmalar: <b>{total_orders}</b>\nYangi buyurtmalar: <b>{new_orders}</b>\n\n"
        "Yangi mahsulot qo‘shish: <code>/addproduct</code>\nBekor qilish: <code>/cancel</code>\n\nOxirgi buyurtmalar:",
        reply_markup=keyboard,
    )


@dp.callback_query(F.data.startswith("adm_order:"))
async def admin_order_detail(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo‘q", show_alert=True)
        return
    order_id = int(callback.data.split(":", 1)[1])
    conn = connect_db()
    try:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    items = json.loads(row["items_json"])
    item_text = "\n".join(f"• {html.escape(i['title'])} × {i['quantity']} — {price_text(i['price'] * i['quantity'])}" for i in items)
    text = (
        f"<b>📦 Buyurtma #{row['id']}</b>\n\n{item_text}\n\n"
        f"Jami: <b>{price_text(row['total'])}</b>\nHolati: <b>{status_label(row['status'])}</b>\n\n"
        f"Mijoz: {html.escape(row['customer_name'])}\nTelefon: <code>{html.escape(row['phone'])}</code>\n"
        f"Manzil: {html.escape(row['address'])}\nIzoh: {html.escape(row['notes'] or '—')}\nTelegram ID: <code>{row['telegram_id'] or 'Web orqali'}</code>"
    )
    await callback.message.answer(text, reply_markup=order_keyboard(order_id, row["status"]))
    await callback.answer()


@dp.callback_query(F.data.startswith("adm_status:"))
async def admin_change_status(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo‘q", show_alert=True)
        return
    _, order_id_text, new_status = callback.data.split(":", 2)
    if new_status not in {"confirmed", "shipped", "cancelled"}:
        await callback.answer("Noto‘g‘ri holat", show_alert=True)
        return
    conn = connect_db()
    try:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (int(order_id_text),)).fetchone()
        if not row:
            await callback.answer("Buyurtma topilmadi", show_alert=True)
            return
        allowed_transitions = {
            "new": {"confirmed", "cancelled"},
            "confirmed": {"shipped", "cancelled"},
            "shipped": set(),
            "cancelled": set(),
        }
        if new_status not in allowed_transitions.get(row["status"], set()):
            await callback.answer("Bu buyurtma holatini endi o‘zgartirib bo‘lmaydi", show_alert=True)
            return
        conn.execute("BEGIN IMMEDIATE")
        if new_status == "cancelled":
            # Return reserved stock exactly once when an order is cancelled.
            for item in json.loads(row["items_json"]):
                conn.execute(
                    "UPDATE products SET stock=stock+? WHERE id=?",
                    (int(item["quantity"]), int(item["id"])),
                )
        conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, int(order_id_text)))
        conn.commit()
    finally:
        conn.close()
    if row["telegram_id"] and bot:
        try:
            await bot.send_message(row["telegram_id"], f"📦 <b>#{order_id_text}</b> buyurtmangiz holati yangilandi: <b>{status_label(new_status)}</b>.")
        except Exception:
            pass
    await callback.message.edit_reply_markup(reply_markup=order_keyboard(int(order_id_text), new_status))
    await callback.message.answer(f"Buyurtma #{order_id_text} holati: <b>{status_label(new_status)}</b>")
    await callback.answer("Saqlandi")


@dp.message(Command("products"))
async def admin_products_handler(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("Bu amal faqat administratorlar uchun.")
        return
    rows = all_products(active_only=False)
    if not rows:
        await message.answer("Katalogda mahsulot yo‘q.")
        return
    lines = ["<b>🛍 Mahsulotlar katalogi</b>"]
    for p in rows[:80]:
        state = "✅ Faol" if p["active"] else "⏸ Yashirilgan"
        lines.append(f"#{p['id']} · {html.escape(p['title'])} · {price_text(p['price'])} · {p['stock']} dona · {state}")
    lines.append("\n/setprice ID NARX — narxni o‘zgartirish\n/setstock ID MIQDOR — zaxira\n/hideproduct ID — katalogdan yashirish\n/showproduct ID — katalogga qaytarish")
    await message.answer("\n".join(lines))


@dp.message(Command("setprice"))
async def set_price_handler(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("Bu amal faqat administratorlar uchun.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit() or int(parts[2]) <= 0:
        await message.answer("Format: <code>/setprice ID NARX</code>\nMisol: <code>/setprice 4 6999000</code>")
        return
    conn = connect_db()
    try:
        cursor = conn.execute("UPDATE products SET price=? WHERE id=?", (int(parts[2]), int(parts[1])))
        conn.commit()
    finally:
        conn.close()
    await message.answer("✅ Narx yangilandi." if cursor.rowcount else "Mahsulot ID topilmadi.")


@dp.message(Command("setstock"))
async def set_stock_handler(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("Bu amal faqat administratorlar uchun.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit() or int(parts[2]) > 100000:
        await message.answer("Format: <code>/setstock ID MIQDOR</code>\nMisol: <code>/setstock 4 12</code>")
        return
    conn = connect_db()
    try:
        cursor = conn.execute("UPDATE products SET stock=? WHERE id=?", (int(parts[2]), int(parts[1])))
        conn.commit()
    finally:
        conn.close()
    await message.answer("✅ Ombordagi miqdor yangilandi." if cursor.rowcount else "Mahsulot ID topilmadi.")


async def set_product_active(message: Message, active: int) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("Bu amal faqat administratorlar uchun.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        command = "/showproduct ID" if active else "/hideproduct ID"
        await message.answer(f"Format: <code>{command}</code>")
        return
    conn = connect_db()
    try:
        cursor = conn.execute("UPDATE products SET active=? WHERE id=?", (active, int(parts[1])))
        conn.commit()
    finally:
        conn.close()
    if cursor.rowcount:
        await message.answer("✅ Mahsulot katalogda ko‘rsatiladi." if active else "✅ Mahsulot katalogdan yashirildi.")
    else:
        await message.answer("Mahsulot ID topilmadi.")


@dp.message(Command("hideproduct"))
async def hide_product_handler(message: Message) -> None:
    await set_product_active(message, 0)


@dp.message(Command("showproduct"))
async def show_product_handler(message: Message) -> None:
    await set_product_active(message, 1)


@dp.message(Command("addproduct"))
async def add_product_start(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("Bu amal faqat administratorlar uchun.")
        return
    await state.clear()
    await state.set_state(ProductAdd.title)
    await message.answer("Mahsulot nomini yuboring. Bekor qilish: /cancel")


@dp.message(ProductAdd.title)
async def add_product_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if len(title) < 2 or len(title) > 120:
        await message.answer("Nom 2–120 belgi orasida bo‘lsin. Qayta kiriting:")
        return
    await state.update_data(title=title)
    await state.set_state(ProductAdd.category)
    await message.answer("Toifani yuboring (masalan: Gaming, Premium, O‘qish va ofis):")


@dp.message(ProductAdd.category)
async def add_product_category(message: Message, state: FSMContext) -> None:
    category = (message.text or "").strip()
    if not category or len(category) > 80:
        await message.answer("Toifa nomini kiriting (80 belgigacha):")
        return
    await state.update_data(category=category)
    await state.set_state(ProductAdd.price)
    await message.answer("Narxini faqat raqam bilan yuboring (masalan: 7499000):")


@dp.message(ProductAdd.price)
async def add_product_price(message: Message, state: FSMContext) -> None:
    value = (message.text or "").replace(" ", "").replace(",", "").replace(".", "")
    if not value.isdigit() or int(value) <= 0:
        await message.answer("Narx musbat son bo‘lishi kerak. Qayta yuboring, masalan: 7499000")
        return
    await state.update_data(price=int(value))
    await state.set_state(ProductAdd.description)
    await message.answer("Mahsulot tavsifini yuboring:")


@dp.message(ProductAdd.description)
async def add_product_description(message: Message, state: FSMContext) -> None:
    description = (message.text or "").strip()
    if not description:
        await message.answer("Tavsif bo‘sh qolmasin. Qayta kiriting:")
        return
    await state.update_data(description=description[:1000])
    await state.set_state(ProductAdd.image_url)
    await message.answer("Mahsulot rasmi uchun to‘g‘ridan-to‘g‘ri HTTPS URL yuboring yoki rasm bo‘lmasa — yuboring: -")


@dp.message(ProductAdd.image_url)
async def add_product_image(message: Message, state: FSMContext) -> None:
    image_url = (message.text or "").strip()
    if image_url == "-":
        image_url = ""
    elif image_url and not image_url.startswith("https://"):
        await message.answer("Rasm manzili https:// bilan boshlansin yoki rasm bo‘lmasa - yuboring:")
        return
    data = await state.get_data()
    conn = connect_db()
    try:
        conn.execute(
            "INSERT INTO products(title,category,price,description,image_url,badge,stock) VALUES(?,?,?,?,?,?,?)",
            (data["title"], data["category"], data["price"], data["description"], image_url, "Yangi", 10),
        )
        conn.commit()
    finally:
        conn.close()
    await state.clear()
    await message.answer(
        "✅ <b>Mahsulot qo‘shildi!</b>\n\n"
        f"{html.escape(data['title'])}\nToifa: {html.escape(data['category'])}\nNarx: <b>{price_text(data['price'])}</b>\nZaxira: 10 dona\n\n"
        "Mini App sahifasini yangilab, katalogda tekshiring.",
        reply_markup=main_keyboard(),
    )


@dp.message()
async def fallback_handler(message: Message) -> None:
    await message.answer("Menyudan kerakli bo‘limni tanlang yoki /help buyrug‘ini yuboring.", reply_markup=main_keyboard())


# ---------------------------------- API -------------------------------------

@app.get("/", response_class=HTMLResponse)
async def mini_app() -> HTMLResponse:
    page = MINI_APP_HTML.replace("__SHOP_NAME__", html.escape(SHOP_NAME))
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "shop": SHOP_NAME}


@app.get("/api/products")
async def api_products() -> list[dict[str, Any]]:
    products = all_products()
    return [
        {
            "id": p["id"], "title": p["title"], "category": p["category"],
            "price": p["price"], "description": p["description"],
            "image_url": p["image_url"], "badge": p["badge"], "stock": p["stock"],
        }
        for p in products
    ]


@app.get("/api/orders")
async def api_orders(initData: str = "") -> list[dict[str, Any]]:
    user = validate_init_data(initData)
    if not user or not isinstance(user.get("id"), int):
        raise HTTPException(status_code=401, detail="Telegram foydalanuvchisi tekshirilmadi. Bot ichidagi Mini App’dan oching.")
    conn = connect_db()
    try:
        rows = conn.execute(
            "SELECT * FROM orders WHERE telegram_id=? ORDER BY id DESC LIMIT 30", (user["id"],)
        ).fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row["id"], "total": row["total"], "status": row["status"],
                "status_label": status_label(row["status"]), "created_at": row["created_at"],
                "items": json.loads(row["items_json"]),
            })
        return result
    finally:
        conn.close()


@app.post("/api/order")
async def api_create_order(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="So‘rov ma’lumotlari noto‘g‘ri.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="So‘rov ma’lumotlari noto‘g‘ri.")
    init_data = str(payload.get("initData", ""))
    telegram_user = None
    if init_data:
        telegram_user = validate_init_data(init_data)
        if not telegram_user or not isinstance(telegram_user.get("id"), int):
            raise HTTPException(status_code=401, detail="Telegram xavfsizlik tekshiruvi muvaffaqiyatsiz. Mini App’ni qayta oching.")
    name = str(payload.get("customerName", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    address = str(payload.get("address", "")).strip()
    notes = str(payload.get("notes", "")).strip()
    items = payload.get("items")
    if not 2 <= len(name) <= 100:
        raise HTTPException(status_code=400, detail="Ism familiyani to‘g‘ri kiriting.")
    if not 7 <= len(phone) <= 30:
        raise HTTPException(status_code=400, detail="Telefon raqamini to‘g‘ri kiriting.")
    if not 5 <= len(address) <= 500:
        raise HTTPException(status_code=400, detail="Yetkazib berish manzilini to‘liq kiriting.")
    if not isinstance(items, list) or not items or len(items) > 30:
        raise HTTPException(status_code=400, detail="Savatingizga kamida bitta mahsulot qo‘shing.")

    conn = connect_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        item_snapshot = []
        total = 0
        quantities: dict[int, int] = {}
        for item in items:
            if not isinstance(item, dict):
                raise HTTPException(status_code=400, detail="Savatcha ma’lumotlari noto‘g‘ri.")
            try:
                product_id, quantity = int(item.get("id")), int(item.get("quantity"))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Mahsulot ma’lumotlari noto‘g‘ri.")
            if quantity < 1 or quantity > 10:
                raise HTTPException(status_code=400, detail="Har bir mahsulotdan 1–10 dona tanlash mumkin.")
            quantities[product_id] = quantities.get(product_id, 0) + quantity
        for product_id, quantity in quantities.items():
            p = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (product_id,)).fetchone()
            if not p:
                raise HTTPException(status_code=400, detail="Mahsulotlardan biri topilmadi. Sahifani yangilang.")
            if quantity > int(p["stock"]):
                raise HTTPException(status_code=409, detail=f"{p['title']} uchun omborda faqat {p['stock']} dona qoldi.")
            item_snapshot.append({"id": p["id"], "title": p["title"], "price": p["price"], "quantity": quantity})
            total += int(p["price"]) * quantity
        cursor = conn.execute(
            """INSERT INTO orders(telegram_id,customer_name,phone,address,notes,items_json,total,status)
               VALUES(?,?,?,?,?,?,?,'new')""",
            (
                int(telegram_user["id"]) if telegram_user else None,
                name, phone, address, notes[:500], json.dumps(item_snapshot, ensure_ascii=False), total,
            ),
        )
        order_id = int(cursor.lastrowid)
        for product_id, quantity in quantities.items():
            conn.execute("UPDATE products SET stock=stock-? WHERE id=?", (quantity, product_id))
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        log.exception("Order create failed")
        raise HTTPException(status_code=500, detail="Buyurtma saqlanmadi. Birozdan so‘ng qayta urinib ko‘ring.")
    finally:
        conn.close()

    item_lines = "\n".join(f"• {html.escape(i['title'])} × {i['quantity']} — {price_text(i['price'] * i['quantity'])}" for i in item_snapshot)
    admin_message = (
        f"🛎 <b>Yangi buyurtma #{order_id}</b>\n\n{item_lines}\n\nJami: <b>{price_text(total)}</b>\n\n"
        f"Mijoz: {html.escape(name)}\nTelefon: <code>{html.escape(phone)}</code>\nManzil: {html.escape(address)}\n"
        f"Izoh: {html.escape(notes or '—')}\nTelegram ID: <code>{telegram_user['id'] if telegram_user else 'Web orqali'}</code>"
    )
    await notify_admins(admin_message)
    return JSONResponse({"ok": True, "order_id": order_id, "total": total})


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> dict[str, bool]:
    if not IS_RENDER:
        raise HTTPException(status_code=404, detail="Not found")
    provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(provided_secret, WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot is starting")
    try:
        update = Update.model_validate(await request.json(), context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception:
        log.exception("Could not process Telegram webhook update")
        raise HTTPException(status_code=500, detail="Update failed")
    return {"ok": True}


# ---------------------------------- Main ------------------------------------

async def run() -> None:
    global bot
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN topilmadi. Lokal ishga tushirishdan oldin BOT_TOKEN muhit o‘zgaruvchisiga BotFather tokenini kiriting.\n"
            "Windows PowerShell: $env:BOT_TOKEN='TOKENINGIZ'\nLinux/macOS: export BOT_TOKEN='TOKENINGIZ'"
        )
    init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Do‘konni ochish"),
            BotCommand(command="help", description="Yordam"),
            BotCommand(command="id", description="Telegram ID ni ko‘rish"),
            BotCommand(command="admin", description="Admin panel"),
            BotCommand(command="addproduct", description="Mahsulot qo‘shish"),
            BotCommand(command="products", description="Mahsulotlar ro‘yxati"),
        ])
        if IS_RENDER:
            if not APP_URL.startswith("https://"):
                raise SystemExit("Render ishga tushirish uchun RENDER_EXTERNAL_URL mavjud bo‘lishi kerak.")
            await bot.set_webhook(
                url=f"{APP_URL}{WEBHOOK_PATH}",
                secret_token=WEBHOOK_SECRET,
                allowed_updates=dp.resolve_used_update_types(),
                drop_pending_updates=False,
            )
            try:
                await bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(text="Do‘kon", web_app=WebAppInfo(url=APP_URL))
                )
            except Exception as exc:
                log.warning("Could not set Mini App menu button: %s", exc)
            port = int(os.getenv("PORT", "10000"))
            log.info("Starting %s on Render at %s (port %s)", SHOP_NAME, APP_URL, port)
            server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info"))
            await server.serve()
        else:
            # Local mode uses polling for the bot while the Mini App can be previewed in a browser.
            await bot.delete_webhook(drop_pending_updates=False)
            if APP_URL.startswith("https://"):
                try:
                    await bot.set_chat_menu_button(
                        menu_button=MenuButtonWebApp(text="Do‘kon", web_app=WebAppInfo(url=APP_URL))
                    )
                except Exception as exc:
                    log.warning("Could not set Mini App menu button: %s", exc)
            else:
                log.info("Mini App browser preview: http://127.0.0.1:%s", LOCAL_WEB_PORT)
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=LOCAL_WEB_PORT, log_level="warning"))
            await asyncio.gather(dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()), server.serve())
    finally:
        if bot is not None:
            await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("Bot stopped")
