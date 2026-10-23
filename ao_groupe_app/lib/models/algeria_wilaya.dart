class AlgerianWilaya {
  const AlgerianWilaya({
    required this.code,
    required this.arabicName,
    required this.frenchName,
  });

  final String code;
  final String arabicName;
  final String frenchName;

  String label(String languageCode) =>
      languageCode == 'ar' ? arabicName : frenchName;
}

const algerianWilayas = [
  AlgerianWilaya(code: '01', arabicName: 'أدرار', frenchName: 'Adrar'),
  AlgerianWilaya(code: '02', arabicName: 'الشلف', frenchName: 'Chlef'),
  AlgerianWilaya(code: '03', arabicName: 'الأغواط', frenchName: 'Laghouat'),
  AlgerianWilaya(
      code: '04', arabicName: 'أم البواقي', frenchName: 'Oum El Bouaghi'),
  AlgerianWilaya(code: '05', arabicName: 'باتنة', frenchName: 'Batna'),
  AlgerianWilaya(code: '06', arabicName: 'بجاية', frenchName: 'Béjaïa'),
  AlgerianWilaya(code: '07', arabicName: 'بسكرة', frenchName: 'Biskra'),
  AlgerianWilaya(code: '08', arabicName: 'بشار', frenchName: 'Béchar'),
  AlgerianWilaya(code: '09', arabicName: 'البليدة', frenchName: 'Blida'),
  AlgerianWilaya(code: '10', arabicName: 'البويرة', frenchName: 'Bouira'),
  AlgerianWilaya(code: '11', arabicName: 'تمنراست', frenchName: 'Tamanrasset'),
  AlgerianWilaya(code: '12', arabicName: 'تبسة', frenchName: 'Tébessa'),
  AlgerianWilaya(code: '13', arabicName: 'تلمسان', frenchName: 'Tlemcen'),
  AlgerianWilaya(code: '14', arabicName: 'تيارت', frenchName: 'Tiaret'),
  AlgerianWilaya(code: '15', arabicName: 'تيزي وزو', frenchName: 'Tizi Ouzou'),
  AlgerianWilaya(
      code: '16', arabicName: 'الجزائر العاصمة', frenchName: 'Alger'),
  AlgerianWilaya(code: '17', arabicName: 'الجلفة', frenchName: 'Djelfa'),
  AlgerianWilaya(code: '18', arabicName: 'جيجل', frenchName: 'Jijel'),
  AlgerianWilaya(code: '19', arabicName: 'سطيف', frenchName: 'Sétif'),
  AlgerianWilaya(code: '20', arabicName: 'سعيدة', frenchName: 'Saïda'),
  AlgerianWilaya(code: '21', arabicName: 'سكيكدة', frenchName: 'Skikda'),
  AlgerianWilaya(
      code: '22', arabicName: 'سيدي بلعباس', frenchName: 'Sidi Bel Abbès'),
  AlgerianWilaya(code: '23', arabicName: 'عنابة', frenchName: 'Annaba'),
  AlgerianWilaya(code: '24', arabicName: 'قالمة', frenchName: 'Guelma'),
  AlgerianWilaya(code: '25', arabicName: 'قسنطينة', frenchName: 'Constantine'),
  AlgerianWilaya(code: '26', arabicName: 'المدية', frenchName: 'Médéa'),
  AlgerianWilaya(code: '27', arabicName: 'مستغانم', frenchName: 'Mostaganem'),
  AlgerianWilaya(code: '28', arabicName: 'المسيلة', frenchName: 'M’Sila'),
  AlgerianWilaya(code: '29', arabicName: 'معسكر', frenchName: 'Mascara'),
  AlgerianWilaya(code: '30', arabicName: 'ورقلة', frenchName: 'Ouargla'),
  AlgerianWilaya(code: '31', arabicName: 'وهران', frenchName: 'Oran'),
  AlgerianWilaya(code: '32', arabicName: 'البيض', frenchName: 'El Bayadh'),
  AlgerianWilaya(code: '33', arabicName: 'إليزي', frenchName: 'Illizi'),
  AlgerianWilaya(
      code: '34', arabicName: 'برج بوعريريج', frenchName: 'Bordj Bou Arréridj'),
  AlgerianWilaya(code: '35', arabicName: 'بومرداس', frenchName: 'Boumerdès'),
  AlgerianWilaya(code: '36', arabicName: 'الطارف', frenchName: 'El Tarf'),
  AlgerianWilaya(code: '37', arabicName: 'تندوف', frenchName: 'Tindouf'),
  AlgerianWilaya(code: '38', arabicName: 'تيسمسيلت', frenchName: 'Tissemsilt'),
  AlgerianWilaya(code: '39', arabicName: 'الوادي', frenchName: 'El Oued'),
  AlgerianWilaya(code: '40', arabicName: 'خنشلة', frenchName: 'Khenchela'),
  AlgerianWilaya(code: '41', arabicName: 'سوق أهراس', frenchName: 'Souk Ahras'),
  AlgerianWilaya(code: '42', arabicName: 'تيبازة', frenchName: 'Tipaza'),
  AlgerianWilaya(code: '43', arabicName: 'ميلة', frenchName: 'Mila'),
  AlgerianWilaya(code: '44', arabicName: 'عين الدفلى', frenchName: 'Aïn Defla'),
  AlgerianWilaya(code: '45', arabicName: 'النعامة', frenchName: 'Naâma'),
  AlgerianWilaya(
      code: '46', arabicName: 'عين تموشنت', frenchName: 'Aïn Témouchent'),
  AlgerianWilaya(code: '47', arabicName: 'غرداية', frenchName: 'Ghardaïa'),
  AlgerianWilaya(code: '48', arabicName: 'غليزان', frenchName: 'Relizane'),
  AlgerianWilaya(code: '49', arabicName: 'تيميمون', frenchName: 'Timimoun'),
  AlgerianWilaya(
      code: '50',
      arabicName: 'برج باجي مختار',
      frenchName: 'Bordj Badji Mokhtar'),
  AlgerianWilaya(
      code: '51', arabicName: 'أولاد جلال', frenchName: 'Ouled Djellal'),
  AlgerianWilaya(code: '52', arabicName: 'بني عباس', frenchName: 'Béni Abbès'),
  AlgerianWilaya(code: '53', arabicName: 'عين صالح', frenchName: 'In Salah'),
  AlgerianWilaya(code: '54', arabicName: 'عين قزام', frenchName: 'In Guezzam'),
  AlgerianWilaya(code: '55', arabicName: 'تقرت', frenchName: 'Touggourt'),
  AlgerianWilaya(code: '56', arabicName: 'جانت', frenchName: 'Djanet'),
  AlgerianWilaya(code: '57', arabicName: 'المغير', frenchName: 'El M’Ghair'),
  AlgerianWilaya(code: '58', arabicName: 'المنيعة', frenchName: 'El Meniaa'),
];

AlgerianWilaya? algerianWilayaByCode(String code) {
  for (final wilaya in algerianWilayas) {
    if (wilaya.code == code) return wilaya;
  }
  return null;
}
