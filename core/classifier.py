"""
Category Classifier for Egyptian Deals & Black Friday Telegram Bot.
Classifies products into 5 target categories using Arabic and English regex patterns.
"""

from __future__ import annotations
import re
from typing import Optional, Any
from core.models import StoreEnum, CategoryEnum, Deal


def normalize_arabic(text: str) -> str:
    """Normalize Arabic letters and remove diacritics for uniform regex matching."""
    if not text:
        return ""
    # Remove Tashkeel (diacritics)
    text = re.sub(r"[\u064B-\u0652\u0670]", "", text)
    # Normalize Alef forms
    text = re.sub(r"[إأآٱ]", "ا", text)
    # Normalize Ta Marbuta and Ha
    text = re.sub(r"ة\b", "ه", text)
    # Normalize Ya / Alef Maksura
    text = re.sub(r"ى\b", "ي", text)
    return text


# --- LAPTOPS PATTERNS ---
LAPTOP_INCLUSION = re.compile(
    r"\b(لابتوب|لاب\s*توب|حاسوب\s*محمول|كمبيوتر\s*محمول|نوت\s*بوك|"
    r"(?:ابل\s*)?ماك\s*بوك|(?:لينوفو\s*)?ثينك\s*باد|(?:اتش\s*بي\s*)?بافيليون|"
    r"(?:ديل\s*)?لاتيتيود|(?:ديل\s*)?xps|(?:ايسوس\s*)?زين\s*بوك|كروم\s*بوك|ايديا\s*باد|"
    r"laptop|notebook|macbook|chromebook|ultrabook|thinkpad|ideapad|"
    r"legion|rog\s*strix|scar\s*18|zenbook|vivobook|pavilion|yoga\s*slim|"
    r"alienware|predator\s*helios|tuf\s*gaming|blade\s*1[4568]|razer\s*blade|"
    r"omen\s*1[567]|victus|loq|latitude|elitebook|probook|expertbook|xps|spectre|envy)\b",
    re.IGNORECASE
)

# Laptop accessory exclusion (so bags/stands/stickers are NOT tagged as laptops)
# Matches both Ta Marbuta (ة) and Ha (ه) endings
LAPTOP_ACCESSORY_EXCLUSION = re.compile(
    r"\b(شنط[ةه]|حقيب[ةه]|جراب|كفر|غطاء|ستيكر|ملصق|حامل|مسند|قاعد[ةه]|كابل|شاحن|محول|وصل[ةه]|سماع[ةه]|ماوس|لوح[ةه]\s*مفاتيح|"
    r"سلك|لزق[ةه]|ماوس\s*باد|"
    r"bag|backpack|sleeve|case|cover|skin|sticker|stand|holder|dock|adapter|charger|cable|mouse|pad|headset)\b",
    re.IGNORECASE
)

# --- BABY DIAPERS PATTERNS ---
DIAPERS_INCLUSION = re.compile(
    r"\b(حفاض|حفاضات|حفائض|بامبرز|فاين\s*بيبي|مولفيكس|بيبي\s*جوي|كان\s*بيبي|سليب\s*اند\s*بلاي|كلوت\s*اطفال|"
    r"مناديل\s*مبلله\s*للاطفال|وايبس\s*اطفال|"
    r"diaper|diapers|nappy|nappies|pampers|molfix|babyjoy|baby\s*joy|canbebe|fine\s*baby|baby\s*wipes)\b",
    re.IGNORECASE
)

ADULT_INCONTINENCE_EXCLUSION = re.compile(
    r"\b(ل?كبار\s*السن|ل?سلس\s*البول|تينا|ديبند|سيني|adult\s*diaper|adult\s*briefs|tena|depend|seni)\b",
    re.IGNORECASE
)

# --- BABY CLOTHES PATTERNS ---
BABY_CLOTHES_INCLUSION = re.compile(
    r"\b(ملابس\s*اطفال|ملابس\s*رضع|سالوبيت|سالوبت|سلوبيت|افارول|بافته|مريله\s*اطفال|حديثي\s*الولاده|"
    r"تبانه|تيابنه|كوالين\s*اطفال|اطقم\s*بيبي|بيبي\s*وير|شورت\s*اطفال|رومبر|"
    r"onesie|onesies|romper|rompers|bodysuit|bodysuits|baby\s*wear|baby\s*clothing|"
    r"infant\s*wear|newborn\s*wear|toddler\s*wear|sleepsuit|footie)\b",
    re.IGNORECASE
)

# --- ADULT & KIDS CLOTHING PATTERNS ---
CLOTHING_INCLUSION = re.compile(
    r"\b(قميص|فستان|بنطلون|بنطال|جاكيت|ستره|معطف|هودي|سويت\s*شيرت|بلوفر|تيشيرت|تي\s*شيرت|تشيرت|"
    r"احذيه|حذاء|شوز|كوتشي|سنيكرز|صندل|بوت|ترنج|ترينج|عبايه|عباءه|تنوره|جيبه|شورت|جينز|سروال|"
    r"ملابس\s*رجالي|ملابس\s*حريمي|ازياء|بيجامه|طقم\s*خروج|"
    r"shoes|sneakers|boots|sandals|t-shirt|tshirt|shirt|hoodie|sweatshirt|jacket|coat|"
    r"blazer|jeans|pants|trousers|dress|skirt|sweater|cardigan|polo|blouse|sportswear|"
    r"tracksuit|sweatpants|joggers|apparel|footwear)\b",
    re.IGNORECASE
)

# --- HOUSEHOLD GENERAL PATTERNS ---
HOUSEHOLD_INCLUSION = re.compile(
    r"\b(منظف|منظفات|مسحوق\s*غسيل|مسحوق\s*اتوماتيك|اريال|تايد|برسيل|فيري|كلوركس|صابون\s*صحون|مطهر|"
    r"مناديل|بكره\s*مناديل|ورق\s*تواليت|فوط\s*مطبخ|اسفنجه|"
    r"قلايه\s*هوائيه|ايرفراير|مكنسه|مكنسه\s*كهربائيه|خلاط|عجانه|كبه|غلايه|طقم\s*طهي|طقم\s*حلل|"
    r"اواني|مقلاه|طاسه|صينيه|كوبايات|اطباق|مطبخ|ملايات|مفارش|وسائد|مخدات|لحاف|سجاد|منزلي|مستلزمات\s*المنزل|"
    r"detergent|washing\s*powder|ariel|tide|persil|fairy|clorox|dishwashing|cleaner|disinfectant|"
    r"tissues|napkins|paper\s*towel|towels|kitchenware|cookware|frying\s*pan|pot\s*set|casserole|"
    r"airfryer|air\s*fryer|vacuum|blender|food\s*processor|kettle|bedsheet|blanket|pillow|household|home\s*appliances)\b",
    re.IGNORECASE
)


def classify_deal(
    title: str,
    store: StoreEnum = StoreEnum.AMAZON_EG,
    raw_category: Optional[str] = None
) -> CategoryEnum:
    """
    Classifies a product into one of the 5 canonical categories:
    1. LAPTOPS (Dedicated)
    2. BABY_DIAPERS
    3. BABY_CLOTHES
    4. CLOTHING_ADULT_KIDS
    5. HOUSEHOLD_GENERAL

    Evaluates both title and optional raw_category with Arabic normalization.
    """
    title_str = title or ""
    raw_cat_str = raw_category or ""
    combined_text = f"{title_str} {raw_cat_str}".strip()
    norm_text = normalize_arabic(combined_text)

    # 1. Check LAPTOPS first (highest priority)
    if LAPTOP_INCLUSION.search(combined_text) or LAPTOP_INCLUSION.search(norm_text):
        # Verify it is not merely an accessory like a laptop bag or sticker
        is_accessory = LAPTOP_ACCESSORY_EXCLUSION.search(combined_text) or LAPTOP_ACCESSORY_EXCLUSION.search(norm_text)
        if is_accessory:
            # Laptop bundles: If title has a clear laptop model/keyword and contains 'هدية' / 'شنطة هدية' / 'شنطه هديه' / 'gift',
            # and does not START with an accessory type, it remains LAPTOPS.
            is_gift_bundle = bool(
                re.search(r"(هد[يى][ةه]|شنط[ةه]\s*هد[يى][ةه]|free\s*(?:bag|gift)|bundle)", combined_text, re.IGNORECASE) or
                re.search(r"(هد[يى][ةه]|شنط[ةه]\s*هد[يى][ةه]|free\s*(?:bag|gift)|bundle)", norm_text, re.IGNORECASE)
            )
            starts_with_accessory = bool(
                re.match(r"^\s*(شنط[ةه]|حقيب[ةه]|جراب|كفر|غطاء|ستيكر|ملصق|حامل|مسند|قاعد[ةه]|شاحن|كابل|سماع[ةه]|ماوس|وصل[ةه]|سلك|لزق[ةه]|باد|bag|backpack|sleeve|case|stand|holder|dock|charger|cable|adapter|mouse|headset)\b", combined_text, re.IGNORECASE) or
                re.match(r"^\s*(شنط[ةه]|حقيب[ةه]|جراب|كفر|غطاء|ستيكر|ملصق|حامل|مسند|قاعد[ةه]|شاحن|كابل|سماع[ةه]|ماوس|وصل[ةه]|سلك|لزق[ةه]|باد|bag|backpack|sleeve|case|stand|holder|dock|charger|cable|adapter|mouse|headset)\b", norm_text, re.IGNORECASE)
            )
            if is_gift_bundle and not starts_with_accessory:
                is_accessory = False

        if not is_accessory:
            return CategoryEnum.LAPTOPS
        else:
            # If accessory is a bag/sleeve, route to clothing/accessories or household
            if re.search(r"\b(bag|backpack|شنط[ةه]|حقيب[ةه])\b", combined_text, re.IGNORECASE) or \
               re.search(r"\b(bag|backpack|شنط[ةه]|حقيب[ةه])\b", norm_text, re.IGNORECASE):
                return CategoryEnum.CLOTHING_ADULT_KIDS
            return CategoryEnum.HOUSEHOLD_GENERAL

    # 2. Check BABY DIAPERS
    if DIAPERS_INCLUSION.search(combined_text) or DIAPERS_INCLUSION.search(norm_text):
        if not (ADULT_INCONTINENCE_EXCLUSION.search(combined_text) or ADULT_INCONTINENCE_EXCLUSION.search(norm_text)):
            return CategoryEnum.BABY_DIAPERS

    # Detergent guard: prevent baby laundry detergents from falling into baby clothing
    is_detergent = bool(
        re.search(r"\b(مسحوق|منظف|منظفات|سائل\s*غسيل|مسحوق\s*غسيل|غسيل\s*ملابس|اريال|تايد|برسيل|فيري|كلوركس|صابون|detergent|washing\s*powder|cleaner)\b", combined_text, re.IGNORECASE) or
        re.search(r"\b(مسحوق|منظف|منظفات|سائل\s*غسيل|مسحوق\s*غسيل|غسيل\s*ملابس|اريال|تايد|برسيل|فيري|كلوركس|صابون|detergent|washing\s*powder|cleaner)\b", norm_text, re.IGNORECASE)
    )
    if is_detergent:
        return CategoryEnum.HOUSEHOLD_GENERAL

    # 3. Check BABY CLOTHES
    if BABY_CLOTHES_INCLUSION.search(combined_text) or BABY_CLOTHES_INCLUSION.search(norm_text):
        return CategoryEnum.BABY_CLOTHES

    # Check for baby + clothing combinations (e.g., "بيبي فستان" or "baby shirt")
    if (re.search(r"\b(baby|بيبي|رضع|اطفال)\b", combined_text, re.IGNORECASE) or
        re.search(r"\b(بيبي|رضع|اطفال)\b", norm_text, re.IGNORECASE)):
        if CLOTHING_INCLUSION.search(combined_text) or CLOTHING_INCLUSION.search(norm_text):
            return CategoryEnum.BABY_CLOTHES

    # 4. Check ADULT & KIDS CLOTHING
    if CLOTHING_INCLUSION.search(combined_text) or CLOTHING_INCLUSION.search(norm_text):
        return CategoryEnum.CLOTHING_ADULT_KIDS

    # 5. Check HOUSEHOLD GENERAL
    if HOUSEHOLD_INCLUSION.search(combined_text) or HOUSEHOLD_INCLUSION.search(norm_text):
        return CategoryEnum.HOUSEHOLD_GENERAL

    # 6. Fallback based on raw_category if provided
    if raw_category:
        norm_raw = normalize_arabic(raw_category.lower())
        if "diaper" in norm_raw or "حفاض" in norm_raw:
            return CategoryEnum.BABY_DIAPERS
        if "baby" in norm_raw or "رضع" in norm_raw or "اطفال" in norm_raw:
            return CategoryEnum.BABY_CLOTHES
        if "fashion" in norm_raw or "clothing" in norm_raw or "ملابس" in norm_raw or "ازياء" in norm_raw:
            return CategoryEnum.CLOTHING_ADULT_KIDS
        if "laptop" in norm_raw or "لابتوب" in norm_raw or "كمبيوتر" in norm_raw:
            return CategoryEnum.LAPTOPS

    # Default fallback category
    return CategoryEnum.HOUSEHOLD_GENERAL


def tag_deal_category(deal: Deal) -> Deal:
    """Classifies and applies the resolved category and laptop flag to a Deal instance."""
    resolved_cat = classify_deal(deal.title, deal.store, deal.category.value if deal.category else None)
    deal.category = resolved_cat
    if resolved_cat == CategoryEnum.LAPTOPS:
        deal.is_special_laptop = True
    return deal
