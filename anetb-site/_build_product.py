# -*- coding: utf-8 -*-
import io
HERO = open(r'C:\Users\maxinjian\Desktop\video-translator\anetb-site\_hero.b64','r',encoding='utf-8').read().strip()

# ---- shared fonts per language ----
FONT_JP = ('"Yu Gothic Medium","游ゴシック Medium","YuGothic","游ゴシック体","Hiragino Kaku Gothic ProN","ヒラギノ角ゴ ProN W3","Hiragino Sans","メイリオ",Meiryo,sans-serif',
           '"Yu Mincho","游明朝","YuMincho","游明朝体","Hiragino Mincho ProN","ヒラギノ明朝 ProN","HG明朝E","MS PMincho",serif')
FONT_LAT= ('-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif',
           'Georgia,"Times New Roman",serif')
FONT_ZH = ('-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei","微软雅黑",sans-serif',
           '"Songti SC","Noto Serif SC","Source Han Serif SC","STSong","SimSun","宋体",serif')

TEMPS = ['90°','130°','160°','180°','180°','140°']

# ---- per-language content ----
D = {}

D['jp'] = dict(
  lang='ja', file='product-anet1600.html', canon='https://anetb.com/product-anet1600.html',
  home='/', font=FONT_JP,
  title='ANET1600-R30 高速・高精度 フィルム塗工複合ライン｜アネット株式会社',
  desc='ANET1600-R30 は最大1,600mm幅のフィルムを安定して高精度に塗工する、マイクログラビア＋スロットダイの複合ライン。6ゾーン30m乾燥炉、閉ループ張力制御、クリーン構造で先端産業の量産を支えます。',
  back='← 会社トップへ', nav_home='会社トップ', nav_biz='事業内容',
  eyebrow='Precision Coating System', pname1='高速・高精度', pname2='フィルム塗工複合ライン',
  psub='ANET1600-R30 ・ マイクログラビア ＋ スロットダイ',
  plead='最大1,600mm幅のフィルムを安定して高精度に塗工。巻出し・表面処理・塗工・乾燥・ラミネート・検査スペース・アキュムレータ・巻取りまでを一体化した精密塗工複合ラインです。',
  cta_hero='最終提案・承認図を問い合わせる', cta_hero2='事業内容を見る',
  specs=[('1,600 mm','最大基材幅'),('100 m/min','最高機械速度'),('30 m','6ゾーン乾燥炉'),('6–250 μm','対応基材厚み範囲')],
  s_over_eye='Overview', s_over_h='一体化された精密塗工複合ライン',
  s_over_p='巻出しから収卷まで、塗工品質とノンストップ生産を両立する連続プロセス。重要区間は二重閉ループ張力制御を採用します。',
  s_proc_eye='Process', s_proc_h='7ステップの連続プロセス',
  steps=['第1巻出し','コロナ / 除塵','マイクログラビア / スロットダイ','6ゾーン・30m 乾燥炉','蛇行修正 / ラミネート','検査予備 / アキュムレータ','牽引 / 巻取り'],
  proc_note='最終的なウェブパスと装置寸法は設計承認図によります。',
  s_coat_eye='Coating', s_coat_h='2つの塗工方式とゾーン乾燥',
  s_coat_p='幅広い液特性に対応する2方式。マイクログラビアとスロットダイを1ラインで使い分けます。',
  mg_t='マイクログラビア', mg=['固形分 約 1–3%','ウェット塗布量 約 8 g/m²','粘度 300 cps・60 kg/h'],
  sd_t='スロットダイ', sd=['固形分 約 25–50%','ウェット塗布量 約 45–90 g/m²','粘度 10,000 cps・120 kg/h'],
  dry_h='各乾燥炉の最高温度（No.1–No.6）', dry_note='熱媒油加熱 ・ 1–2区 ロール支持 ・ 3–6区 フローティング',
  s_ctrl_eye='Control & Safety', s_ctrl_h='閉ループ制御・クリーン構造・安全連動',
  ctrl=[('張力精度','±0.15 kgf / 全幅'),('温度制御精度','±2℃'),('蛇行修正ストローク','±75 mm'),('巻取り端面','±1 mm（設計目標）'),('クリーンろ過','F9 ・ 0.5 μm で 99.9%')],
  safe_h='主要安全装備', safe=['溶剤濃度警報器 2 台','静電除去装置 5 台','風圧・空圧低下インターロック','安全カバー、非常停止ロープ、手すり'],
  s_del_eye='Documentation', s_del_h='仕様承認から引渡しまで、資料を明確化',
  deliv=['ウェブパス図・全体レイアウト','基礎図・消耗部品図','電気回路図・取扱説明書','予備品・保守・潤滑関連資料'],
  del_note='ユーティリティ、一次配管・配線、現地クリーン仕上げは契約上の分担表で確定します。',
  s_ct_eye='Contact', s_ct_h='最終提案書・承認図をお問い合わせください',
  s_ct_p='精密塗工ラインのご相談・お見積りは、お気軽にご連絡ください。',
  ct_btn='電話でお問い合わせ', ct_btn2='会社トップへ戻る',
  disc='ご提供の技術パラメータを基に作成。メイン画像は製品イメージです。電力、外形寸法、ウェブ方向および未確定項目は最終設計・契約を優先します。',
  foot='© {Y} アネット株式会社（ANET CO., LTD.） All Rights Reserved.',
)

D['en'] = dict(
  lang='en', file='product-anet1600-en.html', canon='https://anetb.com/product-anet1600-en.html',
  home='/en.html', font=FONT_LAT,
  title='ANET1600-R30 High-Speed Precision Film Coating Line | ANET CO., LTD.',
  desc='ANET1600-R30 is a micro-gravure + slot-die coating line delivering stable precision coating for web widths up to 1,600 mm. A 6-zone 30 m drying oven, closed-loop tension control and clean construction support volume production for advanced industries.',
  back='← Company home', nav_home='Home', nav_biz='Business',
  eyebrow='Precision Coating System', pname1='High-Speed Precision', pname2='Film Coating Line',
  psub='ANET1600-R30 · Micro-gravure + slot-die',
  plead='Stable, precise coating for web widths up to 1,600 mm. One integrated line from unwinding and surface treatment through coating, drying, laminating, inspection allowance, accumulation and rewinding.',
  cta_hero='Request final proposal & drawings', cta_hero2='View business lines',
  specs=[('1,600 mm','Maximum web width'),('100 m/min','Maximum mechanical speed'),('30 m','Six-zone drying oven'),('6–250 μm','Supported substrate range')],
  s_over_eye='Overview', s_over_h='An integrated precision coating line',
  s_over_p='A continuous process from unwind to rewind that balances coating quality with non-stop production. Dual closed-loop tension control supports the critical sections.',
  s_proc_eye='Process', s_proc_h='A seven-step continuous process',
  steps=['Primary unwind','Corona / cleaning','Micro-gravure / slot-die','6-zone · 30 m oven','Web guide / lamination','Inspection / accumulator','Traction / rewind'],
  proc_note='Final web path and dimensions are subject to design approval.',
  s_coat_eye='Coating', s_coat_h='Two coating methods and zoned drying',
  s_coat_p='Two methods covering a broad formulation window — micro-gravure and slot-die on one line.',
  mg_t='Micro-gravure', mg=['Solids approx. 1–3%','Wet coat approx. 8 g/m²','Viscosity 300 cps · 60 kg/h'],
  sd_t='Slot-die', sd=['Solids approx. 25–50%','Wet coat approx. 45–90 g/m²','Viscosity 10,000 cps · 120 kg/h'],
  dry_h='Maximum oven temperature (No.1–No.6)', dry_note='Thermal-oil heating · roll support in zones 1–2 · flotation in zones 3–6',
  s_ctrl_eye='Control & Safety', s_ctrl_h='Closed-loop control, clean build and interlocks',
  ctrl=[('Tension accuracy','±0.15 kgf across full width'),('Temperature accuracy','±2°C'),('Web-guide travel','±75 mm'),('Rewind edge','±1 mm design target'),('Clean filtration','F9 · 99.9% at 0.5 μm')],
  safe_h='Core safety provisions', safe=['2 solvent concentration alarms','5 static eliminators','Airflow / pressure-loss interlocks','Guards, pull-cord E-stops and handrails'],
  s_del_eye='Documentation', s_del_h='Clear interfaces and complete documentation',
  deliv=['Web path and general arrangement','Foundation and wear-part drawings','Electrical schematics and operating manual','Spares, maintenance and lubrication documents'],
  del_note='Utilities, primary piping/wiring and on-site cleanroom finishing are confirmed in the contractual interface matrix.',
  s_ct_eye='Contact', s_ct_h='Request the final proposal and approved drawings',
  s_ct_p='For enquiries or a quotation on a precision coating line, feel free to contact us.',
  ct_btn='Call us', ct_btn2='Back to company home',
  disc='Prepared from the supplied technical parameters. Hero image is a concept visualization. Power, dimensions, web direction and open parameters remain subject to final design and contract.',
  foot='© {Y} ANET CO., LTD. All Rights Reserved.',
)

D['es'] = dict(
  lang='es', file='product-anet1600-es.html', canon='https://anetb.com/product-anet1600-es.html',
  home='/es.html', font=FONT_LAT,
  title='ANET1600-R30 Línea de recubrimiento de alta precisión | ANET CO., LTD.',
  desc='ANET1600-R30 es una línea de recubrimiento por micrograbado + ranura que ofrece un recubrimiento estable y preciso para bandas de hasta 1.600 mm. Horno de secado de 6 zonas y 30 m, control de tensión en lazo cerrado y construcción limpia.',
  back='← Inicio de la empresa', nav_home='Inicio', nav_biz='Negocios',
  eyebrow='Precision Coating System', pname1='Línea de recubrimiento', pname2='de alta precisión',
  psub='ANET1600-R30 · Micrograbado + ranura',
  plead='Recubrimiento estable y preciso para bandas de hasta 1.600 mm. Una línea integrada desde el desbobinado y el tratamiento superficial hasta el recubrimiento, secado, laminado, acumulación y rebobinado.',
  cta_hero='Solicitar propuesta y planos', cta_hero2='Ver líneas de negocio',
  specs=[('1.600 mm','Ancho máximo de banda'),('100 m/min','Velocidad mecánica máxima'),('30 m','Horno de seis zonas'),('6–250 μm','Rango de espesor del sustrato')],
  s_over_eye='Overview', s_over_h='Una línea de recubrimiento integrada',
  s_over_p='Un proceso continuo del desbobinado al rebobinado que combina calidad de recubrimiento con producción sin paradas. El control de tensión de doble lazo cerrado actúa en las secciones críticas.',
  s_proc_eye='Proceso', s_proc_h='Un proceso continuo de siete pasos',
  steps=['Desbobinado primario','Corona / limpieza','Micrograbado / ranura','Horno 6 zonas · 30 m','Guiado / laminado','Inspección / acumulador','Tracción / rebobinado'],
  proc_note='El recorrido y las dimensiones finales quedan sujetos a aprobación de diseño.',
  s_coat_eye='Recubrimiento', s_coat_h='Dos métodos de recubrimiento y secado por zonas',
  s_coat_p='Dos métodos que amplían la ventana de proceso: micrograbado y ranura en una sola línea.',
  mg_t='Micrograbado', mg=['Sólidos aprox. 1–3%','Capa húmeda aprox. 8 g/m²','Viscosidad 300 cps · 60 kg/h'],
  sd_t='Ranura (slot-die)', sd=['Sólidos aprox. 25–50%','Capa húmeda aprox. 45–90 g/m²','Viscosidad 10.000 cps · 120 kg/h'],
  dry_h='Temperatura máxima del horno (N.º 1–6)', dry_note='Calentamiento por aceite térmico · rodillos en zonas 1–2 · flotación en zonas 3–6',
  s_ctrl_eye='Control y seguridad', s_ctrl_h='Control en lazo cerrado, construcción limpia y enclavamientos',
  ctrl=[('Precisión de tensión','±0,15 kgf en todo el ancho'),('Precisión de temperatura','±2 °C'),('Recorrido del guiado','±75 mm'),('Borde de rebobinado','Objetivo de diseño ±1 mm'),('Filtración limpia','F9 · 99,9% a 0,5 μm')],
  safe_h='Protecciones principales', safe=['2 alarmas de concentración de disolvente','5 eliminadores de electricidad estática','Enclavamientos por pérdida de caudal o presión','Resguardos, parada por cable y barandillas'],
  s_del_eye='Documentación', s_del_h='Interfaces claras y documentación completa',
  deliv=['Diagrama de banda y disposición general','Planos de cimentación y piezas de desgaste','Esquemas eléctricos y manual de operación','Documentos de repuestos, mantenimiento y lubricación'],
  del_note='Los servicios, las tuberías y el cableado primarios, y el acabado de sala limpia se confirman en la matriz contractual de interfaces.',
  s_ct_eye='Contacto', s_ct_h='Solicite la propuesta final y los planos aprobados',
  s_ct_p='Para consultas o presupuesto de una línea de recubrimiento de precisión, contáctenos.',
  ct_btn='Llámenos', ct_btn2='Volver al inicio',
  disc='Preparado a partir de los parámetros técnicos suministrados. La imagen principal es una visualización conceptual. Potencia, dimensiones, recorrido y parámetros abiertos quedan sujetos al diseño final y al contrato.',
  foot='© {Y} ANET CO., LTD. Todos los derechos reservados.',
)

D['zh'] = dict(
  lang='zh-CN', file='product-anet1600-zh.html', canon='https://anetb.com/product-anet1600-zh.html',
  home='/zh.html', font=FONT_ZH,
  title='ANET1600-R30 高速精密保护膜涂布复合线 | ANET CO., LTD.',
  desc='ANET1600-R30 是采用微凹＋狭缝双工艺的涂布复合线，为最大1600mm宽幅薄膜提供稳定、连续的精密涂布。六段30m干燥风箱、闭环张力控制与洁净结构，支撑先进产业的量产。',
  back='← 返回公司首页', nav_home='公司首页', nav_biz='业务内容',
  eyebrow='Precision Coating System', pname1='高速精密保护膜', pname2='涂布复合线',
  psub='ANET1600-R30 · 微凹 ＋ 狭缝双工艺',
  plead='为最大1600mm宽幅薄膜提供稳定、连续的精密涂布。覆盖放卷、表面处理、涂布、干燥、复合、检测预留、储料与收卷的完整生产链。',
  cta_hero='获取最终方案与技术确认图', cta_hero2='查看业务内容',
  specs=[('1600 mm','最大基材宽度'),('100 m/min','最高机械速度'),('30 m','六段式干燥风箱'),('6–250 μm','覆盖基材厚度')],
  s_over_eye='Overview', s_over_h='一体化的精密涂布复合线',
  s_over_p='从放卷到收卷的连续工艺，兼顾涂布质量与不停机生产。关键区段采用双闭环张力控制。',
  s_proc_eye='工艺流程', s_proc_h='七步连续工艺',
  steps=['第一放卷','电晕 / 除尘','微凹 / 狭缝','六段 30m 烘箱','纠偏 / 复合','检测预留 / 储料','牵引 / 收卷'],
  proc_note='最终走膜方向与设备尺寸以设计确认图为准。',
  s_coat_eye='涂布工艺', s_coat_h='双涂布工艺与分区干燥',
  s_coat_p='适配不同浆料窗口的两种工艺——微凹与狭缝，可在同一条线上切换使用。',
  mg_t='微凹涂布', mg=['固含量约 1–3%','湿涂量约 8 g/m²','黏度约 300 cps · 60 kg/h'],
  sd_t='狭缝涂布', sd=['固含量约 25–50%','湿涂量约 45–90 g/m²','黏度约 10,000 cps · 120 kg/h'],
  dry_h='烘箱温度上限（No.1–No.6）', dry_note='导热油加热 · 1–2区过辊 · 3–6区悬浮',
  s_ctrl_eye='控制与安全', s_ctrl_h='闭环控制、洁净结构与安全联锁',
  ctrl=[('张力精度','±0.15 kgf / 全幅宽'),('温控精度','±2℃'),('纠偏行程','±75 mm'),('收卷端面','偏差 ±1 mm（设计目标）'),('洁净过滤','F9 · 0.5 μm 过滤效率 99.9%')],
  safe_h='关键安全配置', safe=['2 套溶剂浓度报警器','5 套静电消除装置','风压 / 气压失压联锁','防护罩、急停拉绳与护栏'],
  s_del_eye='交付文档', s_del_h='从方案确认到现场交付，资料完整',
  deliv=['设备走膜图与总布局图','地基图、易损件图纸','电气原理图与设备说明书','备品备件、保养与润滑资料'],
  del_note='公用工程、一次配管配线及现场洁净收口由双方按合同界面确认。',
  s_ct_eye='联系我们', s_ct_h='获取最终方案与技术确认图',
  s_ct_p='精密涂布线的咨询与报价，欢迎随时与我们联系。',
  ct_btn='电话联系', ct_btn2='返回公司首页',
  disc='依据《精密涂布技术参数》整理。主视觉为产品概念示意；功率、外形尺寸、走膜方向及待定参数以最终设计与合同为准。',
  foot='© {Y} ANET CO., LTD.（アネット株式会社） 版权所有。',
)

CSS = '''
  :root{--ink:#14181d;--navy:#0d2a4b;--accent:#b8121b;--bg:#ffffff;--bg-soft:#f5f6f8;--line:#e3e6ea;--muted:#5b6572;--sub:#98a1ac;--gothic:__G__;--mincho:__M__;--wrap:1180px;}
  *{margin:0;padding:0;box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{font-family:var(--gothic);color:var(--ink);background:var(--bg);line-height:1.85;font-size:15px;-webkit-font-smoothing:antialiased;letter-spacing:.01em}
  a{color:inherit;text-decoration:none}
  img{max-width:100%;display:block}
  ::selection{background:var(--navy);color:#fff}
  .wrap{width:100%;max-width:var(--wrap);margin:0 auto;padding:0 28px}
  .eyebrow{font-size:11px;letter-spacing:.24em;color:var(--accent);font-weight:700;display:inline-flex;align-items:center;gap:12px;text-transform:uppercase}
  .eyebrow::before{content:"";width:26px;height:1px;background:var(--accent);display:inline-block}
  .sec-title{font-family:var(--mincho);font-size:clamp(24px,3.2vw,36px);line-height:1.35;font-weight:600;color:var(--navy);margin-top:14px;letter-spacing:.02em}
  .sec-lead{color:var(--muted);margin-top:18px;max-width:680px;font-size:14.5px}
  header{position:fixed;top:0;left:0;width:100%;z-index:100;background:rgba(255,255,255,.92);backdrop-filter:saturate(180%) blur(10px);-webkit-backdrop-filter:saturate(180%) blur(10px);border-bottom:1px solid var(--line)}
  .nav{display:flex;align-items:center;justify-content:space-between;height:66px}
  .brand{display:flex;align-items:center;gap:12px}
  .brand-logo{height:24px;width:auto;mix-blend-mode:multiply}
  .brand-sub{font-size:11px;letter-spacing:.12em;color:var(--sub);padding-left:12px;border-left:1px solid var(--line)}
  .topnav{display:flex;align-items:center;gap:24px;font-size:13px}
  .topnav a{color:var(--ink);transition:color .3s}
  .topnav a:hover{color:var(--navy)}
  .topnav .back{color:var(--navy);font-weight:700}
  @media(max-width:560px){.brand-sub,.topnav a.hidem{display:none}}
  section{padding:92px 0}
  .sec-head{margin-bottom:48px}
  .hero{padding:120px 0 76px;background:linear-gradient(180deg,#fbfcfd,#fff)}
  .hero .eyebrow{margin-bottom:0}
  .hero h1{font-family:var(--mincho);font-weight:600;color:var(--navy);font-size:clamp(30px,4.6vw,52px);line-height:1.28;letter-spacing:.02em;margin:22px 0 0}
  .hero .sub{margin-top:16px;font-size:14px;letter-spacing:.06em;color:var(--accent);font-weight:700}
  .hero p.lead{margin-top:22px;font-size:15px;color:var(--muted);max-width:680px}
  .hero-actions{margin-top:30px;display:flex;gap:14px;flex-wrap:wrap}
  .btn{display:inline-flex;align-items:center;gap:9px;font-size:13px;letter-spacing:.04em;padding:14px 26px;transition:transform .3s,background .3s,color .3s,border-color .3s;cursor:pointer}
  .btn-primary{background:var(--navy);color:#fff}
  .btn-primary:hover{background:var(--accent);transform:translateY(-2px)}
  .btn-ghost{border:1px solid var(--line);color:var(--navy)}
  .btn-ghost:hover{border-color:var(--navy);transform:translateY(-2px)}
  .hero-img{margin-top:44px;border:1px solid var(--line);border-radius:12px;overflow:hidden;box-shadow:0 40px 80px -50px rgba(13,42,75,.6)}
  .hero-img img{width:100%;display:block}
  .facts{border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:#fff}
  .facts .wrap{display:grid;grid-template-columns:repeat(4,1fr)}
  .fact{padding:32px 18px;text-align:center;border-left:1px solid var(--line)}
  .fact:first-child{border-left:0}
  .fact .v{font-size:26px;font-weight:800;color:var(--navy);letter-spacing:.01em}
  .fact .k{font-family:var(--mincho);font-size:12.5px;color:var(--muted);margin-top:6px}
  #proc{background:var(--bg)}
  .steps{display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-top:8px}
  .step{background:#fff;padding:26px 16px;text-align:center}
  .step .n{font-family:var(--mincho);font-size:22px;color:var(--accent);font-weight:600}
  .step .t{margin-top:10px;font-size:12.5px;color:var(--ink);line-height:1.5}
  .note{margin-top:22px;font-size:12.5px;color:var(--sub)}
  #coat{background:var(--bg-soft)}
  .coat-grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line)}
  .coat{background:#fff;padding:38px 34px}
  .coat h3{font-size:19px;font-weight:800;color:var(--navy);margin-bottom:18px}
  .coat h3 .en{display:block;font-size:11px;letter-spacing:.14em;color:var(--sub);font-weight:600;margin-bottom:3px;text-transform:uppercase}
  .coat ul{list-style:none}
  .coat li{padding:9px 0;border-bottom:1px solid var(--line);color:var(--muted);font-size:14px}
  .coat li:last-child{border-bottom:0}
  .dry{margin-top:40px}
  .dry h4{font-size:14px;color:var(--navy);font-weight:800;margin-bottom:16px}
  .dry-row{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}
  .dry-cell{background:#fff;border:1px solid var(--line);border-radius:8px;padding:18px 8px;text-align:center}
  .dry-cell .z{font-size:11px;color:var(--sub);letter-spacing:.08em}
  .dry-cell .d{font-size:22px;font-weight:800;color:var(--navy);margin-top:4px}
  #ctrl{background:var(--bg)}
  .ctrl-flex{display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:start}
  .dl{border-top:1px solid var(--line)}
  .dl .row{display:grid;grid-template-columns:1fr auto;gap:16px;border-bottom:1px solid var(--line);padding:16px 2px}
  .dl dt{font-weight:800;color:var(--navy);font-size:13.5px}
  .dl dd{color:var(--muted);font-size:14px;text-align:right}
  .safe h4{font-size:14px;color:var(--navy);font-weight:800;margin-bottom:16px}
  .safe ul{list-style:none}
  .safe li{position:relative;padding:11px 0 11px 26px;border-bottom:1px solid var(--line);color:var(--muted);font-size:13.5px}
  .safe li:last-child{border-bottom:0}
  .safe li::before{content:"";position:absolute;left:0;top:17px;width:10px;height:10px;border:2px solid var(--accent);border-radius:2px}
  #deliv{background:var(--bg-soft)}
  .deliv-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin-top:8px}
  .dcard{background:#fff;border:1px solid var(--line);padding:30px 24px}
  .dcard .n{font-family:var(--mincho);font-size:14px;color:var(--accent)}
  .dcard p{margin-top:12px;font-size:13.5px;color:var(--ink);line-height:1.6}
  #contact{background:var(--navy);color:#fff;position:relative;overflow:hidden}
  #contact::before{content:"";position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,.06) 1px,transparent 1px);background-size:24px 24px;opacity:.6}
  #contact .wrap{position:relative;text-align:center}
  #contact .eyebrow{color:#f0b6ba}
  #contact .eyebrow::before{background:#f0b6ba}
  #contact h2{font-family:var(--mincho);font-size:clamp(26px,3.6vw,40px);font-weight:600;margin:16px 0 18px;line-height:1.35}
  #contact p{color:rgba(255,255,255,.72);max-width:600px;margin:0 auto 20px;font-size:14.5px}
  .contact-info{display:flex;gap:30px;justify-content:center;flex-wrap:wrap;margin:22px 0 34px;color:rgba(255,255,255,.85);font-size:14px}
  .contact-info b{color:#fff;font-weight:800}
  .contact-btns{display:flex;gap:14px;justify-content:center;flex-wrap:wrap}
  .btn-white{background:#fff;color:var(--navy);font-weight:700}
  .btn-white:hover{background:var(--accent);color:#fff;transform:translateY(-2px)}
  .btn-outline{border:1px solid rgba(255,255,255,.4);color:#fff}
  .btn-outline:hover{border-color:#fff;transform:translateY(-2px)}
  footer{background:#0a1f37;color:rgba(255,255,255,.55);padding:40px 0;font-size:12px;text-align:center;line-height:2}
  .disc{max-width:900px;margin:0 auto 14px;color:rgba(255,255,255,.4);font-size:11.5px;line-height:1.8}
  .reveal{opacity:0;transform:translateY(24px);transition:opacity .8s cubic-bezier(.2,.7,.2,1),transform .8s cubic-bezier(.2,.7,.2,1)}
  .reveal.in{opacity:1;transform:none}
  @media(max-width:920px){.ctrl-flex{grid-template-columns:1fr;gap:40px}.coat-grid{grid-template-columns:1fr}.deliv-grid{grid-template-columns:1fr 1fr}.steps{grid-template-columns:repeat(2,1fr)}.facts .wrap{grid-template-columns:repeat(2,1fr)}.fact:nth-child(3){border-left:0}.dry-row{grid-template-columns:repeat(3,1fr)}}
  @media(max-width:560px){section{padding:64px 0}.deliv-grid{grid-template-columns:1fr}.steps{grid-template-columns:1fr}.dry-row{grid-template-columns:repeat(2,1fr)}.facts .wrap{grid-template-columns:1fr}.fact{border-left:0;border-top:1px solid var(--line)}.fact:first-child{border-top:0}}
'''

def esc(s): return s.replace('&','&amp;')

def build(d):
    G,M=d['font']
    css=CSS.replace('__G__',G).replace('__M__',M)
    steps=''.join(f'<div class="step"><div class="n">{i+1}</div><div class="t">{s}</div></div>' for i,s in enumerate(d['steps']))
    facts=''.join(f'<div class="fact"><div class="v">{v}</div><div class="k">{k}</div></div>' for v,k in d['specs'])
    mg=''.join(f'<li>{x}</li>' for x in d['mg']); sd=''.join(f'<li>{x}</li>' for x in d['sd'])
    dry=''.join(f'<div class="dry-cell"><div class="z">No.{i+1}</div><div class="d">{t}</div></div>' for i,t in enumerate(TEMPS))
    ctrl=''.join(f'<div class="row"><dt>{a}</dt><dd>{b}</dd></div>' for a,b in d['ctrl'])
    safe=''.join(f'<li>{x}</li>' for x in d['safe'])
    deliv=''.join(f'<div class="dcard reveal"><div class="n">0{i+1}</div><p>{x}</p></div>' for i,x in enumerate(d['deliv']))
    html=f'''<!DOCTYPE html>
<html lang="{d['lang']}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{d['title']}</title>
<meta name="description" content="{d['desc']}">
<meta name="robots" content="index, follow">
<meta name="format-detection" content="telephone=no">
<link rel="canonical" href="{d['canon']}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E%3Crect width='40' height='40' fill='%230d2a4b'/%3E%3Cpath d='M20 8 L31 32 H26 L20 17 L14 32 H9 Z' fill='white'/%3E%3Crect x='17.5' y='24' width='5' height='2.4' fill='%23b8121b'/%3E%3C/svg%3E">
<meta property="og:type" content="website">
<meta property="og:title" content="{d['title']}">
<meta property="og:description" content="{d['desc']}">
<meta property="og:url" content="{d['canon']}">
<style>{css}</style>
</head>
<body>
<header>
  <div class="wrap nav">
    <a href="{d['home']}" class="brand">
      <img class="brand-logo" src="https://japanerp.com/images/anet-logo.png" alt="ANET CO., LTD." width="140" height="30">
      <span class="brand-sub">ANET CO., LTD.</span>
    </a>
    <nav class="topnav">
      <a href="{d['home']}#business" class="hidem">{d['nav_biz']}</a>
      <a href="{d['home']}" class="back">{d['back']}</a>
    </nav>
  </div>
</header>

<section class="hero">
  <div class="wrap">
    <span class="eyebrow">{d['eyebrow']}</span>
    <h1>{d['pname1']}<br>{d['pname2']}</h1>
    <div class="sub">{d['psub']}</div>
    <p class="lead">{d['plead']}</p>
    <div class="hero-actions">
      <a href="#contact" class="btn btn-primary">{d['cta_hero']} &rarr;</a>
      <a href="{d['home']}#business" class="btn btn-ghost">{d['cta_hero2']} &rarr;</a>
    </div>
    <div class="hero-img"><img src="{HERO}" alt="ANET1600-R30" width="1040" height="585" loading="eager"></div>
  </div>
</section>

<div class="facts"><div class="wrap">{facts}</div></div>

<section id="proc">
  <div class="wrap">
    <div class="sec-head reveal"><span class="eyebrow">{d['s_proc_eye']}</span><h2 class="sec-title">{d['s_proc_h']}</h2><p class="sec-lead">{d['s_over_p']}</p></div>
    <div class="steps reveal">{steps}</div>
    <p class="note">{d['proc_note']}</p>
  </div>
</section>

<section id="coat">
  <div class="wrap">
    <div class="sec-head reveal"><span class="eyebrow">{d['s_coat_eye']}</span><h2 class="sec-title">{d['s_coat_h']}</h2><p class="sec-lead">{d['s_coat_p']}</p></div>
    <div class="coat-grid reveal">
      <div class="coat"><h3><span class="en">Micro-gravure</span>{d['mg_t']}</h3><ul>{mg}</ul></div>
      <div class="coat"><h3><span class="en">Slot-die</span>{d['sd_t']}</h3><ul>{sd}</ul></div>
    </div>
    <div class="dry reveal"><h4>{d['dry_h']}</h4><div class="dry-row">{dry}</div><p class="note">{d['dry_note']}</p></div>
  </div>
</section>

<section id="ctrl">
  <div class="wrap ctrl-flex">
    <div class="reveal">
      <div class="sec-head" style="margin-bottom:24px"><span class="eyebrow">{d['s_ctrl_eye']}</span><h2 class="sec-title">{d['s_ctrl_h']}</h2></div>
      <dl class="dl">{ctrl}</dl>
    </div>
    <div class="safe reveal"><h4>{d['safe_h']}</h4><ul>{safe}</ul></div>
  </div>
</section>

<section id="deliv">
  <div class="wrap">
    <div class="sec-head reveal"><span class="eyebrow">{d['s_del_eye']}</span><h2 class="sec-title">{d['s_del_h']}</h2></div>
    <div class="deliv-grid">{deliv}</div>
    <p class="note">{d['del_note']}</p>
  </div>
</section>

<section id="contact">
  <div class="wrap reveal">
    <span class="eyebrow">{d['s_ct_eye']}</span>
    <h2>{d['s_ct_h']}</h2>
    <p>{d['s_ct_p']}</p>
    <div class="contact-info"><div>Tel&nbsp;&nbsp;<b>082-430-8758</b></div><div>Fax&nbsp;&nbsp;<b>082-430-8757</b></div><div>ANET CO., LTD. &middot; anetb.com</div></div>
    <div class="contact-btns">
      <a href="tel:0824308758" class="btn btn-white">{d['ct_btn']} &rarr;</a>
      <a href="{d['home']}" class="btn btn-outline">{d['ct_btn2']} &rarr;</a>
    </div>
  </div>
</section>

<footer>
  <div class="wrap">
    <p class="disc">{d['disc']}</p>
    <p>{d['foot'].replace('{Y}','<span id="y"></span>')}<br>Tel 082-430-8758 &nbsp;&middot;&nbsp; Fax 082-430-8757 &nbsp;&middot;&nbsp; https://anetb.com/</p>
  </div>
</footer>
<script>
var io=new IntersectionObserver(function(e){{e.forEach(function(x){{if(x.isIntersecting){{x.target.classList.add('in');io.unobserve(x.target);}}}})}},{{threshold:.12,rootMargin:'0px 0px -8% 0px'}});
document.querySelectorAll('.reveal').forEach(function(el){{io.observe(el)}});
document.getElementById('y').textContent=new Date().getFullYear();
</script>
</body>
</html>'''
    path=r'C:\Users\maxinjian\Desktop\video-translator\anetb-site\%s' % d['file']
    open(path,'w',encoding='utf-8').write(html)
    print('built', d['file'], len(html)//1024,'KB')

for k in ['jp','en','es','zh']:
    build(D[k])
print('DONE')
