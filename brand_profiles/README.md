# brand_profiles — müştəri brend sistemi

Hər müştəri üçün ayrıca qovluq:

```
brand_profiles/<client_id>/
├── brand.yaml          # brend kimliyi (sahələr: _template/brand.yaml)
├── corrections.yaml    # müştərinin adları, brendləri, terminləri (ASR düzəlişləri)
└── assets/             # loqo və s. (yalnız təsdiqlənmiş fayllar)
```

Qaydalar:

- **Uydurma yoxdur.** Rəng, font, loqo və CTA yalnız müştərinin təsdiqlədiyi
  məlumatdır. Təsdiq olunmayıbsa `approved: false` saxlayın — render neytral
  üslubla gedir və xəbərdarlıq verir (`lib/reels_profiles.resolve_style`).
- **Montaj profili brend rəngi təyin etmir.** Temp, kəsim və subtitr düzülüşü
  `config/reels/editing_profiles/` içindədir; rəng/font/loqo yalnız buradan gəlir.
- **Məxfilik.** Real müştəri qovluqları `.gitignore` ilə repodan kənarda
  saxlanılır; repoda yalnız `_template/` və `neutral_test/` var. Müştəri
  profillərini versiya nəzarətinə salmaq qərarı ayrıca verilməlidir
  (məsələn, özəl repoda).
- `client_id` yalnız `a-z 0-9 _ -` simvollarıdır və qovluq adı ilə eyni olmalıdır.

Yeni müştəri:

```bash
cp -r brand_profiles/_template brand_profiles/<client_id>
# brand.yaml-də client_id-ni dəyişin, təsdiqlənmiş məlumatları doldurun
.venv/bin/python -c "from lib.reels_profiles import load_brand_profile as l; print(l('<client_id>')['brand_name'])"
```
