"""
Run this script to regenerate mock_inventory.csv with a realistic
distribution of compliance states across all 6 GCC countries.

Today = 2026-05-19

UAE threshold: 75% remaining shelf life
KSA/Kuwait/Qatar/Bahrain/Oman threshold: 50%

Zones:
A  - CLEAR all countries            (days_remaining > 75% of total SL)
B  - UAE breach imminent 10-90d     (currently clear, breach soon)
C  - UAE failed, KSA/others CLEAR   (50-75% remaining)
D  - ALL shelf life failed          (< 50% remaining or expired)
E  - INGREDIENT blocked             (banned substances)
F  - RX_ONLY                        (melatonin)
G  - HALAL cert needed              (animal-derived, long expiry, no cert)
"""
from datetime import date, timedelta
import csv, os

TODAY = date(2026, 5, 19)

def row(sku, name, brand, cat, hs, ingredients, batch, days_rem, total_sl, qty, cost, halal, origin):
    expiry = TODAY + timedelta(days=int(days_rem))
    mfg    = expiry - timedelta(days=int(total_sl))
    return dict(
        sku_id=sku, product_name=name, brand=brand, category=cat, hs_code=hs,
        ingredients=ingredients, batch_id=batch,
        manufacture_date=mfg.strftime('%Y-%m-%d'),
        expiry_date=expiry.strftime('%Y-%m-%d'),
        total_shelf_life_days=total_sl, qty_on_hand=qty,
        unit_cost_usd=cost, halal_certified=halal, country_of_origin=origin,
    )

PRODUCTS = [
    # ── Zone A: CLEAR all countries ─────────────────────────────────────────
    # 730-day shelf life, days_remaining > 548 (75% of 730)
    row('SKU001','Vitamin D3 2000IU 120 Capsules (Vegan)','NOW Foods','Vitamins','2936.29',
        'Vitamin D3 Cholecalciferol, Cellulose, Magnesium Stearate','B26-001',700,730,280,7.49,'yes','USA'),
    row('SKU002','Vitamin C 1000mg 100 Tablets','NOW Foods','Vitamins','2936.27',
        'Ascorbic Acid, Cellulose, Stearic Acid, Magnesium Stearate','B26-002',680,730,180,8.99,'yes','USA'),
    row('SKU003','Magnesium Glycinate 400mg 180 Capsules','Doctors Best','Minerals','2106.90',
        'Magnesium Glycinate Chelate, Cellulose, Magnesium Stearate','B26-003',660,730,415,18.99,'yes','USA'),
    row('SKU004','Zinc Picolinate 50mg 120 Capsules','NOW Foods','Minerals','2106.90',
        'Zinc Picolinate, Cellulose, Magnesium Stearate','B26-004',640,730,290,9.49,'yes','USA'),
    row('SKU005','Vitamin B Complex 100 Capsules','Jarrow Formulas','Vitamins','2106.90',
        'Thiamine HCl, Riboflavin, Niacinamide, Pyridoxine B6, Methylfolate, Methylcobalamin, Biotin, Pantothenic Acid, Cellulose','B26-005',620,730,320,11.99,'yes','USA'),
    row('SKU006','Multivitamin Mens 120 Tablets','Garden of Life','Vitamins','2106.90',
        'Vitamin A Acetate, Ascorbic Acid, Cholecalciferol, d-Alpha Tocopherol, Thiamine, Riboflavin, Niacinamide, Pyridoxine, Methylfolate, Methylcobalamin, Zinc, Selenium, Organic Spinach','B26-006',600,730,260,28.99,'yes','USA'),
    row('SKU007','Multivitamin Womens 120 Tablets','Garden of Life','Vitamins','2106.90',
        'Vitamin A, Ascorbic Acid, Cholecalciferol, d-Alpha Tocopherol, Menaquinone K2, Methylfolate, Methylcobalamin, Iron, Calcium Carbonate, Magnesium Oxide, Organic Cranberry Extract','B26-007',580,730,240,29.99,'yes','USA'),
    row('SKU008','Ashwagandha KSM-66 600mg 90 Capsules','Jarrow Formulas','Adaptogen','1302.19',
        'Ashwagandha Root Extract KSM-66 Withania somnifera, Cellulose, Magnesium Stearate','B26-008',560,730,310,18.49,'yes','India'),
    row('SKU009','Turmeric Curcumin 500mg 60 Capsules','NOW Foods','Herbal','1302.19',
        'Turmeric Root Extract 95% Curcuminoids, Black Pepper Extract BioPerine, Cellulose','B26-009',700,730,220,9.99,'yes','India'),
    row('SKU010','Creatine Monohydrate 500g','Optimum Nutrition','Sports','2106.90',
        'Creatine Monohydrate','B26-010',680,730,110,24.99,'yes','Germany'),
    row('SKU011','Spirulina 500mg 200 Tablets','NOW Foods','Superfoods','2106.90',
        'Spirulina Arthrospira platensis, Cellulose, Magnesium Stearate','B26-011',660,730,280,14.99,'yes','USA'),
    row('SKU012','Vitamin B12 Methylcobalamin 1000mcg 100 Tablets','Jarrow Formulas','Vitamins','2936.26',
        'Methylcobalamin, Mannitol, Cellulose, Magnesium Stearate','B26-012',640,730,350,11.49,'yes','USA'),
    row('SKU013','Quercetin 500mg 60 Capsules','NOW Foods','Antioxidants','2106.90',
        'Quercetin Dihydrate, Cellulose, Magnesium Stearate','B26-013',620,730,185,14.49,'yes','USA'),
    row('SKU014','Berberine HCl 500mg 60 Capsules','Thorne Research','Metabolic','2106.90',
        'Berberine HCl, Cellulose, Magnesium Stearate','B26-014',600,730,175,24.99,'yes','China'),
    row('SKU015','Lions Mane Mushroom 500mg 60 Capsules','Host Defense','Cognitive','1302.19',
        'Lions Mane Mushroom Hericium erinaceus Mycelium and Fruiting Bodies, Cellulose','B26-015',580,730,160,26.99,'yes','USA'),
    row('SKU016','Alpha Lipoic Acid 600mg 60 Capsules','Doctors Best','Antioxidants','2106.90',
        'Alpha Lipoic Acid, Cellulose, Magnesium Stearate','B26-016',700,730,190,14.99,'yes','USA'),
    row('SKU017','NAC N-Acetyl Cysteine 600mg 100 Capsules','NOW Foods','Antioxidants','2106.90',
        'N-Acetyl-L-Cysteine, Cellulose, Magnesium Stearate','B26-017',680,730,165,12.49,'yes','USA'),
    row('SKU018','Maca Root 500mg 100 Capsules','NOW Foods','Hormonal','1211.90',
        'Maca Root Powder Lepidium meyenii, Cellulose, Magnesium Stearate','B26-018',660,730,175,10.99,'yes','Peru'),
    row('SKU019','Rhodiola Rosea 500mg 60 Capsules','NOW Foods','Adaptogen','1302.19',
        'Rhodiola Rosea Root Extract 3% Rosavins 1% Salidroside, Cellulose','B26-019',640,730,155,14.99,'yes','Russia'),
    row('SKU020','BCAAs 2:1:1 300g Unflavoured','NOW Sports','Sports','2922.41',
        'L-Leucine, L-Isoleucine, L-Valine','B26-020',620,730,88,19.99,'yes','USA'),
    row('SKU021','L-Glutamine 500g','Jarrow Formulas','Sports','2922.41',
        'L-Glutamine','B26-021',700,730,76,21.49,'yes','USA'),
    row('SKU022','Black Seed Oil 500mg 90 Capsules Vegan','Amazing Herbs','Herbal','1515.90',
        'Black Cumin Seed Oil Nigella sativa, Cellulose Capsule','B26-022',680,730,200,19.99,'yes','Egypt'),
    row('SKU023','Moringa Leaf Powder 240g Organic','Kiva','Superfoods','1211.90',
        'Organic Moringa Oleifera Leaf Powder','B26-023',660,730,115,17.99,'yes','India'),
    row('SKU024','Pea Protein Isolate Unflavoured 1kg','NOW Sports','Protein','2106.10',
        'Pea Protein Isolate Pisum sativum','B26-024',640,730,54,28.99,'yes','Canada'),
    row('SKU025','Selenium 200mcg 90 Capsules','NOW Foods','Minerals','2106.90',
        'Selenium Glycinate Complex, Cellulose, Magnesium Stearate','B26-025',620,730,310,8.49,'yes','USA'),

    # ── Zone B: CLEAR now, UAE breach imminent (10–90 days) ─────────────────
    # breach_days_UAE = days_remaining - 548  (for 730-day products)
    row('SKU026','Vitamin K2 MK-7 100mcg 60 Capsules','Life Extension','Vitamins','2936.29',
        'Menaquinone-7 from Natto, Cellulose, Calcium Phosphate','B26-026',558,730,190,14.99,'yes','Japan'),   # breach in 10d
    row('SKU027','CoQ10 Ubiquinol 100mg 60 Capsules','Jarrow Formulas','Vitamins','2106.90',
        'Ubiquinol CoQ10, Sunflower Oil, Beeswax, Cellulose','B26-027',568,730,225,21.99,'yes','Japan'),       # breach in 20d
    row('SKU028','Folate 5-MTHF 800mcg 100 Capsules','Thorne Research','Vitamins','2936.29',
        '5-Methyltetrahydrofolate Calcium Salt, Cellulose, Magnesium Citrate','B26-028',578,730,195,16.99,'yes','USA'),  # breach in 30d
    row('SKU029','Vitamin E Mixed Tocopherols 400IU 100 Capsules','NOW Foods','Vitamins','2936.28',
        'd-Alpha Tocopherol, d-Beta d-Gamma d-Delta Tocopherols, Cellulose, Magnesium Stearate','B26-029',588,730,280,11.99,'yes','USA'),  # breach in 40d
    row('SKU030','Selenium plus Molybdenum 90 Capsules','NOW Foods','Minerals','2106.90',
        'Selenium Amino Acid Chelate, Molybdenum Glycinate Chelate, Cellulose, Stearic Acid','B26-030',598,730,145,9.99,'yes','USA'),  # breach in 50d
    row('SKU031','Iodine 225mcg 180 Capsules','Biotics Research','Minerals','2106.90',
        'Potassium Iodide, Kelp Powder, Cellulose, Stearic Acid','B26-031',608,730,145,14.49,'yes','USA'),     # breach in 60d
    row('SKU032','Chromium Picolinate 200mcg 100 Capsules','NOW Foods','Minerals','2106.90',
        'Chromium Picolinate, Cellulose, Magnesium Stearate','B26-032',618,730,310,7.99,'yes','USA'),          # breach in 70d
    row('SKU033','Iron Bisglycinate 25mg 90 Capsules','Thorne Research','Minerals','2106.90',
        'Iron Bisglycinate Chelate, Hypromellose, Magnesium Citrate','B26-033',628,730,165,14.99,'yes','USA'), # breach in 80d
    row('SKU034','Manganese 10mg 250 Capsules','NOW Foods','Minerals','2106.90',
        'Manganese Glycinate Chelate, Cellulose, Magnesium Stearate','B26-034',638,730,145,9.99,'yes','USA'),  # breach in 90d
    # 548-day products: breach_days_UAE = days_remaining - 411
    row('SKU035','Digestive Enzymes 90 Capsules','NOW Foods','Digestive','2106.90',
        'Amylase, Protease, Lipase, Lactase, Cellulase, Bromelain, Papain, Cellulose','B26-035',421,548,145,17.99,'yes','USA'),  # breach in 10d
    row('SKU036','Milk Thistle 300mg 100 Capsules','NOW Foods','Herbal','1302.19',
        'Milk Thistle Extract 80% Silymarin, Cellulose, Magnesium Stearate','B26-036',431,548,210,11.49,'yes','Europe'), # breach in 20d
    row('SKU037','Reishi Mushroom 500mg 100 Capsules','NOW Foods','Immunity','1302.19',
        'Reishi Mushroom Extract Ganoderma lucidum, Cellulose, Magnesium Stearate','B26-037',441,548,185,17.49,'yes','China'), # breach in 30d

    # ── Zone C: UAE shelf life FAILED, KSA/others still CLEAR ───────────────
    # 730-day: 365 <= days_remaining <= 547  (50–75%)
    row('SKU038','Saw Palmetto 320mg 60 Capsules','NOW Foods','Herbal','1302.19',
        'Saw Palmetto Berry Powder, Cellulose, Magnesium Stearate','B26-038',380,730,155,16.99,'yes','USA'),   # 52%
    row('SKU039','Valerian Root 500mg 100 Capsules','Natures Way','Herbal','1211.90',
        'Valerian Root Powder, Cellulose, Magnesium Stearate','B26-039',400,730,130,8.99,'yes','Europe'),      # 55%
    row('SKU040','Echinacea 400mg 100 Capsules','Natures Way','Immunity','1211.90',
        'Echinacea purpurea Aerial Parts Powder, Cellulose, Magnesium Stearate','B26-040',420,730,200,9.99,'yes','USA'),  # 58%
    row('SKU041','Elderberry 1000mg 60 Capsules','Natures Answer','Immunity','1302.19',
        'Black Elderberry Extract Sambucus nigra, Cellulose, Magnesium Stearate','B26-041',440,730,175,16.99,'yes','USA'), # 60%
    row('SKU042','Lemon Balm 500mg 100 Capsules','NOW Foods','Mood','1211.90',
        'Lemon Balm Leaf Powder Melissa officinalis, Cellulose, Magnesium Stearate','B26-042',460,730,155,9.99,'yes','Europe'), # 63%
    row('SKU043','Passionflower 350mg 90 Capsules','NOW Foods','Mood','1211.90',
        'Passionflower Aerial Parts Passiflora incarnata, Cellulose, Magnesium Stearate','B26-043',480,730,135,9.49,'yes','Europe'), # 66%
    row('SKU044','St Johns Wort 300mg 100 Tablets','Natures Sunshine','Mood','1302.19',
        'Hypericum perforatum Extract 0.3% Hypericin, Cellulose, Stearic Acid','B26-044',500,730,120,10.49,'yes','Germany'), # 68%
    row('SKU045','Bacopa Monnieri 320mg 60 Capsules','Jarrow Formulas','Cognitive','1302.19',
        'Bacopa monnieri Leaf Extract 20% Bacosides, Cellulose, Magnesium Stearate','B26-045',520,730,125,18.49,'yes','India'), # 71%
    row('SKU046','Saffron Extract 88.5mg 60 Capsules','Life Extension','Mood','1302.19',
        'Affron Saffron Extract Crocus sativus, Cellulose, Magnesium Stearate','B26-046',535,730,85,21.99,'yes','Spain'),    # 73%
    # 548-day: 274 <= days_remaining <= 410
    row('SKU047','Chlorella Powder 200g','Sun Chlorella','Superfoods','2106.90',
        'Chlorella Broken Cell Wall Powder','B26-047',280,548,92,24.99,'yes','Japan'),  # 51%
    row('SKU048','Green Tea Extract 400mg 100 Capsules','NOW Foods','Antioxidants','2106.90',
        'Green Tea Extract 50% EGCG Camellia sinensis, Cellulose, Magnesium Stearate','B26-048',310,548,165,14.49,'yes','China'), # 57%
    row('SKU049','Ginger Root 550mg 100 Capsules','NOW Foods','Digestive','1211.90',
        'Ginger Root Powder Zingiber officinale, Cellulose, Magnesium Stearate','B26-049',340,548,190,7.99,'yes','India'),  # 62%
    row('SKU050','Cinnamon Bark 600mg 120 Capsules','NOW Foods','Metabolic','1302.19',
        'Ceylon Cinnamon Bark Powder Cinnamomum verum, Cellulose, Magnesium Stearate','B26-050',370,548,165,8.49,'yes','Sri Lanka'), # 68%
    row('SKU051','Fenugreek 610mg 100 Capsules','NOW Foods','Herbal','1211.90',
        'Fenugreek Seed Powder Trigonella foenum-graecum, Cellulose, Magnesium Stearate','B26-051',400,548,145,7.49,'yes','India'), # 73%
    row('SKU052','Ginkgo Biloba 60mg 60 Tablets','Solgar','Herbal','1302.19',
        'Ginkgo Biloba Leaf Extract 24% Flavone Glycosides, Cellulose, Stearic Acid','B26-052',408,548,130,19.99,'yes','China'), # 74.5% — right on UAE edge

    # ── Zone D: ALL shelf life failed (<50% remaining) ───────────────────────
    row('SKU053','Vitamin A 10000IU 100 Capsules','NOW Foods','Vitamins','2936.21',
        'Vitamin A Palmitate, Cellulose, Magnesium Stearate','B26-053',350,730,195,8.49,'yes','USA'),           # 48%
    row('SKU054','Biotin 5000mcg 60 Capsules','NOW Foods','Beauty','2936.29',
        'Biotin, Cellulose, Magnesium Stearate','B26-054',300,730,285,9.49,'yes','USA'),                        # 41%
    row('SKU055','Pre-Workout Energy Powder 300g','Legion Athletics','Sports','2106.90',
        'Citrulline Malate, Beta-Alanine, Caffeine Anhydrous 350mg, L-Theanine, Alpha-GPC, Natural Flavors','B26-055',200,730,65,44.99,'yes','USA'), # 27%
    row('SKU056','Protein Bar Variety 12-Pack','Quest Nutrition','Protein','2106.90',
        'Whey Protein Isolate, Milk Protein Isolate, Almonds, Erythritol, Natural Flavors, Sunflower Lecithin','B26-056',250,548,200,24.99,'yes','USA'), # 46%
    row('SKU057','Probiotic 30 Billion 60 Capsules','Jarrow Formulas','Probiotics','2106.90',
        'Lactobacillus acidophilus, Bifidobacterium lactis, L. rhamnosus, L. gasseri, Cellulose, Maltodextrin','B26-057',100,365,95,22.99,'yes','USA'), # 27%
    row('SKU058','NAD+ Nicotinamide Riboside 300mg 60 Caps','Tru Niagen','Antioxidants','2106.90',
        'Nicotinamide Riboside Chloride, Cellulose, Magnesium Stearate','B26-058',150,548,80,44.99,'yes','USA'), # 27%
    row('SKU059','Acetyl L-Carnitine 500mg 100 Capsules','Jarrow Formulas','Cognitive','2922.41',
        'Acetyl L-Carnitine HCl, Cellulose, Magnesium Stearate','B26-059',50,365,185,14.99,'yes','Italy'),      # 14% — nearly expired
    row('SKU060','Magnesium Citrate 250mg (old batch)','NOW Foods','Minerals','2106.90',
        'Magnesium Citrate, Cellulose, Magnesium Stearate','B26-060',-15,365,310,12.49,'yes','USA'),             # EXPIRED

    # ── Zone E: INGREDIENT blocked ───────────────────────────────────────────
    row('SKU061','CBD Oil 1000mg 30ml','Charlottes Web','CBD','2934.99',
        'Hemp Extract Aerial Parts, Fractionated Coconut Oil, Natural Flavor, Cannabidiol CBD','B26-061',600,730,60,59.99,'yes','USA'),
    row('SKU062','CBD Gummies 25mg 30 Count','Green Roads','CBD','2934.99',
        'Hemp-Derived CBD Cannabidiol, Glucose Syrup, Sugar, Pectin, Citric Acid, Natural Flavors','B26-062',580,730,45,34.99,'yes','USA'),
    row('SKU063','DMAA Pre-Workout 300g','Jack3d','Pre-workout','2106.90',
        'Caffeine Anhydrous, 1,3-Dimethylamylamine DMAA, Beta-Alanine, Creatine Monohydrate, Citric Acid','B26-063',700,730,30,29.99,'no','USA'),
    row('SKU064','Ephedra Extract 12.5mg 100 Tablets','Generic Brand','Weight','1302.19',
        'Ephedra sinica Extract 8% Ephedrine Alkaloids, Caffeine Anhydrous, Guarana Seed Extract, Cellulose','B26-064',650,730,25,19.99,'no','China'),
    row('SKU065','Kava Root Extract 250mg 60 Capsules','NOW Foods','Herbal','1302.19',
        'Kava Root Extract Piper methysticum 30% Kavalactones, Cellulose, Magnesium Stearate','B26-065',680,730,80,14.99,'yes','Pacific Islands'),
    row('SKU066','Yohimbe Bark 500mg 90 Capsules','NOW Foods','Herbal','1302.19',
        'Yohimbe Bark Extract standardized to 8% Yohimbine, Gelatin, Magnesium Stearate','B26-066',660,730,95,12.99,'no','Africa'),
    row('SKU067','5-HTP 100mg 60 Capsules','NOW Foods','Mood','2934.99',
        '5-Hydroxytryptophan 5-HTP from Griffonia simplicifolia, Cellulose, Magnesium Stearate','B26-067',640,730,145,12.99,'yes','Africa'),
    row('SKU068','Bitter Orange Synephrine 300mg 60 Capsules','NOW Foods','Weight','1302.19',
        'Bitter Orange Extract Citrus aurantium standardized to 6% Synephrine, Cellulose, Magnesium Stearate','B26-068',620,730,110,12.49,'yes','China'),

    # ── Zone F: RX_ONLY (melatonin — classified as medicament in all GCC) ────
    row('SKU069','Melatonin 3mg 120 Tablets','Natrol','Sleep','2934.99',
        'Melatonin, Dicalcium Phosphate, Cellulose, Stearic Acid, Silica','B26-069',700,730,450,8.49,'yes','USA'),
    row('SKU070','Melatonin 5mg 60 Tablets','NOW Foods','Sleep','2934.99',
        'Melatonin, Cellulose, Stearic Acid, Silica, Magnesium Stearate','B26-070',680,730,380,7.99,'yes','USA'),
    row('SKU071','Melatonin 10mg Extended Release 60 Capsules','Life Extension','Sleep','2934.99',
        'Melatonin, Cellulose, Vegetable Stearate, Silica','B26-071',660,730,280,9.49,'yes','USA'),

    # ── Zone G: HALAL cert needed (animal-derived, long expiry, no cert) ─────
    row('SKU072','Omega-3 Fish Oil 1000mg 100 Softgels','Nordic Naturals','Omega','1504.20',
        'Fish Oil Concentrate from Anchovies and Sardines, Gelatin, Glycerin, Water, Natural Lemon Flavor','B26-072',700,730,150,12.49,'no','Norway'),
    row('SKU073','Omega-3 Fish Oil 2000mg 60 Softgels','Carlson Labs','Omega','1504.20',
        'Norwegian Fish Oil, Gelatin, Glycerin, Purified Water, Natural Lemon Oil','B26-073',680,730,200,19.99,'no','Norway'),
    row('SKU074','Collagen Peptides Powder 284g','Vital Proteins','Beauty','3504.00',
        'Bovine Hide Collagen Peptides from grass-fed cows, Vitamin C','B26-074',660,730,175,24.99,'no','USA'),
    row('SKU075','Marine Collagen 120 Capsules','NeoCell','Beauty','3504.00',
        'Marine Collagen Peptides from Fish, Vitamin C, Hyaluronic Acid, Gelatin','B26-075',640,730,130,21.99,'no','USA'),
    row('SKU076','Hydrolyzed Collagen Type I and III 450g','Great Lakes Wellness','Beauty','3504.00',
        'Hydrolyzed Bovine Collagen Peptides, Natural Flavor','B26-076',620,730,88,24.99,'no','USA'),
    row('SKU077','Whey Protein Isolate Vanilla 2lb','Optimum Nutrition','Protein','2106.10',
        'Whey Protein Isolate, Natural Vanilla Flavor, Sunflower Lecithin, Sucralose','B26-077',600,730,88,34.99,'no','USA'),
    row('SKU078','Whey Protein Chocolate 5lb','Optimum Nutrition','Protein','2106.10',
        'Whey Protein Concentrate, Cocoa Powder, Natural Flavors, Sunflower Lecithin, Sucralose','B26-078',580,730,42,54.99,'no','USA'),
    row('SKU079','Casein Protein Chocolate 2lb','Optimum Nutrition','Protein','2106.10',
        'Micellar Casein, Cocoa, Natural Flavors, Sucralose, Acesulfame Potassium','B26-079',560,730,72,34.99,'no','USA'),
    row('SKU080','Glucosamine Sulfate 1000mg 120 Tablets','Doctors Best','Joint Health','2106.90',
        'Glucosamine Sulfate 2KCl from Shellfish, Cellulose, Vegetable Stearate','B26-080',700,730,190,19.99,'no','USA'),
    row('SKU081','Chondroitin Sulfate 400mg 90 Capsules','NOW Foods','Joint Health','2106.90',
        'Chondroitin Sulfate from Bovine Trachea, Cellulose, Magnesium Stearate','B26-081',680,730,165,24.99,'no','USA'),
    row('SKU082','Vitamin D3 5000IU 240 Softgels','NOW Foods','Vitamins','2936.29',
        'Vitamin D3 Cholecalciferol, Soybean Oil, Gelatin, Glycerin, Water','B26-082',660,730,240,14.99,'no','USA'),
    row('SKU083','Vitamin E 400IU 100 Softgels','NOW Foods','Vitamins','2936.28',
        'd-Alpha Tocopherol, Soybean Oil, Gelatin, Glycerin, Water','B26-083',640,730,280,11.99,'no','USA'),
    row('SKU084','Astaxanthin 4mg 60 Softgels','NOW Foods','Antioxidants','2106.90',
        'AstaREAL Astaxanthin from Haematococcus pluvialis, Olive Oil, Gelatin, Glycerin, Water','B26-084',620,730,155,19.99,'no','Japan'),
    row('SKU085','Lutein 20mg 60 Softgels','NOW Foods','Eye Health','2106.90',
        'Lutein from Marigold Tagetes erecta, Zeaxanthin, Olive Oil, Gelatin, Glycerin, Water','B26-085',600,730,130,16.99,'no','India'),
    row('SKU086','CoQ10 100mg 60 Softgels','Jarrow Formulas','Vitamins','2106.90',
        'Coenzyme Q10 Ubiquinone, Rice Bran Oil, Gelatin, Glycerin, Purified Water','B26-086',580,730,225,21.99,'no','Japan'),
    row('SKU087','Vitamin K2 MK-7 100mcg Softgels','NOW Foods','Vitamins','2936.29',
        'Menaquinone-7 from Natto, Extra Virgin Olive Oil, Gelatin, Glycerin, Water','B26-087',560,730,190,14.99,'no','USA'),
    row('SKU088','Phosphatidylserine 100mg 60 Softgels','NOW Foods','Cognitive','2106.90',
        'Phosphatidylserine from Soy Lecithin, Soybean Oil, Gelatin, Glycerin','B26-088',700,730,140,21.99,'no','USA'),
    row('SKU089','Saw Palmetto 320mg 60 Softgels','NOW Foods','Herbal','1302.19',
        'Saw Palmetto Berry Extract, Olive Oil, Gelatin, Glycerin, Water','B26-089',680,730,155,16.99,'no','USA'),
    row('SKU090','Evening Primrose Oil 500mg 100 Softgels','NOW Foods','Womens Health','1515.90',
        'Evening Primrose Oil Oenothera biennis, Gelatin, Glycerin, Water','B26-090',660,730,145,11.99,'no','USA'),
    row('SKU091','Cod Liver Oil 1000mg 90 Softgels','NOW Foods','Omega','1504.20',
        'Cod Liver Oil Gadus morhua, Vitamin A, Vitamin D3, Gelatin, Glycerin, Water','B26-091',640,730,160,12.99,'no','Norway'),
    row('SKU092','Bone Broth Protein Powder 400g','Ancient Nutrition','Protein','3504.00',
        'Hydrolyzed Bovine Bone Broth Protein Concentrate, Natural Flavors','B26-092',620,730,65,44.99,'no','USA'),
    row('SKU093','Fish Collagen Peptides 5000mg Powder','Vital Proteins','Beauty','3504.00',
        'Hydrolyzed Fish Collagen Peptides Type I, Vitamin C, Natural Flavor','B26-093',600,730,80,32.99,'no','USA'),

    # ── Zone H: Mixed — HALAL + other status ─────────────────────────────────
    row('SKU094','Omega-3 Fish Oil UAE Breach Imminent','Garden of Life','Omega','1504.20',
        'Fish Oil from Wild Sardines Mackerel Anchovies, Gelatin, Glycerin, Water, Rosemary Extract','B26-094',570,730,120,14.99,'no','USA'),  # Halal + UAE breach in 22d
    row('SKU095','Collagen Peptides UAE-Failed KSA-Clear','Sports Research','Beauty','3504.00',
        'Bovine Collagen Peptides Type I and III, Sunflower Lecithin','B26-095',400,730,160,29.99,'no','USA'), # Halal + UAE fail, KSA clear
    row('SKU096','Whey Protein All-Failed','Dymatize','Protein','2106.10',
        'Whey Protein Isolate, Soy Lecithin, Natural Flavors, Sucralose','B26-096',200,730,55,32.99,'no','USA'), # Halal + ALL shelf fail
    row('SKU097','Hyaluronic Acid 120mg Gelatin Capsule','Solgar','Beauty','2106.90',
        'Sodium Hyaluronate, Gelatin, Water','B26-097',580,730,165,18.99,'no','USA'),                          # Halal
    row('SKU098','Vitamin D3+K2 60 Softgels','Life Extension','Vitamins','2936.29',
        'Vitamin D3 Cholecalciferol, Vitamin K2 MK-7 from Natto, Olive Oil, Gelatin, Glycerin','B26-098',640,730,170,15.99,'no','USA'), # Halal
    row('SKU099','Astaxanthin 12mg 60 Softgels','Sports Research','Antioxidants','2106.90',
        'Astaxanthin from Haematococcus pluvialis, Coconut Oil, Gelatin, Glycerin, Water','B26-099',660,730,95,29.99,'no','USA'),  # Halal
    row('SKU100','Glucosamine Chondroitin MSM 90 Tablets','NOW Foods','Joint Health','2106.90',
        'Glucosamine Sulfate from Shellfish, Chondroitin Sulfate from Bovine, MSM Methylsulfonylmethane, Cellulose','B26-100',700,730,175,21.99,'no','USA'), # Halal
]

HEADERS = ['sku_id','product_name','brand','category','hs_code','ingredients',
           'batch_id','manufacture_date','expiry_date','total_shelf_life_days',
           'qty_on_hand','unit_cost_usd','halal_certified','country_of_origin']

out = os.path.join(os.path.dirname(__file__), 'mock_inventory.csv')
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=HEADERS)
    w.writeheader()
    w.writerows(PRODUCTS)

print(f"Written {len(PRODUCTS)} products to {out}")
