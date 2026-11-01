// Initialize Telegram WebApp
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
}

// Sample initial deals data for instantaneous offline/first load
let deals = [
    {
        id: "amz_philips_airfryer_xxl",
        title: "قلاية هوائية فيليبس XXL سعة 7.2 لتر مع تقنية Rapid Air الأصلية",
        store: "Amazon Egypt",
        category: "Home Appliances",
        original_price: 12499,
        discount_price: 6899,
        discount_percentage: 45,
        url: "https://www.amazon.eg/",
        is_flash_sale: 1,
        coupon_code: "PRIME15 (خصم 15% إضافي)",
        installment_info: "تقسيط 6 شهور بدون فوائد عبر بنك CIB"
    },
    {
        id: "noon_anker_soundcore_q45",
        title: "سماعة Anker Soundcore Space Q45 اللاسلكية مع عزل ضوضاء تكيفي فائق",
        store: "Noon Egypt",
        category: "Audio & Accessories",
        original_price: 7999,
        discount_price: 3899,
        discount_percentage: 51,
        url: "https://www.noon.com/egypt-ar/",
        is_flash_sale: 1,
        coupon_code: "EGY10 (كاش باك 10%)",
        installment_info: "خصم فوري 15% عند الدفع ببطاقات بنك مصر"
    },
    {
        id: "noon_samsung_tv_65",
        title: "تلفزيون سامسونج 65 بوصة 4K Ultra HD Smart LED الجيل الأحدث",
        store: "Noon Egypt",
        category: "TVs & Displays",
        original_price: 34999,
        discount_price: 18499,
        discount_percentage: 47,
        url: "https://www.noon.com/egypt-ar/",
        is_flash_sale: 1,
        coupon_code: "NOON15",
        installment_info: "تقسيط 12 شهر بدون فوائد مع valU والأهلي"
    },
    {
        id: "dream_anker_powerbank_20k",
        title: "باور بانك أنكر 20,000 مللي أمبير بقوة 30 واط شحن سريع PD",
        store: "Dream 2000",
        category: "Mobiles & Accessories",
        original_price: 2999,
        discount_price: 1499,
        discount_percentage: 50,
        url: "https://dream2000.com/",
        is_flash_sale: 1,
        coupon_code: "DREAMBF",
        installment_info: "متاح دفع فوري أو عبر المحافظ الإلكترونية"
    },
    {
        id: "btech_lg_oled_55",
        title: "شاشة إل جي 55 بوصة OLED 4K 120Hz فئة B3 سينما وألعاب بلايستيشن",
        store: "B.TECH",
        category: "TVs & Displays",
        original_price: 68000,
        discount_price: 38999,
        discount_percentage: 43,
        url: "https://btech.com/ar/",
        is_flash_sale: 1,
        coupon_code: "BTECH10",
        installment_info: "ميني كاش بدون فوائد على 12 شهر"
    }
];

let activeStore = "All";
let searchQuery = "";

// Fetch dynamic deals from server API if available
async function loadDealsFromApi() {
    try {
        const res = await fetch("/api/deals");
        if (res.ok) {
            const data = await res.json();
            if (data && data.length > 0) {
                deals = data;
            }
        }
    } catch (e) {
        console.log("Using local/cached deals dataset");
    }
    renderDeals();
}

function renderDeals() {
    const container = document.getElementById("dealsContainer");
    const countEl = document.getElementById("dealCount");

    const filtered = deals.filter(deal => {
        const matchesStore = activeStore === "All" || deal.store === activeStore;
        const matchesSearch = !searchQuery || 
            deal.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            deal.store.toLowerCase().includes(searchQuery.toLowerCase()) ||
            deal.category.toLowerCase().includes(searchQuery.toLowerCase());
        return matchesStore && matchesSearch;
    });

    countEl.textContent = filtered.length;

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center text-slate-400">
                <p class="text-sm font-bold">لا توجد عروض تطابق بحثك حالياً</p>
                <p class="text-xs text-slate-500 mt-1">جرب تغيير شروط الفلترة أو اسم المتجر</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map(deal => `
        <div class="bg-slate-900/90 border border-slate-800/80 rounded-2xl p-3.5 hover:border-slate-700 transition space-y-2.5">
            <div class="flex items-start justify-between gap-2">
                <div class="flex items-center gap-2">
                    <span class="bg-indigo-950 text-indigo-400 text-[10px] font-bold px-2 py-0.5 rounded-md border border-indigo-900">
                        ${deal.store}
                    </span>
                    ${deal.is_flash_sale ? `
                        <span class="bg-red-950 text-red-400 text-[10px] font-black px-2 py-0.5 rounded-md border border-red-900 animate-pulse">
                            🔥 فلاش سيل عاجل
                        </span>
                    ` : ''}
                </div>
                <div class="bg-emerald-950 text-emerald-400 border border-emerald-800/80 font-black text-xs px-2.5 py-1 rounded-lg">
                    خصم ${deal.discount_percentage}%
                </div>
            </div>

            <h4 class="text-sm font-bold text-white leading-snug line-clamp-2">
                ${deal.title}
            </h4>

            <div class="flex items-baseline gap-2">
                <span class="text-lg font-black text-white">${deal.discount_price.toLocaleString()} ج.م</span>
                ${deal.original_price > deal.discount_price ? `
                    <span class="text-xs text-slate-500 line-through">${deal.original_price.toLocaleString()} ج.م</span>
                ` : ''}
                <span class="text-[11px] text-emerald-400 font-bold mr-auto">
                    وفر ${(deal.original_price - deal.discount_price).toLocaleString()} ج.م
                </span>
            </div>

            ${deal.coupon_code ? `
                <div class="bg-amber-950/40 border border-amber-800/40 rounded-xl px-2.5 py-1.5 flex items-center justify-between text-[11px]">
                    <span class="text-amber-300">🎟️ كود إضافي: <b>${deal.coupon_code}</b></span>
                    <button onclick="navigator.clipboard.writeText('${deal.coupon_code.split(' ')[0]}'); alert('تم نسخ الكود!');" 
                            class="text-amber-400 text-[10px] font-bold hover:underline">نسخ</button>
                </div>
            ` : ''}

            ${deal.installment_info ? `
                <p class="text-[11px] text-indigo-300 bg-indigo-950/30 rounded-lg px-2.5 py-1 border border-indigo-900/40">
                    💳 ${deal.installment_info}
                </p>
            ` : ''}

            <div class="pt-1 flex items-center gap-2">
                <a href="${deal.url}" target="_blank" 
                   onclick="if(window.Telegram?.WebApp){window.Telegram.WebApp.openLink('${deal.url}'); return false;}"
                   class="flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold py-2 px-3 rounded-xl text-center shadow-md transition">
                    الحق العرض واشتري الآن ↗
                </a>
            </div>
        </div>
    `).join("");
}

// Event Listeners
document.querySelectorAll(".store-filter").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".store-filter").forEach(b => {
            b.classList.remove("active", "bg-indigo-600", "text-white");
            b.classList.add("bg-slate-800", "text-slate-300");
        });
        btn.classList.add("active", "bg-indigo-600", "text-white");
        btn.classList.remove("bg-slate-800", "text-slate-300");
        activeStore = btn.dataset.store;
        renderDeals();
    });
});

document.getElementById("searchInput").addEventListener("input", (e) => {
    searchQuery = e.target.value.trim();
    renderDeals();
});

document.getElementById("refreshBtn").addEventListener("click", () => {
    loadDealsFromApi();
    if (tg) tg.HapticFeedback?.notificationOccurred("success");
});

document.getElementById("alertSettingsBtn").addEventListener("click", () => {
    alert("التنبيهات مفعلة تلقائياً في تليجرام فور صدور أي خصم يتجاوز 40% أو أي هبوط في سعر ASUS ROG Strix 18.");
});

// Initial run
loadDealsFromApi();
