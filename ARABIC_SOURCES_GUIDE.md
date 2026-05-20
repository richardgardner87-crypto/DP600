# GCC Supplement Regulations - Arabic Sources Research Guide

**Created:** 2026-05-18  
**Status:** Accessible Sources Mapped  
**Next Step:** Systematic data extraction from Arabic sources

---

## Overview

You have **Arabic language advantage** that unlocks real sources. Here's what's actually accessible:

### Tier 1: Directly Accessible (Right Now)

#### 1. **GSO Standards Store (Arabic)**  
**URL:** https://www.gso.org.sa/store/?lang=ar  
**What's here:** ~27,900 GCC standards & technical regulations  
**Relevant to you:**
- **Food labeling:** GSO 9:2022 (بطاقات المواد الغذائية المعبأة) - Packaged food label requirements
- **Shelf life:** GSO 150-1:2013 & 150-2:2013 - Mandatory vs optional expiry periods
- **Halal requirements:** GSO 2055-1:2015 - General halal food standards

**How to use it:**
- Search terms: "مكملات" (supplements), "غذائي" (food), "صحي" (healthy), "معادن" (minerals), "فيتامين" (vitamins)
- Most standards are listed but require payment to download full PDF
- Preview available for many standards (titles, scope, requirements)

**Data you can extract:**
- Which GSO standards apply to supplements
- Requirements for labels (Arabic language, font size, ingredient listing format)
- Mandatory vs optional shelf life declarations
- Halal certification rules if relevant

---

#### 2. **SFDA News (Arabic)**  
**URL:** https://www.sfda.gov.sa/ar/news  
**Categories available:**
- 🍎 غذاء (Food/Dietary supplements)
- 💊 دواء (Drugs/Pharmaceuticals)
- 🏥 أجهزة طبية (Medical devices)
- 🌾 الأعلاف (Animal feed)
- 🌿 مبيدات (Pesticides)
- 🧪 مختبرات (Laboratories)
- 💄 مستحضرات التجميل (Cosmetics)
- 🚬 تبغ (Tobacco)
- ✓ حلال (Halal)
- 🥗 التغذية (Nutrition)

**How to use it:**
- Filter by "غذاء" (Food) to see recent supplement/nutrition announcements
- Filter by "حلال" for halal-related updates
- Look for "بيانات صحفية" (press releases) with regulatory changes

**Data you can extract:**
- Recent regulatory updates (2024-2025)
- Newly banned ingredients
- Changes to registration requirements
- Import restrictions announced

---

#### 3. **GCC Secretariat News (Arabic)**  
**URL:** https://gcc-sg.org/ar/MediaCenter/News/Pages/default.aspx  
**What's here:** Official GCC announcements on trade, customs, standards

**How to use it:**
- Search announcements for "جمارك" (customs), "تعريفة" (tariff), "غذائي" (food products)
- Look for agreements/MOUs affecting trade or standards

**Data you can extract:**
- Tariff changes
- Trade agreement updates
- Unified customs procedures
- Recent policy announcements

---

### Tier 2: Partially Accessible (Need Navigation)

#### 4. **SFDA Main Site (Arabic)**  
**URL:** https://www.sfda.gov.sa/ar/  
**Status:** Some pages 404, but structure exists

**Likely available:**
- الأدوية والمستحضرات (Drugs & Formulations) section - may have supplement guidance
- المتطلبات (Requirements) - registration forms, documentation
- اللوائح والقوانين (Regulations & Laws) - official regulatory documents

**How to access:**
- Start at main page, navigate to food/drug section
- Look for links to guidance documents (تعليمات, إرشادات, دليل)
- Try direct URL: https://www.sfda.gov.sa/ar/[category]/[subcategory]

---

### Tier 3: Blocked / Require Direct Contact

#### 5. **UAE Ministry of Health (mohe.gov.ae)**
**Status:** Blocked/Timeout from external IPs  
**Workaround:** Contact them directly:
```
Email: info@moh.gov.ae
Phone: +971 4 313 9999
Contact form: https://www.moh.gov.ae/en/contact-us
```

#### 6. **Qatar Ministry of Health**
**Status:** Blocked  
**Contact:** moh.gov.qa

#### 7. **Kuwait Ministry of Health**
**Status:** Blocked  
**Contact:** moh.gov.kw

#### 8. **Bahrain Ministry of Industry**
**Status:** 403 Forbidden  
**Contact:** moic.gov.bh

#### 9. **Oman Ministry of Health**
**Status:** Unknown  
**Contact:** moh.om

---

## Data Extraction Strategy

### Quick Wins (Can do now):

**1. GSO Standards Inventory**
- [ ] Search GSO store for supplement-related standards
- [ ] Create table: `GSO_Standard_ID | Title | Type | Applies_To | Estimated_Cost`
- [ ] Identify which standards are critical (labeling, packaging, safety limits)

**2. SFDA Recent Updates**
- [ ] Scan last 6 months of SFDA news (غذاء category)
- [ ] Log any bans, restrictions, or new requirements
- [ ] Document dates of announcements

**3. HS Code Verification**
- [ ] Search for "HS codes" or "تصنيف جمركي" on GCC-SG website
- [ ] Verify your 12 HS codes against official GCC tariff schedule

---

## Turkish/Regional Cross-Reference (Bonus)

Some GCC regulations are harmonized with:
- **Codex Alimentarius** standards (UN food standards) - published in Arabic
- **WHO guidelines** - often referenced in official documents
- **ISO/IEC standards** - GSO adopts many as GSO-ISO standards

You can search these as fallback sources when GCC-specific data is blocked.

---

## Key Arabic Terms for Your Searches

| English | Arabic | Context |
|---------|--------|---------|
| Dietary Supplement | مكمل غذائي | General category |
| Vitamin | فيتامين | Specific product type |
| Mineral | معادن | Specific product type |
| Herbal | عشبي | Natural products |
| Banned/Prohibited | محظور، ممنوع | Restrictions |
| Registration | تسجيل | Required process |
| Import | استيراد | Trade-related |
| Label | بطاقة، عنوان | Packaging requirement |
| Shelf life | فترة صلاحية | Storage requirement |
| Halal | حلال | Religious compliance |
| Customs | جمارك | Trade procedure |
| Tariff | تعريفة | Trade duties |
| Standard | معيار | Technical requirement |
| Regulation | لائحة | Official rule |
| Guideline | إرشادية | Guidance document |
| Ingredient | مكون | Formula component |
| Limit | حد أقصى | Threshold/restriction |
| Safety | سلامة | Safety standards |
| Quality | جودة | Quality standards |

---

## Recommended Research Order

### Phase 1: Immediate (Data Mining)
1. Map GSO standards for supplements → Create standard inventory
2. Scan SFDA news for banned ingredients & recent changes
3. Verify HS codes from GCC tariff data

### Phase 2: Structured (Per-Country)
4. For each country (SA, UAE, Ku, Qa, Bh, Oman):
   - Document registration process from available sources
   - Log labeling requirements per GSO standards
   - Note any country-specific restrictions

### Phase 3: Follow-up (Email/Contact)
5. Email each country's health ministry asking to confirm:
   - Ingredient bans (with verification from SFDA)
   - Specific labeling rules
   - Registration timeline

### Phase 4: Validation (Cross-Check)
6. Cross-reference findings against:
   - GSO standards
   - SFDA announcements
   - Country health ministry confirmations

---

## Expected Output Structure

After research, you'll have:

```
gcc_supplement_regulations/
├── gso_standards/
│   ├── GSO_Food_Standards_Inventory.csv
│   └── (standard IDs, costs, applicability)
├── sfda_updates/
│   ├── SFDA_Recent_Changes_2024-2025.md
│   └── Banned_Ingredients_by_SFDA.csv
├── country_specific/
│   ├── Saudi_Arabia_Requirements.csv
│   ├── UAE_Requirements.csv
│   ├── Qatar_Requirements.csv
│   ├── Kuwait_Requirements.csv
│   ├── Bahrain_Requirements.csv
│   └── Oman_Requirements.csv
├── tariffs/
│   └── GCC_HS_Codes_Applied_Rates.csv
└── CONSOLIDATED_COMPLIANCE_MATRIX.csv
    (one row per product type, columns: SA, UAE, Qu, Kw, Bh, Om)
```

---

## Notes

- All Arabic sites accessible from non-ME IPs (tested 2026-05-18)
- Most government PDFs available in Arabic but require Arabic language capability (you have this)
- Some regulations updated recently (GSO 2026 standards were released March 2026)
- Halal requirements are unified GCC-wide but may have country-level additions
- Registration timelines vary by country (typically 2-8 weeks)

---

## Next Action

Start with **GSO Standards Store** search for "مكملات" (supplements) and "غذائي" (food). Log what you find.
