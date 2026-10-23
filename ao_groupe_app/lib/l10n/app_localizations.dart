import 'package:flutter/widgets.dart';

class AppLocalizations {
  const AppLocalizations(this.locale);

  final Locale locale;

  static const supportedLocales = [
    Locale('ar'),
    Locale('fr'),
    Locale('en'),
  ];

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  String _text(String key) {
    final languageCode = locale.languageCode;
    return _translations[languageCode]?[key] ??
        _translations['ar']![key] ??
        key;
  }

  String get appName => 'AO groupe';
  String get showcase => _text('showcase');
  String get showcaseDescription => _text('showcaseDescription');
  String get language => _text('language');
  String get gradient => _text('gradient');
  String get appearance => _text('appearance');
  String get system => _text('system');
  String get light => _text('light');
  String get dark => _text('dark');
  String get palette => _text('palette');
  String get primary => _text('primary');
  String get accent => _text('accent');
  String get lightBackground => _text('lightBackground');
  String get darkBackground => _text('darkBackground');
  String get states => _text('states');
  String get available => _text('available');
  String get outOfStock => _text('outOfStock');
  String get lowStock => _text('lowStock');
  String get components => _text('components');
  String get buttons => _text('buttons');
  String get primaryAction => _text('primaryAction');
  String get secondaryAction => _text('secondaryAction');
  String get outlinedAction => _text('outlinedAction');
  String get searchLabel => _text('searchLabel');
  String get searchHint => _text('searchHint');
  String get productTitle => _text('productTitle');
  String get productDescription => _text('productDescription');
  String get samplePrice => _text('samplePrice');
  String get previewNote => _text('previewNote');

  static const Map<String, Map<String, String>> _translations = {
    'ar': {
      'showcase': 'معاينة نظام التصميم',
      'showcaseDescription':
          'ألوان ومكونات مشتركة لـ AO groupe، مصممة لتجربة واضحة في تجارة المعدات الكهربائية والطاقة الشمسية.',
      'language': 'اللغة',
      'gradient': 'تدرج الهوية',
      'appearance': 'المظهر',
      'system': 'النظام',
      'light': 'فاتح',
      'dark': 'داكن',
      'palette': 'ألوان الهوية',
      'primary': 'الأزرق الأساسي',
      'accent': 'لون الطاقة',
      'lightBackground': 'خلفية فاتحة',
      'darkBackground': 'خلفية داكنة',
      'states': 'حالات المخزون',
      'available': 'متوفر',
      'outOfStock': 'نفد المخزون',
      'lowStock': 'مخزون منخفض',
      'components': 'المكونات المشتركة',
      'buttons': 'الأزرار',
      'primaryAction': 'إجراء أساسي',
      'secondaryAction': 'إجراء ثانوي',
      'outlinedAction': 'زر بإطار',
      'searchLabel': 'البحث عن منتج',
      'searchHint': 'مثال: مصباح LED أو كابل كهربائي',
      'productTitle': 'مصباح LED اقتصادي E27',
      'productDescription': '9 واط · ضوء أبيض دافئ',
      'samplePrice': '450 دج / قطعة',
      'previewNote': 'معاينة نظام التصميم — ليست شاشة المتجر النهائية',
    },
    'fr': {
      'showcase': 'Aperçu du système de design',
      'showcaseDescription':
          'Couleurs et composants partagés de AO groupe, pensés pour le commerce de matériel électrique et solaire.',
      'language': 'Langue',
      'gradient': 'Dégradé de marque',
      'appearance': 'Apparence',
      'system': 'Système',
      'light': 'Clair',
      'dark': 'Sombre',
      'palette': 'Couleurs de marque',
      'primary': 'Bleu principal',
      'accent': 'Couleur énergie',
      'lightBackground': 'Fond clair',
      'darkBackground': 'Fond sombre',
      'states': 'État du stock',
      'available': 'Disponible',
      'outOfStock': 'Rupture de stock',
      'lowStock': 'Stock faible',
      'components': 'Composants partagés',
      'buttons': 'Boutons',
      'primaryAction': 'Action principale',
      'secondaryAction': 'Action secondaire',
      'outlinedAction': 'Bouton contour',
      'searchLabel': 'Rechercher un produit',
      'searchHint': 'Ex. : ampoule LED ou câble électrique',
      'productTitle': 'Ampoule LED économique E27',
      'productDescription': '9 W · lumière blanc chaud',
      'samplePrice': '450 DA / pièce',
      'previewNote':
          'Aperçu du système de design — pas l’écran final du magasin',
    },
    'en': {
      'showcase': 'Design system preview',
      'showcaseDescription':
          'Shared colors and components for AO groupe, designed for a clear electrical and solar retail experience.',
      'language': 'Language',
      'gradient': 'Brand gradient',
      'appearance': 'Appearance',
      'system': 'System',
      'light': 'Light',
      'dark': 'Dark',
      'palette': 'Brand colors',
      'primary': 'Primary blue',
      'accent': 'Energy accent',
      'lightBackground': 'Light background',
      'darkBackground': 'Dark background',
      'states': 'Stock states',
      'available': 'Available',
      'outOfStock': 'Out of stock',
      'lowStock': 'Low stock',
      'components': 'Shared components',
      'buttons': 'Buttons',
      'primaryAction': 'Primary action',
      'secondaryAction': 'Secondary action',
      'outlinedAction': 'Outlined button',
      'searchLabel': 'Search products',
      'searchHint': 'Try: LED bulb or electrical cable',
      'productTitle': 'Energy-saving LED bulb E27',
      'productDescription': '9 W · warm white light',
      'samplePrice': '450 DZD / piece',
      'previewNote': 'Design system preview — not the final store screen',
    },
  };
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) =>
      const ['ar', 'fr', 'en'].contains(locale.languageCode);

  @override
  Future<AppLocalizations> load(Locale locale) async {
    return AppLocalizations(locale);
  }

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}
