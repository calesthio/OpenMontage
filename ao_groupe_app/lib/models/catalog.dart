import 'package:flutter/material.dart';

class CatalogCategory {
  const CatalogCategory({
    required this.id,
    required this.icon,
    required this.color,
  });

  final String id;
  final IconData icon;
  final Color color;
}

class CatalogProduct {
  const CatalogProduct({
    required this.id,
    required this.categoryId,
    required this.names,
    required this.brand,
    required this.price,
    required this.wholesalePrice,
    required this.stock,
    required this.icon,
    required this.color,
    required this.specification,
    this.badge,
    this.quoteOnly = false,
    this.isNew = false,
    this.isPopular = false,
  });

  final String id;
  final String categoryId;
  final Map<String, String> names;
  final String brand;
  final int price;
  final int wholesalePrice;
  final int stock;
  final IconData icon;
  final Color color;
  final String specification;
  final String? badge;
  final bool quoteOnly;
  final bool isNew;
  final bool isPopular;

  String name(String languageCode) => names[languageCode] ?? names['ar']!;

  int priceForQuantity(int quantity) => quantity >= 5 ? wholesalePrice : price;
}

const catalogCategories = [
  CatalogCategory(
      id: 'cables', icon: Icons.cable_rounded, color: Color(0xFF1D4ED8)),
  CatalogCategory(
      id: 'breakers',
      icon: Icons.electrical_services_rounded,
      color: Color(0xFF7C3AED)),
  CatalogCategory(
      id: 'lighting',
      icon: Icons.lightbulb_outline_rounded,
      color: Color(0xFFF59E0B)),
  CatalogCategory(
      id: 'solar', icon: Icons.solar_power_rounded, color: Color(0xFF16A34A)),
  CatalogCategory(
      id: 'switches', icon: Icons.toggle_on_rounded, color: Color(0xFFEC4899)),
  CatalogCategory(
      id: 'pumps', icon: Icons.water_drop_outlined, color: Color(0xFF0891B2)),
  CatalogCategory(
      id: 'tools', icon: Icons.handyman_outlined, color: Color(0xFFEA580C)),
  CatalogCategory(
      id: 'custom',
      icon: Icons.precision_manufacturing_outlined,
      color: Color(0xFF475569)),
];

const catalogProducts = [
  CatalogProduct(
    id: 'cable-25',
    categoryId: 'cables',
    names: {
      'ar': 'كابل نحاسي 2.5 مم²',
      'fr': 'Câble cuivre 2,5 mm²',
      'en': '2.5 mm² copper cable'
    },
    brand: 'El Djazair Élec',
    price: 180,
    wholesalePrice: 155,
    stock: 420,
    icon: Icons.cable_rounded,
    color: Color(0xFF2563EB),
    specification: 'copper25',
    badge: 'popular',
    isPopular: true,
  ),
  CatalogProduct(
    id: 'cable-15',
    categoryId: 'cables',
    names: {
      'ar': 'كابل نحاسي 1.5 مم²',
      'fr': 'Câble cuivre 1,5 mm²',
      'en': '1.5 mm² copper cable'
    },
    brand: 'El Djazair Élec',
    price: 125,
    wholesalePrice: 108,
    stock: 360,
    icon: Icons.cable_rounded,
    color: Color(0xFF3B82F6),
    specification: 'copper15',
  ),
  CatalogProduct(
    id: 'cable-4',
    categoryId: 'cables',
    names: {
      'ar': 'كابل نحاسي 4 مم²',
      'fr': 'Câble cuivre 4 mm²',
      'en': '4 mm² copper cable'
    },
    brand: 'El Djazair Élec',
    price: 285,
    wholesalePrice: 248,
    stock: 18,
    icon: Icons.cable_rounded,
    color: Color(0xFF60A5FA),
    specification: 'copper4',
  ),
  CatalogProduct(
    id: 'breaker-20',
    categoryId: 'breakers',
    names: {
      'ar': 'قاطع آلي MCB 20A',
      'fr': 'Disjoncteur MCB 20 A',
      'en': 'MCB circuit breaker 20 A'
    },
    brand: 'Voltara',
    price: 950,
    wholesalePrice: 820,
    stock: 76,
    icon: Icons.electrical_services_rounded,
    color: Color(0xFF8B5CF6),
    specification: 'breaker20',
    badge: 'new',
    isNew: true,
  ),
  CatalogProduct(
    id: 'breaker-diff',
    categoryId: 'breakers',
    names: {
      'ar': 'قاطع تفاضلي 40A',
      'fr': 'Disjoncteur différentiel 40 A',
      'en': 'RCD circuit breaker 40 A'
    },
    brand: 'Voltara',
    price: 4850,
    wholesalePrice: 4320,
    stock: 34,
    icon: Icons.electrical_services_rounded,
    color: Color(0xFFA78BFA),
    specification: 'breaker40',
  ),
  CatalogProduct(
    id: 'led-e27',
    categoryId: 'lighting',
    names: {
      'ar': 'مصباح LED اقتصادي E27',
      'fr': 'Ampoule LED économique E27',
      'en': 'Energy-saving LED bulb E27'
    },
    brand: 'Lumière DZ',
    price: 450,
    wholesalePrice: 360,
    stock: 230,
    icon: Icons.lightbulb_rounded,
    color: Color(0xFFFBBF24),
    specification: 'led9',
    badge: 'offer',
    isPopular: true,
  ),
  CatalogProduct(
    id: 'spot-led',
    categoryId: 'lighting',
    names: {
      'ar': 'سبوت LED سقفي 12 واط',
      'fr': 'Spot LED plafond 12 W',
      'en': '12 W recessed LED spotlight'
    },
    brand: 'Lumière DZ',
    price: 780,
    wholesalePrice: 665,
    stock: 64,
    icon: Icons.lightbulb_outline_rounded,
    color: Color(0xFFF59E0B),
    specification: 'spot12',
    isNew: true,
  ),
  CatalogProduct(
    id: 'floodlight',
    categoryId: 'lighting',
    names: {
      'ar': 'كشاف خارجي LED 50 واط',
      'fr': 'Projecteur LED extérieur 50 W',
      'en': '50 W outdoor LED floodlight'
    },
    brand: 'Lumière DZ',
    price: 3200,
    wholesalePrice: 2780,
    stock: 0,
    icon: Icons.wb_twilight_rounded,
    color: Color(0xFFFDE68A),
    specification: 'flood50',
  ),
  CatalogProduct(
    id: 'panel-550',
    categoryId: 'solar',
    names: {
      'ar': 'لوح شمسي أحادي 550 واط',
      'fr': 'Panneau solaire mono 550 W',
      'en': '550 W monocrystalline solar panel'
    },
    brand: 'SunVolt',
    price: 32500,
    wholesalePrice: 29900,
    stock: 22,
    icon: Icons.solar_power_rounded,
    color: Color(0xFF22C55E),
    specification: 'panel550',
    badge: 'popular',
    isPopular: true,
  ),
  CatalogProduct(
    id: 'inverter-3k',
    categoryId: 'solar',
    names: {
      'ar': 'عاكس شمسي هجين 3 كيلوواط',
      'fr': 'Onduleur solaire hybride 3 kW',
      'en': '3 kW hybrid solar inverter'
    },
    brand: 'SunVolt',
    price: 89500,
    wholesalePrice: 84200,
    stock: 8,
    icon: Icons.bolt_rounded,
    color: Color(0xFF4ADE80),
    specification: 'inverter3k',
    isNew: true,
  ),
  CatalogProduct(
    id: 'battery-200',
    categoryId: 'solar',
    names: {
      'ar': 'بطارية جل شمسية 200Ah',
      'fr': 'Batterie gel solaire 200 Ah',
      'en': '200 Ah solar gel battery'
    },
    brand: 'SunVolt',
    price: 67800,
    wholesalePrice: 63400,
    stock: 13,
    icon: Icons.battery_charging_full_rounded,
    color: Color(0xFF86EFAC),
    specification: 'battery200',
  ),
  CatalogProduct(
    id: 'switch-set',
    categoryId: 'switches',
    names: {
      'ar': 'طقم مفتاح ومأخذ عصري',
      'fr': 'Ensemble interrupteur et prise moderne',
      'en': 'Modern switch and outlet set'
    },
    brand: 'CasaVolt',
    price: 1250,
    wholesalePrice: 1060,
    stock: 92,
    icon: Icons.toggle_on_rounded,
    color: Color(0xFFF472B6),
    specification: 'switch',
    isNew: true,
  ),
  CatalogProduct(
    id: 'socket-ip44',
    categoryId: 'switches',
    names: {
      'ar': 'مأخذ مقاوم للماء IP44',
      'fr': 'Prise étanche IP44',
      'en': 'IP44 waterproof outlet'
    },
    brand: 'CasaVolt',
    price: 1850,
    wholesalePrice: 1590,
    stock: 29,
    icon: Icons.power_rounded,
    color: Color(0xFFFB7185),
    specification: 'socket',
  ),
  CatalogProduct(
    id: 'pump-1hp',
    categoryId: 'pumps',
    names: {
      'ar': 'مضخة مياه منزلية 1 حصان',
      'fr': 'Pompe à eau domestique 1 CV',
      'en': '1 HP home water pump'
    },
    brand: 'AquaForce',
    price: 18900,
    wholesalePrice: 17300,
    stock: 16,
    icon: Icons.water_drop_rounded,
    color: Color(0xFF22D3EE),
    specification: 'pump1hp',
  ),
  CatalogProduct(
    id: 'multimeter',
    categoryId: 'tools',
    names: {
      'ar': 'جهاز قياس رقمي متعدد',
      'fr': 'Multimètre numérique',
      'en': 'Digital multimeter'
    },
    brand: 'ProMesure',
    price: 4300,
    wholesalePrice: 3720,
    stock: 41,
    icon: Icons.speed_rounded,
    color: Color(0xFFFB923C),
    specification: 'multimeter',
    badge: 'popular',
    isPopular: true,
  ),
  CatalogProduct(
    id: 'solar-lantern',
    categoryId: 'solar',
    names: {
      'ar': 'كشاف شمسي جداري',
      'fr': 'Applique solaire murale',
      'en': 'Solar wall light'
    },
    brand: 'SunVolt',
    price: 5400,
    wholesalePrice: 4720,
    stock: 3,
    icon: Icons.wb_twilight_rounded,
    color: Color(0xFF4ADE80),
    specification: 'solarLantern',
    badge: 'lowStock',
  ),
  CatalogProduct(
    id: 'distribution-panel',
    categoryId: 'breakers',
    names: {
      'ar': 'لوحة توزيع كهربائية 12 خطاً',
      'fr': 'Tableau électrique 12 modules',
      'en': '12-way distribution board'
    },
    brand: 'Voltara',
    price: 6250,
    wholesalePrice: 5590,
    stock: 25,
    icon: Icons.view_quilt_rounded,
    color: Color(0xFFC4B5FD),
    specification: 'board12',
  ),
  CatalogProduct(
    id: 'custom-enclosure',
    categoryId: 'custom',
    names: {
      'ar': 'صندوق صناعي حسب الطلب',
      'fr': 'Coffret industriel sur mesure',
      'en': 'Custom industrial enclosure'
    },
    brand: 'Atelier AO',
    price: 0,
    wholesalePrice: 0,
    stock: 0,
    icon: Icons.precision_manufacturing_rounded,
    color: Color(0xFF94A3B8),
    specification: 'custom',
    quoteOnly: true,
  ),
];

String formatDzd(int amount) {
  final digits = amount.toString();
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index++) {
    if (index > 0 && (digits.length - index) % 3 == 0) buffer.write(' ');
    buffer.write(digits[index]);
  }
  return '$buffer دج';
}

Map<String, String> localizedSpecification(String id, String languageCode) {
  const specifications = <String, Map<String, Map<String, String>>>{
    'copper25': {
      'ar': {
        'material': 'نحاس مرن',
        'section': '2.5 مم²',
        'voltage': '450/750 فولت',
        'pack': 'سعر المتر'
      },
      'fr': {
        'material': 'Cuivre souple',
        'section': '2,5 mm²',
        'voltage': '450/750 V',
        'pack': 'Prix au mètre'
      },
      'en': {
        'material': 'Flexible copper',
        'section': '2.5 mm²',
        'voltage': '450/750 V',
        'pack': 'Price per metre'
      },
    },
    'copper15': {
      'ar': {
        'material': 'نحاس مرن',
        'section': '1.5 مم²',
        'voltage': '450/750 فولت',
        'pack': 'سعر المتر'
      },
      'fr': {
        'material': 'Cuivre souple',
        'section': '1,5 mm²',
        'voltage': '450/750 V',
        'pack': 'Prix au mètre'
      },
      'en': {
        'material': 'Flexible copper',
        'section': '1.5 mm²',
        'voltage': '450/750 V',
        'pack': 'Price per metre'
      },
    },
    'copper4': {
      'ar': {
        'material': 'نحاس مرن',
        'section': '4 مم²',
        'voltage': '450/750 فولت',
        'pack': 'سعر المتر'
      },
      'fr': {
        'material': 'Cuivre souple',
        'section': '4 mm²',
        'voltage': '450/750 V',
        'pack': 'Prix au mètre'
      },
      'en': {
        'material': 'Flexible copper',
        'section': '4 mm²',
        'voltage': '450/750 V',
        'pack': 'Price per metre'
      },
    },
    'breaker20': {
      'ar': {
        'material': 'Voltara',
        'section': '20 أمبير · قطب واحد',
        'voltage': 'منحنى C · 6 كيلو أمبير',
        'pack': 'قطعة'
      },
      'fr': {
        'material': 'Voltara',
        'section': '20 A · 1 pôle',
        'voltage': 'Courbe C · 6 kA',
        'pack': 'Unité'
      },
      'en': {
        'material': 'Voltara',
        'section': '20 A · single pole',
        'voltage': 'Curve C · 6 kA',
        'pack': 'Per unit'
      },
    },
    'breaker40': {
      'ar': {
        'material': 'Voltara',
        'section': '40 أمبير · قطبان',
        'voltage': 'حساسية 30 mA',
        'pack': 'قطعة'
      },
      'fr': {
        'material': 'Voltara',
        'section': '40 A · bipolaire',
        'voltage': 'Sensibilité 30 mA',
        'pack': 'Unité'
      },
      'en': {
        'material': 'Voltara',
        'section': '40 A · double pole',
        'voltage': '30 mA sensitivity',
        'pack': 'Per unit'
      },
    },
    'led9': {
      'ar': {
        'material': 'Lumière DZ',
        'section': '9 واط · قاعدة E27',
        'voltage': '3000 كلفن · 806 لومن',
        'pack': 'قطعة'
      },
      'fr': {
        'material': 'Lumière DZ',
        'section': '9 W · culot E27',
        'voltage': '3000 K · 806 lm',
        'pack': 'Unité'
      },
      'en': {
        'material': 'Lumière DZ',
        'section': '9 W · E27 base',
        'voltage': '3000 K · 806 lm',
        'pack': 'Per unit'
      },
    },
    'spot12': {
      'ar': {
        'material': 'Lumière DZ',
        'section': '12 واط · فتحة 90 مم',
        'voltage': '4000 كلفن · IP20',
        'pack': 'قطعة'
      },
      'fr': {
        'material': 'Lumière DZ',
        'section': '12 W · découpe 90 mm',
        'voltage': '4000 K · IP20',
        'pack': 'Unité'
      },
      'en': {
        'material': 'Lumière DZ',
        'section': '12 W · 90 mm cutout',
        'voltage': '4000 K · IP20',
        'pack': 'Per unit'
      },
    },
    'flood50': {
      'ar': {
        'material': 'Lumière DZ',
        'section': '50 واط · ألمنيوم',
        'voltage': '6500 كلفن · IP65',
        'pack': 'قطعة'
      },
      'fr': {
        'material': 'Lumière DZ',
        'section': '50 W · aluminium',
        'voltage': '6500 K · IP65',
        'pack': 'Unité'
      },
      'en': {
        'material': 'Lumière DZ',
        'section': '50 W · aluminium',
        'voltage': '6500 K · IP65',
        'pack': 'Per unit'
      },
    },
    'panel550': {
      'ar': {
        'material': 'SunVolt · أحادي البلورة',
        'section': '550 واط ذروة',
        'voltage': 'كفاءة 21.3٪ · ضمان 12 سنة',
        'pack': 'لوح'
      },
      'fr': {
        'material': 'SunVolt · monocristallin',
        'section': '550 Wc',
        'voltage': 'Rendement 21,3 % · garantie 12 ans',
        'pack': 'Panneau'
      },
      'en': {
        'material': 'SunVolt · monocrystalline',
        'section': '550 W peak',
        'voltage': '21.3% efficiency · 12-year warranty',
        'pack': 'Panel'
      },
    },
    'inverter3k': {
      'ar': {
        'material': 'SunVolt · هجين',
        'section': '3 كيلوواط · موجة نقية',
        'voltage': '48 فولت · MPPT مدمج',
        'pack': 'قطعة'
      },
      'fr': {
        'material': 'SunVolt · hybride',
        'section': '3 kW · onde sinusoïdale pure',
        'voltage': '48 V · MPPT intégré',
        'pack': 'Unité'
      },
      'en': {
        'material': 'SunVolt · hybrid',
        'section': '3 kW · pure sine wave',
        'voltage': '48 V · built-in MPPT',
        'pack': 'Per unit'
      },
    },
    'battery200': {
      'ar': {
        'material': 'SunVolt · جل محكم',
        'section': '200 أمبير ساعة · 12 فولت',
        'voltage': 'دورة عميقة · لا يحتاج صيانة',
        'pack': 'بطارية'
      },
      'fr': {
        'material': 'SunVolt · gel étanche',
        'section': '200 Ah · 12 V',
        'voltage': 'Cycle profond · sans entretien',
        'pack': 'Batterie'
      },
      'en': {
        'material': 'SunVolt · sealed gel',
        'section': '200 Ah · 12 V',
        'voltage': 'Deep cycle · maintenance-free',
        'pack': 'Battery'
      },
    },
    'switch': {
      'ar': {
        'material': 'CasaVolt · أبيض مطفي',
        'section': 'مفتاح مفرد + مأخذ',
        'voltage': '230 فولت · تصميم حديث',
        'pack': 'طقم'
      },
      'fr': {
        'material': 'CasaVolt · blanc mat',
        'section': 'Interrupteur simple + prise',
        'voltage': '230 V · design moderne',
        'pack': 'Ensemble'
      },
      'en': {
        'material': 'CasaVolt · matte white',
        'section': 'Single switch + socket',
        'voltage': '230 V · modern design',
        'pack': 'Set'
      },
    },
    'socket': {
      'ar': {
        'material': 'CasaVolt · غطاء واقٍ',
        'section': 'مأخذ 16 أمبير',
        'voltage': '230 فولت · حماية IP44',
        'pack': 'قطعة'
      },
      'fr': {
        'material': 'CasaVolt · capot de protection',
        'section': 'Prise 16 A',
        'voltage': '230 V · protection IP44',
        'pack': 'Unité'
      },
      'en': {
        'material': 'CasaVolt · protective cover',
        'section': '16 A outlet',
        'voltage': '230 V · IP44 protection',
        'pack': 'Per unit'
      },
    },
    'pump1hp': {
      'ar': {
        'material': 'AquaForce · جسم من الحديد',
        'section': '1 حصان · رفع حتى 35 م',
        'voltage': '230 فولت · حماية حرارية',
        'pack': 'مضخة'
      },
      'fr': {
        'material': 'AquaForce · corps en fonte',
        'section': '1 CV · hauteur max. 35 m',
        'voltage': '230 V · protection thermique',
        'pack': 'Pompe'
      },
      'en': {
        'material': 'AquaForce · cast iron body',
        'section': '1 HP · up to 35 m head',
        'voltage': '230 V · thermal protection',
        'pack': 'Pump'
      },
    },
    'multimeter': {
      'ar': {
        'material': 'ProMesure · شاشة رقمية',
        'section': 'قياس 600 فولت AC/DC',
        'voltage': 'استمرارية · مقاومة · دايود',
        'pack': 'جهاز'
      },
      'fr': {
        'material': 'ProMesure · écran numérique',
        'section': 'Mesure 600 V AC/DC',
        'voltage': 'Continuité · résistance · diode',
        'pack': 'Appareil'
      },
      'en': {
        'material': 'ProMesure · digital display',
        'section': '600 V AC/DC measurement',
        'voltage': 'Continuity · resistance · diode',
        'pack': 'Meter'
      },
    },
    'solarLantern': {
      'ar': {
        'material': 'SunVolt · حساس حركة',
        'section': 'إضاءة 1200 لومن',
        'voltage': 'IP65 · شحن شمسي',
        'pack': 'كشاف'
      },
      'fr': {
        'material': 'SunVolt · détecteur de mouvement',
        'section': 'Éclairage 1200 lm',
        'voltage': 'IP65 · recharge solaire',
        'pack': 'Applique'
      },
      'en': {
        'material': 'SunVolt · motion sensor',
        'section': '1200 lm output',
        'voltage': 'IP65 · solar charging',
        'pack': 'Light'
      },
    },
    'board12': {
      'ar': {
        'material': 'Voltara · مقاوم للاشتعال',
        'section': '12 وحدة · تركيب داخلي',
        'voltage': 'IP40 · سكة DIN',
        'pack': 'لوحة'
      },
      'fr': {
        'material': 'Voltara · ignifugé',
        'section': '12 modules · pose intérieure',
        'voltage': 'IP40 · rail DIN',
        'pack': 'Tableau'
      },
      'en': {
        'material': 'Voltara · flame retardant',
        'section': '12 modules · indoor mount',
        'voltage': 'IP40 · DIN rail',
        'pack': 'Panel'
      },
    },
    'custom': {
      'ar': {
        'material': 'Atelier AO · تصنيع حسب الطلب',
        'section': 'الأبعاد والتشطيب حسب المشروع',
        'voltage': 'يتطلب عرض سعر',
        'pack': 'حسب الاتفاق'
      },
      'fr': {
        'material': 'Atelier AO · fabrication sur mesure',
        'section': 'Dimensions et finitions selon le projet',
        'voltage': 'Sur devis',
        'pack': 'Selon accord'
      },
      'en': {
        'material': 'Atelier AO · made to order',
        'section': 'Dimensions and finish to project needs',
        'voltage': 'Quote required',
        'pack': 'As agreed'
      },
    },
  };

  return specifications[id]?[languageCode] ?? specifications[id]?['ar'] ?? {};
}
