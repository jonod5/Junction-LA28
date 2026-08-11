"""
Populate venue_translation with first-pass es/fr/zh-Hans translations of the
collected venue prose (v1.5 Phase 3).

Design:
- TRANSLATIONS lists one entry per (venue, entity, field) — same shape as the
  English source it was translated from: the *stripped* text the API
  actually serves (see app/routers/venues.py's _strip_provenance), not the
  raw DB value with inline research citations still in it.
- `idx` resolves to a real database row by position: for a venue's
  parking/transit rows, that's their order by id ascending, which for a
  freshly-seeded database matches seed_venues.py's list order (the source
  these translations were transcribed from). "venue" and "congestion"
  entities are 1-per-venue, so idx is always 0.
- Every row is inserted with reviewed=False — these are first-pass
  translations (written directly, no third-party translation API — see
  frontend/locales/README.md for the same policy on UI strings) and need a
  native speaker's review before this is treated as production-quality
  content. Query `VenueTranslation.reviewed == False` for the review queue.
- Identifiers are never translated here (see the module docstring in
  app/routers/venues.py) — this script only ever writes rows for the prose
  fields that module's `tr()` helper actually looks up. Two capacity_text
  values ("13,615" and similar) that are purely numeric were skipped: there
  is no prose in them to translate, so a translation row would just be a
  redundant copy of the English value.

Run after seed_venues.py, against the same database:
    python -m app.seed_venue_translations
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.venue import ParkingOption, TransitAccess, Venue, VenueTranslation

LANGUAGES = ("es", "fr", "zh-Hans")

# Each entry: (venue_name, entity_type, idx, field, es, fr, zh)
# entity_type is one of: "venue", "parking", "curb", "transit", "congestion"
TRANSLATIONS: list[tuple[str, str, int, str, str, str, str]] = [
    # ── LA Memorial Coliseum ────────────────────────────────────────────────
    ("LA Memorial Coliseum", "parking", 0, "price_notes",
     "Partidos de fútbol americano en casa de USC: $50/partido (vigente desde el 1/7/2026). Tarifa plana diaria estándar: $20/día + $0.50 de cargo único por Text2Park (o $20/día sin cargo mediante Pay-By-Plate). Tarifa por hora estándar: $4/hora + $0.50 de cargo único (hasta 4 horas; 5+ horas se cobran a la tarifa plana diaria de $20).",
     "Matchs de football américain à domicile de l'USC : 50 $/match (en vigueur à partir du 1/7/2026). Tarif forfaitaire journalier standard : 20 $/jour + 0,50 $ de frais uniques Text2Park (ou 20 $/jour sans frais via Pay-By-Plate). Tarif horaire standard : 4 $/heure + 0,50 $ de frais uniques (jusqu'à 4 heures ; au-delà de 5 heures, facturé au tarif forfaitaire journalier de 20 $).",
     "南加州大学（USC）主场橄榄球比赛：每场 $50（自 2026 年 7 月 1 日起生效）。标准每日统一费率：每天 $20 + 一次性 Text2Park 手续费 $0.50（或通过 Pay-By-Plate 支付每天 $20 且无手续费）。标准每小时费率：每小时 $4 + 一次性手续费 $0.50（最多 4 小时；超过 5 小时按每日统一费率 $20 收取）。"),
    ("LA Memorial Coliseum", "parking", 0, "surge_notes",
     "La página de accesibilidad ADA del Coliseum indica que \"las tarifas de estacionamiento para eventos pueden variar según el evento\". Sitios de terceros (ParkWhiz/ParkMobile) muestran precios basados en la demanda que varían según el evento",
     "La page ADA du Coliseum indique que « les tarifs de stationnement pour les événements peuvent varier selon l'événement ». Des sites tiers (ParkWhiz/ParkMobile) affichent des prix basés sur la demande qui varient selon l'événement",
     "体育场无障碍（ADA）页面指出\"活动停车费率可能因活动而异\"。第三方网站（ParkWhiz/ParkMobile）显示的价格基于需求浮动，因活动而异"),
    ("LA Memorial Coliseum", "parking", 0, "notes",
     "El estacionamiento más cercano a la entrada del recinto: el lote de 910 W. Martin Luther King Jr. Blvd., indicado como a 7 minutos a pie (capacidad de hasta 20 vehículos); estructura Blue; lote Gold; lote Pink. \"No hay estacionamiento disponible en el propio Exposition Park... se aplican tarifas de estacionamiento\", por lo que se indica a los visitantes reservar en justpark.com. El estacionamiento accesible ADA es por orden de llegada, sin reserva anticipada.",
     "Parking le plus proche de l'entrée du site : le parking du 910 W. Martin Luther King Jr. Blvd., à environ 7 minutes à pied (jusqu'à 20 véhicules) ; structure Blue ; parking Gold ; parking Pink. « Il n'y a pas de stationnement sur place dans Exposition Park... des frais de stationnement s'appliquent », les visiteurs sont donc invités à réserver sur justpark.com. Le stationnement accessible ADA se fait par ordre d'arrivée, sans réservation préalable.",
     "距场馆入口最近的停车场：位于 910 W. Martin Luther King Jr. Blvd. 的停车场，步行约 7 分钟（可容纳最多 20 辆车）；Blue 停车楼；Gold 停车场；Pink 停车场。\"Exposition Park 现场没有停车位……需缴纳停车费\"，建议访客前往 justpark.com 预订。ADA 无障碍停车位按先到先得原则提供，不接受提前预订。"),
    ("LA Memorial Coliseum", "curb", 0, "rideshare_zone_description",
     "Vermont Ave. entre Exposition Blvd. y Downey Way. Para eventos tipo concierto más grandes, Vermont Ave. entre Exposition Blvd. y W. 36th Place",
     "Vermont Ave. entre Exposition Blvd. et Downey Way. Pour les événements de type concert plus importants, Vermont Ave. entre Exposition Blvd. et W. 36th Place",
     "Vermont Ave.（位于 Exposition Blvd. 与 Downey Way 之间）。对于规模较大的演唱会类活动，则在 Vermont Ave.（位于 Exposition Blvd. 与 W. 36th Place 之间）"),
    ("LA Memorial Coliseum", "curb", 0, "rideshare_zone_open_window",
     "Los servicios de viajes compartidos tienen prohibido ingresar al área de Exposition Park hasta 45–60 minutos después de que finalice un evento (no se indica la hora exacta de apertura antes de los eventos)",
     "Les services de covoiturage ne sont pas autorisés à entrer dans la zone d'Exposition Park avant 45 à 60 minutes après la fin d'un événement (l'heure exacte d'ouverture avant les événements n'est pas indiquée)",
     "网约车在活动结束后 45–60 分钟内禁止进入 Exposition Park 区域（活动前的确切开放时间未说明）"),
    ("LA Memorial Coliseum", "curb", 0, "taxi_accessible_zone",
     "Estacionamiento limitado para limusinas/vehículos contratados en el lote Green, con acceso desde W. Martin Luther King Jr. Blvd y S. Hoover St. La zona de recogida/entrega ADA está en Exposition Park Drive (entrando desde S. Figueroa en W. 39th St)",
     "Stationnement limité pour limousines/véhicules de location au parking Green, accessible depuis W. Martin Luther King Jr. Blvd et S. Hoover St. La zone de dépose/prise en charge ADA se trouve sur Exposition Park Drive (accès depuis S. Figueroa à W. 39th St)",
     "Green 停车场提供有限的豪华轿车/租赁车辆停车位，可从 W. Martin Luther King Jr. Blvd 和 S. Hoover St 进入。ADA 无障碍上下客区位于 Exposition Park Drive（从 S. Figueroa 与 W. 39th St 交口进入）"),
    ("LA Memorial Coliseum", "curb", 0, "private_vehicle_dropoff",
     "Exposition Park permite el acceso de viajes compartidos/entrega desde Figueroa St., con zona de entrega/recogida a lo largo de Expo Park Dr.",
     "Exposition Park autorise l'accès covoiturage/dépose depuis Figueroa St., avec dépose/prise en charge le long d'Expo Park Dr.",
     "Exposition Park 允许从 Figueroa St. 进入进行网约车上下客，上下客区位于 Expo Park Dr. 沿线"),
    ("LA Memorial Coliseum", "curb", 0, "no_stop_zones",
     "cierres del carril de giro a la izquierda\" en Figueroa St/Expo Park Dr, MLK Jr Blvd/Hoover St, y Exposition Blvd/Bill Robertson Lane durante eventos grandes",
     "fermetures de la voie de tourne-à-gauche\" à Figueroa St/Expo Park Dr, MLK Jr Blvd/Hoover St, et Exposition Blvd/Bill Robertson Lane lors de grands événements",
     "在大型活动期间，Figueroa St/Expo Park Dr、MLK Jr Blvd/Hoover St 以及 Exposition Blvd/Bill Robertson Lane 的左转车道会关闭\""),
    ("LA Memorial Coliseum", "curb", 0, "curbside_restrictions",
     "La recogida/entrega después del evento \"puede retrasarse hasta 45–60 minutos\" debido al control de tráfico que reabre las calles",
     "La prise en charge/dépose après l'événement « peut être retardée jusqu'à 45 à 60 minutes » en raison de la réouverture des rues par le contrôle de la circulation",
     "活动结束后的上下客\"可能因交通管制重新开放街道而延误最多 45–60 分钟\""),
    ("LA Memorial Coliseum", "transit", 0, "gbfs_dock_description",
     "Patinetes Lime cerca de la estación Expo Park/USC; patinetes Lime/Bird en la intersección de Vermont y Expo; estación de bicicletas Doordash frente al Arco en la intersección de Vermont y Expo",
     "Trottinettes Lime près de la station Expo Park/USC ; trottinettes Lime/Bird à l'intersection de Vermont et Expo ; borne de vélos Doordash devant l'Arco à l'intersection de Vermont et Expo",
     "Expo Park/USC 站附近有 Lime 滑板车；Vermont 与 Expo 交叉口有 Lime/Bird 滑板车；Vermont 与 Expo 交叉口的 Arco 加油站前设有 Doordash 自行车停靠点"),
    ("LA Memorial Coliseum", "transit", 0, "transit_notes",
     "Tarifa de ida y vuelta de la Línea E: $3.50; los últimos trenes desde Expo Park salen a las 11:50pm (dirección este) / 12:10am (dirección oeste); el servicio reforzado comienza 2–3 horas antes y continúa 1–2 horas después de los eventos. Tiempos a pie: estación Expo Park/USC (6 min); estación Expo/Vermont (6 min). Paradas de autobús más cercanas: Figueroa/Exposition, Vermont/Exposition (las paradas más cercanas indicadas). Tiempo a pie desde la parada de autobús: Figueroa/Exposition (11 min); Vermont/Exposition (7 min). Carril bici: Sí — Figueroa St cuenta con mejoras de seguridad para ciclistas del proyecto \"MyFigueroa\". La Línea J de Metro también da servicio (autobús de tránsito rápido).",
     "Tarif aller-retour de la ligne E : 3,50 $ ; les derniers trains depuis Expo Park partent à 23h50 (direction est) / 00h10 (direction ouest) ; le service renforcé commence 2 à 3 heures avant et se poursuit 1 à 2 heures après les événements. Temps de marche : station Expo Park/USC (6 min) ; station Expo/Vermont (6 min). Arrêts de bus les plus proches : Figueroa/Exposition, Vermont/Exposition (arrêts les plus proches indiqués). Temps de marche depuis l'arrêt de bus : Figueroa/Exposition (11 min) ; Vermont/Exposition (7 min). Piste cyclable : Oui — Figueroa St bénéficie d'aménagements cyclables du projet « MyFigueroa ». La ligne J de Metro dessert également le secteur (bus à haut niveau de service).",
     "E 线往返票价 $3.50；从 Expo Park 出发的末班车东行为晚上 11:50，西行为凌晨 12:10；活动前 2–3 小时开始加强班次，活动后持续 1–2 小时。步行时间：Expo Park/USC 站（6 分钟）；Expo/Vermont 站（6 分钟）。最近的公交车站：Figueroa/Exposition、Vermont/Exposition（列出的最近车站）。从公交车站步行时间：Figueroa/Exposition（11 分钟）；Vermont/Exposition（7 分钟）。自行车道：有——Figueroa St 因\"MyFigueroa\"项目进行了自行车安全改善。Metro J 线（快速公交）也提供服务。"),
    ("LA Memorial Coliseum", "congestion", 0, "high_congestion_entry_roads",
     "Figueroa St, W. Martin Luther King Jr. Blvd, S. Hoover St, Exposition Blvd (se registran cierres de giro a la izquierda en estas intersecciones durante eventos grandes)",
     "Figueroa St, W. Martin Luther King Jr. Blvd, S. Hoover St, Exposition Blvd (fermetures de tourne-à-gauche signalées à ces intersections lors de grands événements)",
     "Figueroa St、W. Martin Luther King Jr. Blvd、S. Hoover St、Exposition Blvd（大型活动期间这些路口会关闭左转车道）"),
    ("LA Memorial Coliseum", "congestion", 0, "known_congestion_exit_roads",
     "Los mismos corredores (Figueroa St, Exposition Blvd, Vermont Ave) — la salida después del evento se registra con un retraso de 45–60 min",
     "Mêmes corridors (Figueroa St, Exposition Blvd, Vermont Ave) — la sortie après l'événement est signalée comme retardée de 45 à 60 min",
     "同样的路段（Figueroa St、Exposition Blvd、Vermont Ave）——活动结束后离场记录延误 45–60 分钟"),
    ("LA Memorial Coliseum", "congestion", 0, "general_tdm_notes",
     "El Coliseum promueve SoCal511 (Go511.com/app) para actualizaciones de tráfico en vivo y fomenta el uso de la Línea E de Metro para evitar demoras de tráfico/estacionamiento",
     "Le Coliseum recommande SoCal511 (Go511.com/app) pour les informations trafic en direct et encourage l'utilisation de la ligne E de Metro pour éviter les retards liés à la circulation/au stationnement",
     "体育场建议使用 SoCal511（Go511.com/app）获取实时路况信息，并鼓励使用 Metro E 线以避免交通/停车延误"),

    # ── SoFi Stadium ────────────────────────────────────────────────────────
    ("SoFi Stadium", "parking", 0, "price_notes",
     "Día del evento: ~$80 (NFL), ~$88 (no NFL). Anticipado: ~$40 (NFL), ~$77 (no NFL). Todos los precios son aproximados (~$); valores según se indican en el documento.",
     "Jour de l'événement : ~80 $ (NFL), ~88 $ (hors NFL). Tarif anticipé : ~40 $ (NFL), ~77 $ (hors NFL). Tous les prix sont approximatifs (~$) ; valeurs telles qu'indiquées dans le document.",
     "活动当天：约 $80（NFL）、约 $88（非 NFL）。提前购买：约 $40（NFL）、约 $77（非 NFL）。所有价格均为近似值（~$）；数值来自原始文档。"),
    ("SoFi Stadium", "parking", 0, "surge_notes",
     "SoFi utiliza precios basados en la demanda. Los precios aumentan a medida que se acerca la fecha.",
     "SoFi applique une tarification basée sur la demande. Les prix augmentent à l'approche de la date.",
     "SoFi 采用基于需求的定价。价格会随着日期临近而上涨。"),
    ("SoFi Stadium", "parking", 0, "notes",
     "El más cercano a las puertas Oeste/Suroeste. El estadio exige la compra 100% anticipada, solo con pase móvil. La zona Purple ha sido eliminada de forma permanente. Se puede encontrar estacionamiento más económico fuera del estadio a través de ParkWhiz o SpotHero (riesgos de seguridad).",
     "Le plus proche des portes Ouest/Sud-Ouest. Le stade impose un achat 100 % anticipé, avec pass mobile uniquement. La zone Purple a été définitivement supprimée. Un stationnement moins cher peut être trouvé en dehors du stade via ParkWhiz ou SpotHero (risques de sécurité).",
     "距西/西南门最近。体育场要求 100% 提前购买，仅接受手机通行证。Purple 区已永久取消。可通过 ParkWhiz 或 SpotHero 在体育场外找到更便宜的停车位（存在安全风险）。"),
    ("SoFi Stadium", "parking", 1, "price_notes",
     "Día del evento: ~$100 (NFL), ~$77–83 (no NFL). Anticipado: ~$60 (NFL), ~$77 (no NFL). Todos los precios son aproximados (~$).",
     "Jour de l'événement : ~100 $ (NFL), ~77–83 $ (hors NFL). Tarif anticipé : ~60 $ (NFL), ~77 $ (hors NFL). Tous les prix sont approximatifs (~$).",
     "活动当天：约 $100（NFL）、约 $77–83（非 NFL）。提前购买：约 $60（NFL）、约 $77（非 NFL）。所有价格均为近似值（~$）。"),
    ("SoFi Stadium", "parking", 1, "surge_notes",
     "SoFi utiliza precios basados en la demanda. Los precios aumentan a medida que se acerca la fecha.",
     "SoFi applique une tarification basée sur la demande. Les prix augmentent à l'approche de la date.",
     "SoFi 采用基于需求的定价。价格会随着日期临近而上涨。"),
    ("SoFi Stadium", "parking", 1, "notes",
     "El más cercano a la puerta Este/Sureste.",
     "Le plus proche de la porte Est/Sud-Est.",
     "距东/东南门最近。"),
    ("SoFi Stadium", "parking", 2, "price_notes",
     "Día del evento: ~$120 (NFL), ~$88 (no NFL). Anticipado: ~$80 (NFL), ~$77 (no NFL). Todos los precios son aproximados (~$).",
     "Jour de l'événement : ~120 $ (NFL), ~88 $ (hors NFL). Tarif anticipé : ~80 $ (NFL), ~77 $ (hors NFL). Tous les prix sont approximatifs (~$).",
     "活动当天：约 $120（NFL）、约 $88（非 NFL）。提前购买：约 $80（NFL）、约 $77（非 NFL）。所有价格均为近似值（~$）。"),
    ("SoFi Stadium", "parking", 2, "surge_notes",
     "SoFi utiliza precios basados en la demanda. Los precios aumentan a medida que se acerca la fecha.",
     "SoFi applique une tarification basée sur la demande. Les prix augmentent à l'approche de la date.",
     "SoFi 采用基于需求的定价。价格会随着日期临近而上涨。"),
    ("SoFi Stadium", "parking", 2, "notes",
     "El más cercano a la puerta Norte.",
     "Le plus proche de la porte Nord.",
     "距北门最近。"),
    ("SoFi Stadium", "parking", 3, "price_notes",
     "Día del evento: ~$125+ (NFL), ~$70 (no NFL). Anticipado: ~$100 (NFL), ~$50 (no NFL). La tarifa del día del evento de la NFL se indica como '$125+'; price_max solo almacena el valor mínimo. Todos los precios son aproximados (~$).",
     "Jour de l'événement : ~125 $+ (NFL), ~70 $ (hors NFL). Tarif anticipé : ~100 $ (NFL), ~50 $ (hors NFL). Le tarif du jour de match NFL est indiqué comme « 125 $+ » ; price_max ne stocke que la valeur plancher. Tous les prix sont approximatifs (~$).",
     "活动当天：约 $125+（NFL）、约 $70（非 NFL）。提前购买：约 $100（NFL）、约 $50（非 NFL）。NFL 活动当天费率标注为\"$125+\"；price_max 仅记录该下限值。所有价格均为近似值（~$）。"),
    ("SoFi Stadium", "parking", 3, "surge_notes",
     "SoFi utiliza precios basados en la demanda. Los precios aumentan a medida que se acerca la fecha.",
     "SoFi applique une tarification basée sur la demande. Les prix augmentent à l'approche de la date.",
     "SoFi 采用基于需求的定价。价格会随着日期临近而上涨。"),
    ("SoFi Stadium", "parking", 3, "notes",
     "Los vehículos de gran tamaño (limusina/autobús/casa rodante) y el 'tailgating' (fiestas en el estacionamiento) solo están permitidos en la zona Pink.",
     "Les véhicules surdimensionnés (limousine/bus/camping-car) et le tailgating (fêtes sur le parking) ne sont autorisés que dans la zone Pink.",
     "超大型车辆（豪华轿车/巴士/房车）以及车尾派对（tailgating）仅允许在 Pink 区。"),
    ("SoFi Stadium", "parking", 4, "price_notes",
     "Día del evento: ~$200+ (NFL), ~$120 (no NFL). Anticipado: ~$120 (NFL), ~$80 (no NFL). La tarifa del día del evento de la NFL se indica como '$200+'; price_max solo almacena el valor mínimo. Todos los precios son aproximados (~$).",
     "Jour de l'événement : ~200 $+ (NFL), ~120 $ (hors NFL). Tarif anticipé : ~120 $ (NFL), ~80 $ (hors NFL). Le tarif du jour de match NFL est indiqué comme « 200 $+ » ; price_max ne stocke que la valeur plancher. Tous les prix sont approximatifs (~$).",
     "活动当天：约 $200+（NFL）、约 $120（非 NFL）。提前购买：约 $120（NFL）、约 $80（非 NFL）。NFL 活动当天费率标注为\"$200+\"；price_max 仅记录该下限值。所有价格均为近似值（~$）。"),
    ("SoFi Stadium", "parking", 4, "surge_notes",
     "SoFi utiliza precios basados en la demanda. Los precios aumentan a medida que se acerca la fecha.",
     "SoFi applique une tarification basée sur la demande. Les prix augmentent à l'approche de la date.",
     "SoFi 采用基于需求的定价。价格会随着日期临近而上涨。"),
    ("SoFi Stadium", "parking", 5, "price_notes",
     "Día del evento: ~$88 (no NFL). Anticipado: ~$88 (no NFL). No se indica tarifa de la NFL para este garaje. Todos los precios son aproximados (~$).",
     "Jour de l'événement : ~88 $ (hors NFL). Tarif anticipé : ~88 $ (hors NFL). Aucun tarif NFL indiqué pour ce parking. Tous les prix sont approximatifs (~$).",
     "活动当天：约 $88（非 NFL）。提前购买：约 $88（非 NFL）。该车库未列出 NFL 费率。所有价格均为近似值（~$）。"),
    ("SoFi Stadium", "parking", 5, "surge_notes",
     "SoFi utiliza precios basados en la demanda. Los precios aumentan a medida que se acerca la fecha.",
     "SoFi applique une tarification basée sur la demande. Les prix augmentent à l'approche de la date.",
     "SoFi 采用基于需求的定价。价格会随着日期临近而上涨。"),
    ("SoFi Stadium", "parking", 6, "price_notes",
     "Día del evento: ~$66 (no NFL). Anticipado: ~$55 (no NFL). No se indica tarifa de la NFL para este garaje. Todos los precios son aproximados (~$).",
     "Jour de l'événement : ~66 $ (hors NFL). Tarif anticipé : ~55 $ (hors NFL). Aucun tarif NFL indiqué pour ce parking. Tous les prix sont approximatifs (~$).",
     "活动当天：约 $66（非 NFL）。提前购买：约 $55（非 NFL）。该车库未列出 NFL 费率。所有价格均为近似值（~$）。"),
    ("SoFi Stadium", "parking", 6, "surge_notes",
     "SoFi utiliza precios basados en la demanda. Los precios aumentan a medida que se acerca la fecha.",
     "SoFi applique une tarification basée sur la demande. Les prix augmentent à l'approche de la date.",
     "SoFi 采用基于需求的定价。价格会随着日期临近而上涨。"),
    ("SoFi Stadium", "parking", 6, "notes",
     "El más cercano a las puertas Oeste/Suroeste (junto con la zona Blue).",
     "Le plus proche des portes Ouest/Sud-Ouest (avec la zone Blue).",
     "距西/西南门最近（与 Blue 区一样）。"),
    ("SoFi Stadium", "parking", 7, "price_notes",
     "Día del evento: ~$66 (no NFL). Anticipado: ~$66 (no NFL). No se indica tarifa de la NFL para este garaje. Todos los precios son aproximados (~$).",
     "Jour de l'événement : ~66 $ (hors NFL). Tarif anticipé : ~66 $ (hors NFL). Aucun tarif NFL indiqué pour ce parking. Tous les prix sont approximatifs (~$).",
     "活动当天：约 $66（非 NFL）。提前购买：约 $66（非 NFL）。该车库未列出 NFL 费率。所有价格均为近似值（~$）。"),
    ("SoFi Stadium", "parking", 7, "surge_notes",
     "SoFi utiliza precios basados en la demanda. Los precios aumentan a medida que se acerca la fecha.",
     "SoFi applique une tarification basée sur la demande. Les prix augmentent à l'approche de la date.",
     "SoFi 采用基于需求的定价。价格会随着日期临近而上涨。"),
    ("SoFi Stadium", "parking", 8, "price_notes",
     "Día del evento: ~$77 (no NFL). Anticipado: ~$71 (no NFL). No se indica tarifa de la NFL para este garaje. Todos los precios son aproximados (~$).",
     "Jour de l'événement : ~77 $ (hors NFL). Tarif anticipé : ~71 $ (hors NFL). Aucun tarif NFL indiqué pour ce parking. Tous les prix sont approximatifs (~$).",
     "活动当天：约 $77（非 NFL）。提前购买：约 $71（非 NFL）。该车库未列出 NFL 费率。所有价格均为近似值（~$）。"),
    ("SoFi Stadium", "parking", 8, "surge_notes",
     "SoFi utiliza precios basados en la demanda. Los precios aumentan a medida que se acerca la fecha.",
     "SoFi applique une tarification basée sur la demande. Les prix augmentent à l'approche de la date.",
     "SoFi 采用基于需求的定价。价格会随着日期临近而上涨。"),
    ("SoFi Stadium", "parking", 9, "price_notes",
     "Día del evento: $313 (solo vehículos grandes). No se indica precio anticipado.",
     "Jour de l'événement : 313 $ (véhicules de grande taille uniquement). Aucun tarif anticipé indiqué.",
     "活动当天：$313（仅限大型车辆）。未列出提前购买价格。"),
    ("SoFi Stadium", "parking", 9, "surge_notes",
     "SoFi utiliza precios basados en la demanda. Los precios aumentan a medida que se acerca la fecha.",
     "SoFi applique une tarification basée sur la demande. Les prix augmentent à l'approche de la date.",
     "SoFi 采用基于需求的定价。价格会随着日期临近而上涨。"),
    ("SoFi Stadium", "parking", 9, "notes",
     "Solo vehículos grandes.",
     "Véhicules de grande taille uniquement.",
     "仅限大型车辆。"),
    ("SoFi Stadium", "curb", 0, "rideshare_zone_description",
     "Zona de recogida en Kareem Ct. y Manchester Blvd. Los visitantes que llegan y salen deben acceder desde Crenshaw Blvd, girando hacia Pincay Dr. en dirección oeste para llegar a la zona de entrega y recogida",
     "Zone de prise en charge sur Kareem Ct. et Manchester Blvd. Les visiteurs arrivant et repartant doivent accéder depuis Crenshaw Blvd, en tournant vers Pincay Dr. en direction ouest pour atteindre la zone de dépose et de prise en charge",
     "接送区位于 Kareem Ct. 与 Manchester Blvd.。到达和离开的宾客须从 Crenshaw Blvd 进入，转入西行方向的 Pincay Dr. 以到达上下客区顶部"),
    ("SoFi Stadium", "curb", 0, "rideshare_zone_open_window",
     "Siempre", "Toujours", "全天开放"),
    ("SoFi Stadium", "curb", 0, "taxi_accessible_zone",
     "Igual que la zona de recogida", "Identique à la zone de prise en charge", "与接客区相同"),
    ("SoFi Stadium", "curb", 0, "private_vehicle_dropoff",
     "acceso al recinto por Prairie Ave. en dirección norte, girando hacia el este en Arbor Vitae St.",
     "accès au site par Prairie Ave. en direction nord, en tournant vers l'est sur Arbor Vitae St.",
     "从北行方向的 Prairie Ave. 进入场地，然后转入东行方向的 Arbor Vitae St."),
    ("SoFi Stadium", "curb", 0, "no_stop_zones",
     "Vecindarios; negocios privados; estacionamientos comerciales; no se permite 'tailgating' ni vehículos de gran tamaño en ningún lote excepto Pink",
     "Quartiers résidentiels ; commerces privés ; parkings commerciaux ; tailgating et véhicules surdimensionnés interdits dans tous les parkings sauf Pink",
     "居民区；私人商业场所；零售停车场；除 Pink 区外，所有停车场均禁止车尾派对（tailgating）和超大型车辆"),
    ("SoFi Stadium", "curb", 0, "curbside_restrictions",
     "Los oficiales de control de tráfico exigen estrictamente rutas de entrada específicas y prohíben los giros a la izquierda/derecha hacia ciertos lotes. Se prohíben los giros a la izquierda hacia la zona Brown desde Pincay Drive, así como los giros a la izquierda hacia varios lotes desde Century Boulevard.",
     "Les agents de contrôle de la circulation imposent strictement des itinéraires d'entrée spécifiques et interdisent les virages à gauche/droite vers certains parkings. Les virages à gauche vers la zone Brown depuis Pincay Drive, ainsi que les virages à gauche vers divers parkings depuis Century Boulevard, sont interdits.",
     "交通管制人员严格执行特定的进场路线，并禁止向部分停车场左转/右转。禁止从 Pincay Drive 左转进入 Brown 区，也禁止从 Century Boulevard 左转进入多个停车场。"),
    ("SoFi Stadium", "transit", 0, "gbfs_dock_description",
     "Sin patinetes", "Pas de trottinette", "无滑板车"),
    ("SoFi Stadium", "transit", 0, "transit_notes",
     "No hay patinetes ni bicicletas de alquiler disponibles cerca de SoFi. Paradas de autobús más cercanas: Prairie y Kelso (2 min a pie); Los Angeles Stadium (6 min a pie). No hay carriles bici, aceras amplias alrededor de la manzana.",
     "Aucune trottinette ni vélo en location à proximité de SoFi. Arrêts de bus les plus proches : Prairie et Kelso (2 min à pied) ; Los Angeles Stadium (6 min à pied). Pas de pistes cyclables, larges trottoirs autour du pâté de maisons.",
     "SoFi 附近没有可租用的滑板车和自行车。最近的公交车站：Prairie 与 Kelso（步行 2 分钟）；Los Angeles Stadium（步行 6 分钟）。没有自行车道，街区周围人行道较宽。"),
    ("SoFi Stadium", "congestion", 0, "arrival_notes",
     "Partidos de la NFL: los estacionamientos abren 4–5 horas antes del inicio, las puertas abren 2–3 horas antes del inicio. Conciertos/no NFL: los estacionamientos abren 3–4 horas antes, las puertas abren 1–2 horas antes.",
     "Matchs NFL : les parkings ouvrent 4 à 5 heures avant le coup d'envoi, les portes ouvrent 2 à 3 heures avant le coup d'envoi. Concerts/hors NFL : les parkings ouvrent 3 à 4 heures avant, les portes ouvrent 1 à 2 heures avant.",
     "NFL 比赛：停车场在开球前 4–5 小时开放，大门在开球前 2–3 小时开放。演唱会/非 NFL 活动：停车场在活动前 3–4 小时开放，大门在活动前 1–2 小时开放。"),
    ("SoFi Stadium", "congestion", 0, "high_congestion_entry_roads",
     "Mucho tráfico en Century Blvd y Prairie Ave; Arbor Vitae St; I-405 Sur (salidas Century Blvd/Florence Ave)",
     "Fort trafic sur Century Blvd et Prairie Ave ; Arbor Vitae St ; I-405 Sud (sorties Century Blvd/Florence Ave)",
     "Century Blvd 与 Prairie Ave 交通繁忙；Arbor Vitae St；I-405 南（Century Blvd / Florence Ave 出口）"),
    ("SoFi Stadium", "congestion", 0, "known_congestion_exit_roads",
     "Entrada a la I-105 Sur (Century); entrada a la I-405 Norte (Prairie)",
     "Entrée I-105 Sud (Century) ; entrée I-405 Nord (Prairie)",
     "I-105 南向入口（Century）；I-405 北向入口（Prairie）"),

    # ── Dodger Stadium ──────────────────────────────────────────────────────
    ("Dodger Stadium", "venue", 0, "capacity_text",
     "16,000 automóviles, en 21 lotes escalonados",
     "16 000 véhicules, répartis sur 21 parkings en terrasses",
     "16,000 个车位，分布在 21 个阶梯式停车场"),
    ("Dodger Stadium", "parking", 0, "price_notes",
     "General: $40 anticipado / $45 en la puerta. Preferencial: $65 (solo anticipado, no se vende en la puerta). Autobús/limusina/vehículo de gran tamaño: $65 anticipado / $70 en la puerta.",
     "Général : 40 $ à l'avance / 45 $ sur place. Préférentiel : 65 $ (vente anticipée uniquement, non disponible sur place). Bus/limousine/véhicule surdimensionné : 65 $ à l'avance / 70 $ sur place.",
     "普通停车位：提前购买 $40 / 现场购买 $45。优选停车位：$65（仅限提前购买，现场不售）。巴士/豪华轿车/超大型车辆：提前购买 $65 / 现场购买 $70。"),
    ("Dodger Stadium", "parking", 0, "surge_notes",
     "Las tarifas no se aplican a eventos especiales (por ejemplo, conciertos, etc.). Las tarifas de estacionamiento para eventos especiales variarán\". Además: el estacionamiento con traslado de Union Station sube a $65 y el de Harbor Gateway a $10 en días específicos de partidos/zonas de aficionados de la Copa Mundial 2026 (12, 15, 18, 21, 25, 26, 27, 28 de junio; 2 y 10 de julio)",
     "Les tarifs ne s'appliquent pas aux événements spéciaux (par exemple, concerts, etc.). Les tarifs de stationnement pour les événements spéciaux varieront. » Par ailleurs : le parking-relais d'Union Station passe à 65 $ et celui de Harbor Gateway à 10 $ certains jours de matchs/zones de supporters de la Coupe du Monde 2026 (12, 15, 18, 21, 25, 26, 27, 28 juin, 2 et 10 juillet)",
     "该费率不适用于特殊活动（例如演唱会等）。特殊活动的停车费率将有所不同。\"此外：在 2026 年世界杯特定比赛/球迷区活动日（6 月 12、15、18、21、25、26、27、28 日，7 月 2、10 日），Union Station 换乘停车场费率升至 $65，Harbor Gateway 升至 $10"),
    ("Dodger Stadium", "parking", 0, "notes",
     "Lote más cercano a la entrada del recinto: los lotes preferenciales son los más cercanos. Estacionamiento accesible en los lotes B, D, F, G, K, L, N, P con transporte de cortesía ADA (llamar al 323-224-2611). Los titulares de abonos de temporada pueden reservar lugares con nombre por teléfono/correo electrónico. Recogida/entrega de Uber (socio oficial de viajes compartidos): Lote 1, entrando por la Puerta B (trasladado del Lote 11 para reducir la congestión en la Puerta A). Zona de carga/descarga de taxis en el borde exterior del Lote G. Está estrictamente prohibido el 'tailgating' y el consumo de alcohol en todos los lotes; límite de velocidad de 14 mph en los estacionamientos.",
     "Parking le plus proche de l'entrée du site : les parkings préférentiels sont les plus proches. Stationnement accessible dans les parkings B, D, F, G, K, L, N, P avec navette ADA de courtoisie (appeler le 323-224-2611). Places réservées nominatives disponibles pour les détenteurs d'abonnement saison par téléphone/e-mail. Prise en charge/dépose Uber (partenaire officiel de covoiturage) : Parking 1, entrée par la Porte B (déplacé du Parking 11 pour réduire la congestion à la Porte A). Zone de chargement/déchargement de taxis le long du bord extérieur du Parking G. Le tailgating et la consommation d'alcool sont strictement interdits dans tous les parkings ; limite de vitesse de 14 mph (22 km/h) dans les parkings.",
     "距场馆入口最近的停车场：优选停车场距离最近。B、D、F、G、K、L、N、P 停车场提供无障碍停车位，并配有 ADA 免费接驳车（电话 323-224-2611）。赛季套票持有者可通过电话/电子邮件预订指定车位。Uber（官方网约车合作伙伴）上下客点：1 号停车场，从 B 门进入（原为 11 号停车场，已调整以缓解 A 门拥堵）。出租车装卸区位于 G 停车场外缘。所有停车场严禁车尾派对（tailgating）和饮酒；场内限速 14 英里/小时。"),
    ("Dodger Stadium", "curb", 0, "rideshare_zone_description",
     "Uber, el socio oficial de viajes compartidos de los Dodgers, ha trasladado su punto de recogida y entrega del Lote 11 al Lote 1. Los vehículos de Uber ahora ingresarán por la Puerta B, con el fin de reducir la congestión en la Puerta A y agilizar la llegada y entrega de los aficionados.",
     "Uber, partenaire officiel de covoiturage des Dodgers, a déplacé son point de prise en charge et de dépose du Parking 11 au Parking 1. Les véhicules Uber entreront désormais par la Porte B afin de réduire la congestion à la Porte A et d'accélérer l'arrivée et la dépose des supporters.",
     "Uber 作为道奇队官方网约车合作伙伴，已将其上下客地点从 11 号停车场迁至 1 号停车场。Uber 车辆现将从 B 门进入，以缓解 A 门拥堵并加快球迷的到达与下车速度。"),
    ("Dodger Stadium", "curb", 0, "rideshare_zone_open_window",
     "siempre", "toujours", "全天开放"),
    ("Dodger Stadium", "curb", 0, "taxi_accessible_zone",
     "Zona de carga/descarga de taxis en el borde exterior del Lote G",
     "Zone de chargement/déchargement de taxis le long du bord extérieur du Parking G",
     "出租车装卸区位于 G 停车场外缘"),
    ("Dodger Stadium", "curb", 0, "private_vehicle_dropoff",
     "Utilice cualquier puerta para automóviles (Sunset Puerta A, Scott Puerta B, Golden State Puerta C, Academy Puerta D o Downtown Puerta E).",
     "Utilisez n'importe quelle porte pour automobiles (Sunset Porte A, Scott Porte B, Golden State Porte C, Academy Porte D ou Downtown Porte E).",
     "可使用任意车辆入口（Sunset A 门、Scott B 门、Golden State C 门、Academy D 门或 Downtown E 门）。"),
    ("Dodger Stadium", "curb", 0, "no_stop_zones",
     "Stadium Way (Avenue of the Palms); las vías públicas de Elysian Park; bordillos rojos",
     "Stadium Way (Avenue of the Palms) ; voies publiques d'Elysian Park ; bordures rouges",
     "Stadium Way（Avenue of the Palms）；Elysian Park 公共道路；红色路缘"),
    ("Dodger Stadium", "curb", 0, "curbside_restrictions",
     "Está estrictamente prohibido el 'tailgating' y el consumo de alcohol en todos los lotes; límite de velocidad de 14 mph en los estacionamientos",
     "Le tailgating et la consommation d'alcool sont strictement interdits dans tous les parkings ; limite de vitesse de 14 mph (22 km/h)",
     "所有停车场严禁车尾派对（tailgating）和饮酒；场内限速 14 英里/小时"),
    ("Dodger Stadium", "transit", 0, "gbfs_dock_description",
     "No hay zonas de patinetes/estaciones de bicicletas cerca",
     "Aucune zone de trottinettes/bornes de vélos à proximité",
     "附近没有滑板车/停靠站点"),
    ("Dodger Stadium", "transit", 0, "transit_notes",
     "Tiempo a pie desde la estación: estación Chinatown: 27 min. Parada de autobús más cercana: parada de Metro en Sunset Blvd. Tiempo a pie desde la parada de autobús: Sunset Blvd (15 min). Carril/ruta para bicicletas cerca: Sí — los Dodgers \"fomentan formas alternativas de transporte\", con estacionamientos para bicicletas en todos los niveles/torniquetes; sin nombre específico de calle/carril. El transporte gratuito Dodger Stadium Express conecta Union Station con 5 paradas de la Línea J de South Bay (Slauson, Manchester, Harbor Freeway, Rosecrans, Harbor Gateway Transit Center). Tarifa regular de Metro: $1.75 solo ida / $3.50 ida y vuelta (el Express en sí es gratuito con el boleto). Los autobuses desde Union Station circulan cada 5–10 min desde 3 horas antes del partido hasta el final de la 2ª entrada. Los autobuses de la Línea J circulan cada 30 min desde 3 horas antes. El servicio de regreso finaliza 1 hora después del último out (o 30 min después de eventos posteriores al partido).",
     "Temps de marche depuis la station : station Chinatown : 27 min. Arrêt de bus le plus proche : arrêt Metro sur Sunset Blvd. Temps de marche depuis l'arrêt de bus : Sunset Blvd (15 min). Piste/voie cyclable à proximité : Oui — les Dodgers « encouragent les modes de transport alternatifs », des supports à vélos sont présents à tous les niveaux/tourniquets ; aucun nom de rue/voie spécifique. La navette gratuite Dodger Stadium Express relie Union Station et 5 arrêts de la ligne J de South Bay (Slauson, Manchester, Harbor Freeway, Rosecrans, Harbor Gateway Transit Center). Tarif Metro standard : 1,75 $ l'aller simple / 3,50 $ l'aller-retour (la navette Express elle-même est gratuite avec le billet). Les bus depuis Union Station circulent toutes les 5 à 10 min à partir de 3 heures avant le match jusqu'à la fin de la 2e manche. Les bus de la ligne J circulent toutes les 30 min à partir de 3 heures avant. Le service de retour se termine 1 heure après le dernier retrait (ou 30 min après les événements d'après-match).",
     "从车站步行时间：Chinatown 站：27 分钟。最近的公交车站：Sunset Blvd 上的 Metro 巴士站。从公交车站步行时间：Sunset Blvd（15 分钟）。附近自行车道/路径：有——道奇队\"鼓励采用其他出行方式\"，各层/检票口均设有自行车架；无具体街道/车道名称。免费的 Dodger Stadium Express 接驳车连接 Union Station 与南湾 J 线的 5 个站点（Slauson、Manchester、Harbor Freeway、Rosecrans、Harbor Gateway Transit Center）。Metro 常规票价单程 $1.75/往返 $3.50（凭票免费搭乘 Express 接驳车）。从 Union Station 出发的巴士在比赛前 3 小时开始每 5–10 分钟一班，持续至第二局结束。J 线巴士在比赛前 3 小时开始每 30 分钟一班。返程服务在比赛最后一个出局后 1 小时结束（或赛后活动结束后 30 分钟）。"),
    ("Dodger Stadium", "congestion", 0, "arrival_notes",
     "Las puertas de estacionamiento abren 2.5 horas antes de la hora del partido, las puertas del estadio abren 2 horas antes.",
     "Les portes du parking ouvrent 2,5 heures avant le début du match, les portes du stade ouvrent 2 heures avant.",
     "停车场大门在比赛开始前 2.5 小时开放，体育场大门在比赛开始前 2 小时开放。"),
    ("Dodger Stadium", "congestion", 0, "high_congestion_entry_roads",
     "Vin Scully Ave/Sunset Blvd para la Puerta A; Academy Rd para las Puertas C/D; Stadium Way/110 Fwy para la Puerta E.",
     "Vin Scully Ave/Sunset Blvd pour la Porte A ; Academy Rd pour les Portes C/D ; Stadium Way/110 Fwy pour la Porte E.",
     "A 门经 Vin Scully Ave/Sunset Blvd；C/D 门经 Academy Rd；E 门经 Stadium Way/110 高速公路。"),
    ("Dodger Stadium", "congestion", 0, "known_congestion_exit_roads",
     "Downtown/Academy/Sunset", "Downtown/Academy/Sunset", "Downtown/Academy/Sunset"),
    ("Dodger Stadium", "congestion", 0, "general_tdm_notes",
     "Transporte gratuito Dodger Stadium Express; programa de estacionamientos para bicicletas; transporte de cortesía ADA entre los lotes y las puertas.",
     "Navette gratuite Dodger Stadium Express ; programme de supports à vélos ; navette ADA de courtoisie entre les parkings et les portes.",
     "免费的 Dodger Stadium Express 接驳车；自行车停放计划；停车场与大门之间的 ADA 免费接驳车。"),

    # ── DTLA Arena ──────────────────────────────────────────────────────────
    ("DTLA Arena", "venue", 0, "capacity_text",
     "3,300 espacios en lotes propiedad de la arena",
     "3 300 places dans les parkings appartenant à l'arène",
     "3,300 个车位，位于场馆自有停车场"),
    ("DTLA Arena", "parking", 0, "price_notes",
     "Garaje Oeste (Lote W, Puertas E y F): tarifa plana de $40 para estacionamiento de evento (más impuesto municipal de estacionamiento). Garaje Este (Lote E): máximo $40 (por tiempo). Garaje Oeste (Lote W, Puerta B): tarifa plana de $10–$50 (más impuesto municipal) según el evento.",
     "Garage Ouest (Parking W, Portes E et F) : tarif forfaitaire de 40 $ pour le stationnement événementiel (plus taxe municipale de stationnement). Garage Est (Parking E) : 40 $ maximum (tarif horaire). Garage Ouest (Parking W, Porte B) : tarif forfaitaire de 10 $ à 50 $ (plus taxe municipale) selon l'événement.",
     "西停车楼（W 停车场，E 和 F 门）：活动统一停车费 $40（外加市停车税）。东停车楼（E 停车场）：最高 $40（按时计费）。西停车楼（W 停车场，B 门）：统一费率 $10–$50（外加市税），具体视活动而定。"),
    ("DTLA Arena", "parking", 0, "surge_notes",
     "La tarifa plana de la Puerta B varía explícitamente entre $10 y $50 \"según el evento\", es decir, una variabilidad integrada según el evento en lugar de un único indicador de sobreprecio",
     "Le tarif forfaitaire de la Porte B varie explicitement entre 10 $ et 50 $ « selon l'événement », c'est-à-dire une variabilité intégrée liée à l'événement plutôt qu'un simple indicateur de majoration",
     "B 门的统一费率明确在 $10–$50 之间浮动，\"具体视活动而定\"——即内置的按活动浮动机制，而非单一的加价标记"),
    ("DTLA Arena", "parking", 0, "notes",
     "Lote más cercano a la entrada del recinto: Lote 1; Lote W. El Lote W y el Lote E abren de 6 AM a 2 AM todos los días. El Lote 1 y el Lote C abren 2.5 horas antes de un evento; todos los demás lotes abren 90 minutos antes y permanecen con personal 60 minutos después, sin privilegios de estacionamiento nocturno ni de entrada y salida. La Puerta B abre 3.5 horas antes del evento; los vehículos de gran tamaño (limusina/autobús/casa rodante) necesitan reservas con 10 días de anticipación; estacionamiento para motocicletas en el nivel P1 del Garaje Oeste; estacionamiento para personas con discapacidad por orden de llegada; carga de vehículos eléctricos a $3.50/hora (primeras 4 horas), $4.50/hora después, en ambos garajes.",
     "Parking le plus proche de l'entrée du site : Parking 1 ; Parking W. Le Parking W et le Parking E ouvrent de 6h à 2h tous les jours. Le Parking 1 et le Parking C ouvrent 2,5 heures avant un événement ; tous les autres parkings ouvrent 90 minutes avant et restent surveillés 60 minutes après, sans possibilité de stationnement de nuit ni d'aller-retour. La Porte B ouvre 3,5 heures avant l'événement ; les véhicules surdimensionnés (limousine/bus/camping-car) nécessitent une réservation 10 jours à l'avance ; stationnement moto au niveau P1 du Garage Ouest ; stationnement pour personnes handicapées par ordre d'arrivée ; recharge de véhicules électriques à 3,50 $/h (les 4 premières heures), 4,50 $/h ensuite, dans les deux garages.",
     "距场馆入口最近的停车场：1 号停车场；W 停车场。W 停车场和 E 停车场每日 6:00 至凌晨 2:00 开放。1 号停车场和 C 停车场在活动前 2.5 小时开放；其他所有停车场在活动前 90 分钟开放，并在活动后保持有人值守 60 分钟，不提供过夜停车或出入特权。B 门在活动前 3.5 小时开放；超大型车辆（豪华轿车/巴士/房车）需提前 10 天预订；摩托车停放在西停车楼 P1 层；残障人士停车位按先到先得原则提供；两座停车楼均提供电动车充电服务，前 4 小时每小时 $3.50，之后每小时 $4.50。"),
    ("DTLA Arena", "curb", 0, "rideshare_zone_description",
     "Dos zonas designadas: la zona blanca en Chick Hearn Ct. (dirección este) entre L.A. Live Way y Georgia St.; y la zona blanca en Figueroa St. (dirección sur) entre 12th St y Pico",
     "Deux zones désignées : la zone blanche sur Chick Hearn Ct. (direction est) entre L.A. Live Way et Georgia St. ; et la zone blanche sur Figueroa St. (direction sud) entre 12th St et Pico",
     "两个指定区域：Chick Hearn Ct.（东行方向，位于 L.A. Live Way 与 Georgia St. 之间）的白色区域；以及 Figueroa St.（南行方向，位于 12th St 与 Pico 之间）的白色区域"),
    ("DTLA Arena", "curb", 0, "taxi_accessible_zone",
     "Las mismas zonas blancas", "Mêmes zones blanches", "同上述白色区域"),
    ("DTLA Arena", "curb", 0, "no_stop_zones",
     "Chick Hearn Court (antes 11th St.), entre L.A. Live Way y Figueroa, es una zona designada de prohibido estacionar/remolque; la policía de Los Ángeles (LAPD) hace cumplir las señales de \"prohibido detenerse\" en todo el distrito. Cierre de vía el 7/7 en Gilbert Lindsey Dr",
     "Chick Hearn Court (anciennement 11th St.), entre L.A. Live Way et Figueroa, est une zone désignée d'interdiction de stationner/mise en fourrière ; le LAPD fait respecter les panneaux « Arrêt interdit » dans tout le quartier. Fermeture de route le 7/7 à Gilbert Lindsey Dr",
     "Chick Hearn Court（原 11th St.），位于 L.A. Live Way 与 Figueroa 之间，为指定的禁止停车/拖车区域；洛杉矶警察局（LAPD）在全区严格执行\"禁止停车\"标志。7 月 7 日 Gilbert Lindsey Dr 有道路封闭"),
    ("DTLA Arena", "curb", 0, "curbside_restrictions",
     "El 'tailgating' está prohibido en todos los lotes de L.A. LIVE/la arena; el estacionamiento de bicicletas está restringido a dos ubicaciones designadas (nivel P1 del Garaje Este y Gilbert Lindsey Plaza) — a las bicicletas no autorizadas se les cortarán los candados",
     "Le tailgating est interdit dans tous les parkings de L.A. LIVE/de l'arène ; le stationnement des vélos est limité à deux emplacements désignés (niveau P1 du Garage Est et Gilbert Lindsey Plaza) — les cadenas des vélos non autorisés seront coupés",
     "所有 L.A. LIVE/场馆停车场均禁止车尾派对（tailgating）；自行车停放仅限于两个指定地点（东停车楼 P1 层和 Gilbert Lindsey Plaza）——未经授权的自行车锁将被剪断"),
    ("DTLA Arena", "transit", 0, "gbfs_dock_description",
     "Estaciones de Metro Bike Share en Figueroa & 11th, Figueroa & Pico y Pico & Flower",
     "Stations Metro Bike Share à Figueroa & 11th, Figueroa & Pico et Pico & Flower",
     "Metro Bike Share 站点位于 Figueroa & 11th、Figueroa & Pico 以及 Pico & Flower"),
    ("DTLA Arena", "transit", 0, "transit_notes",
     "Tiempos a pie: 2 minutos desde la estación Pico; 15 minutos desde la estación 7th St/Metro Center. Parada de autobús más cercana: se indica que las líneas de Metro y la ruta F de DASH paran en/cerca de Figueroa St., junto a L.A. LIVE. Tiempo a pie desde la parada de autobús: parada Figueroa y 12th (1 min). Carril/ruta para bicicletas cerca: Sí — estaciones de Metro Bike Share cercanas; estacionamiento de bicicletas dedicado en la arena. Metrolink ofrece un pase de fin de semana de $10 con conexiones gratuitas de autobús/tren de Metro; los pasajeros de Amtrak pueden transbordar a Metro Rail en Union Station (se requiere boleto aparte).",
     "Temps de marche : 2 minutes depuis la station Pico ; 15 minutes depuis la station 7th St/Metro Center. Arrêt de bus le plus proche : les lignes Metro et la route DASH F s'arrêtent toutes deux sur/près de Figueroa St., à proximité de L.A. LIVE. Temps de marche depuis l'arrêt de bus : arrêt Figueroa et 12th (1 min). Piste/voie cyclable à proximité : Oui — stations Metro Bike Share à proximité ; stationnement vélo dédié à l'arène. Metrolink propose un pass week-end à 10 $ avec correspondances gratuites bus/rail Metro ; les usagers d'Amtrak peuvent correspondre avec Metro Rail à Union Station (billet séparé requis).",
     "步行时间：距 Pico 站 2 分钟；距 7th St/Metro Center 站 15 分钟。最近的公交车站：Metro 线路及 DASH F 线均在毗邻 L.A. LIVE 的 Figueroa St. 上/附近设站。从公交车站步行时间：Figueroa 与 12th 站（1 分钟）。附近自行车道/路径：有——附近设有 Metro Bike Share 站点；场馆设有专用自行车停放区。Metrolink 提供 $10 周末通票，可免费换乘 Metro 巴士/轻轨；Amtrak 乘客可在 Union Station 换乘 Metro Rail（需单独购票）。"),
    ("DTLA Arena", "congestion", 0, "arrival_notes",
     "El Lote 1 y el Lote C abren 2.5 horas antes del evento; la Puerta B (Garaje Oeste) abre 3.5 horas antes del evento (recomendado para eventos de 3.5 horas o más); todos los demás lotes abren 90 minutos antes.",
     "Le Parking 1 et le Parking C ouvrent 2,5 heures avant l'événement ; la Porte B (Garage Ouest) ouvre 3,5 heures avant l'événement (recommandé pour les événements de 3,5 heures ou plus) ; tous les autres parkings ouvrent 90 minutes avant.",
     "1 号停车场和 C 停车场在活动前 2.5 小时开放；B 门（西停车楼）在活动前 3.5 小时开放（建议时长 3.5 小时以上的活动使用）；其他所有停车场在活动前 90 分钟开放。"),
    ("DTLA Arena", "congestion", 0, "high_congestion_entry_roads",
     "Pico Blvd; Chick Hearn Court; Olympic Blvd",
     "Pico Blvd ; Chick Hearn Court ; Olympic Blvd",
     "Pico Blvd；Chick Hearn Court；Olympic Blvd"),
    ("DTLA Arena", "congestion", 0, "known_congestion_exit_roads",
     "LA Live Way; Francisco St; Flower St",
     "LA Live Way ; Francisco St ; Flower St",
     "LA Live Way；Francisco St；Flower St"),
    ("DTLA Arena", "congestion", 0, "general_tdm_notes",
     "Zonas de prohibido detenerse aplicadas por la LAPD para gestionar la congestión de viajes compartidos; estaciones de Metro Bike Share cercanas; DASH y Metrolink se ofrecen como opciones de acceso alternativas.",
     "Zones d'arrêt interdit appliquées par le LAPD pour gérer la congestion liée au covoiturage ; bornes Metro Bike Share à proximité ; DASH et Metrolink proposés comme options d'accès alternatives.",
     "洛杉矶警察局（LAPD）执行禁止停车区域以管理网约车拥堵；附近设有 Metro Bike Share 停靠点；另提供 DASH 和 Metrolink 作为替代出行方式。"),

    # ── Peacock Theater ─────────────────────────────────────────────────────
    ("Peacock Theater", "venue", 0, "capacity_text",
     "3,300 espacios en lotes propiedad de Crypto.com Arena/Peacock Theater",
     "3 300 places dans les parkings appartenant à Crypto.com Arena/Peacock Theater",
     "3,300 个车位，位于 Crypto.com Arena/Peacock Theater 自有停车场"),
    ("Peacock Theater", "parking", 0, "price_notes",
     "Garaje Oeste (Lote W, Puertas E y F): tarifa plana de $40 para estacionamiento de evento (más impuesto municipal de estacionamiento). Garaje Este (Lote E): máximo $40 (por tiempo). Garaje Oeste (Lote W, Puerta B): tarifa plana de $10–$50 (más impuesto municipal) según el evento. Estacionamiento prepagado disponible en línea a través de AXS.com.",
     "Garage Ouest (Parking W, Portes E et F) : tarif forfaitaire de 40 $ pour le stationnement événementiel (plus taxe municipale de stationnement). Garage Est (Parking E) : 40 $ maximum (tarif horaire). Garage Ouest (Parking W, Porte B) : tarif forfaitaire de 10 $ à 50 $ (plus taxe municipale) selon l'événement. Stationnement prépayé disponible en ligne via AXS.com.",
     "西停车楼（W 停车场，E 和 F 门）：活动统一停车费 $40（外加市停车税）。东停车楼（E 停车场）：最高 $40（按时计费）。西停车楼（W 停车场，B 门）：统一费率 $10–$50（外加市税），具体视活动而定。可通过 AXS.com 在线预付停车费。"),
    ("Peacock Theater", "parking", 0, "surge_notes",
     "La tarifa plana de la Puerta B varía explícitamente entre $10 y $50 \"según el evento\"",
     "Le tarif forfaitaire de la Porte B varie explicitement entre 10 $ et 50 $ « selon l'événement »",
     "B 门的统一费率明确在 $10–$50 之间浮动，\"具体视活动而定\""),
    ("Peacock Theater", "parking", 0, "notes",
     "Lote más cercano a la entrada del recinto: LA Live Parking/Lote W; Lote 1. El Lote W y el Lote E abren de 6 AM a 2 AM todos los días; el Lote C abre 2.5 horas antes de un evento en Peacock Theater; sin privilegios de estacionamiento nocturno ni de entrada y salida; la Puerta B abre 3.5 horas antes del evento (recomendado para eventos de 3.5 horas o más); los vehículos de gran tamaño necesitan arreglos con 10 días de anticipación, no se aceptan en el Lote 1; estacionamiento para motocicletas en el nivel P1 del Garaje Oeste; carga de vehículos eléctricos a $3.50/hora (primeras 4 horas), $4.50/hora después, en ambos garajes.",
     "Parking le plus proche de l'entrée du site : LA Live Parking/Parking W ; Parking 1. Le Parking W et le Parking E ouvrent de 6h à 2h tous les jours ; le Parking C ouvre 2,5 heures avant un événement au Peacock Theater ; aucune possibilité de stationnement de nuit ni d'aller-retour ; la Porte B ouvre 3,5 heures avant l'événement (recommandé pour les événements de 3,5 heures ou plus) ; les véhicules surdimensionnés nécessitent une organisation 10 jours à l'avance, non acceptés au Parking 1 ; stationnement moto au niveau P1 du Garage Ouest ; recharge de véhicules électriques à 3,50 $/h (les 4 premières heures), 4,50 $/h ensuite, dans les deux garages.",
     "距场馆入口最近的停车场：LA Live Parking/W 停车场；1 号停车场。W 停车场和 E 停车场每日 6:00 至凌晨 2:00 开放；C 停车场在 Peacock Theater 活动前 2.5 小时开放；不提供过夜停车或出入特权；B 门在活动前 3.5 小时开放（建议时长 3.5 小时以上的活动使用）；超大型车辆需提前 10 天安排，1 号停车场不接受此类车辆；摩托车停放在西停车楼 P1 层；两座停车楼均提供电动车充电服务，前 4 小时每小时 $3.50，之后每小时 $4.50。"),
    ("Peacock Theater", "curb", 0, "rideshare_zone_description",
     "Zona blanca en Chick Hearn Ct. (dirección este) entre L.A. Live Way y Georgia St.; zona blanca en Figueroa St. (dirección sur) entre 12th St y Pico",
     "Zone blanche sur Chick Hearn Ct. (direction est) entre L.A. Live Way et Georgia St. ; zone blanche sur Figueroa St. (direction sud) entre 12th St et Pico",
     "Chick Hearn Ct.（东行方向，位于 L.A. Live Way 与 Georgia St. 之间）的白色区域；Figueroa St.（南行方向，位于 12th St 与 Pico 之间）的白色区域"),
    ("Peacock Theater", "curb", 0, "taxi_accessible_zone",
     "La misma zona blanca", "Même zone blanche", "同上述白色区域"),
    ("Peacock Theater", "curb", 0, "no_stop_zones",
     "Chick Hearn Court, entre L.A. Live Way y Figueroa, es una zona de prohibido estacionar/remolque; la LAPD hace cumplir la señalización de \"prohibido detenerse\" en todo el distrito",
     "Chick Hearn Court, entre L.A. Live Way et Figueroa, est une zone d'interdiction de stationner/mise en fourrière ; le LAPD fait respecter la signalisation « Arrêt interdit » dans tout le quartier",
     "Chick Hearn Court（位于 L.A. Live Way 与 Figueroa 之间）为禁止停车/拖车区域；洛杉矶警察局（LAPD）在全区严格执行\"禁止停车\"标志"),
    ("Peacock Theater", "curb", 0, "curbside_restrictions",
     "El 'tailgating' está prohibido en todos los lotes de L.A. LIVE/Crypto.com Arena; el estacionamiento de bicicletas está restringido a dos ubicaciones designadas (Garaje Este P1, Gilbert Lindsey Plaza)",
     "Le tailgating est interdit dans tous les parkings de L.A. LIVE/Crypto.com Arena ; le stationnement des vélos est limité à deux emplacements désignés (Garage Est P1, Gilbert Lindsey Plaza)",
     "所有 L.A. LIVE/Crypto.com Arena 停车场均禁止车尾派对（tailgating）；自行车停放仅限于两个指定地点（东停车楼 P1、Gilbert Lindsey Plaza）"),
    ("Peacock Theater", "transit", 0, "gbfs_dock_description",
     "Estaciones de Metro Bike Share en Figueroa & 11th, Figueroa & Pico, Pico & Flower",
     "Stations Metro Bike Share à Figueroa & 11th, Figueroa & Pico, Pico & Flower",
     "Metro Bike Share 站点位于 Figueroa & 11th、Figueroa & Pico、Pico & Flower"),
    ("Peacock Theater", "transit", 0, "transit_notes",
     "Aproximadamente 10 minutos desde la estación Pico. Parada de autobús más cercana: corredor de Figueroa St. Tiempo a pie desde la parada de autobús: ~1–2 min. Carril/ruta para bicicletas cerca: Sí — estaciones de Metro Bike Share en el distrito inmediato; estacionamiento de bicicletas en el complejo del teatro/arena. El pase de fin de semana de Metrolink de $10 incluye conexiones gratuitas de autobús/tren de Metro; los pasajeros de Amtrak pueden transbordar a Metro Rail en Union Station (se requiere boleto aparte).",
     "Environ 10 minutes depuis la station Pico. Arrêt de bus le plus proche : couloir de Figueroa St. Temps de marche depuis l'arrêt de bus : ~1–2 min. Piste/voie cyclable à proximité : Oui — stations Metro Bike Share dans le quartier immédiat ; stationnement vélo au complexe théâtre/arène. Le pass week-end Metrolink à 10 $ inclut des correspondances gratuites bus/rail Metro ; les usagers d'Amtrak peuvent correspondre avec Metro Rail à Union Station (billet séparé requis).",
     "距 Pico 站约 10 分钟。最近的公交车站：Figueroa St. 沿线。从公交车站步行时间：约 1–2 分钟。附近自行车道/路径：有——周边区域设有 Metro Bike Share 站点；剧院/场馆综合体设有自行车停放区。Metrolink $10 周末通票包含免费换乘 Metro 巴士/轻轨；Amtrak 乘客可在 Union Station 换乘 Metro Rail（需单独购票）。"),
    ("Peacock Theater", "congestion", 0, "arrival_notes",
     "El Lote C abre 2.5 horas antes del evento; la Puerta B (Garaje Oeste) abre 3.5 horas antes del evento y se recomienda para eventos de 3.5 horas o más.",
     "Le Parking C ouvre 2,5 heures avant l'événement ; la Porte B (Garage Ouest) ouvre 3,5 heures avant l'événement et est recommandée pour les événements de 3,5 heures ou plus.",
     "C 停车场在活动前 2.5 小时开放；B 门（西停车楼）在活动前 3.5 小时开放，建议时长 3.5 小时以上的活动使用。"),
    ("Peacock Theater", "congestion", 0, "high_congestion_entry_roads",
     "Igual que Crypto", "Identique à Crypto", "与 Crypto 相同"),
    ("Peacock Theater", "congestion", 0, "known_congestion_exit_roads",
     "Igual que Crypto", "Identique à Crypto", "与 Crypto 相同"),
    ("Peacock Theater", "congestion", 0, "general_tdm_notes",
     "Zonas de prohibido detenerse aplicadas por la LAPD para la gestión de viajes compartidos; estaciones de Metro Bike Share cercanas; DASH y Metrolink se ofrecen como acceso alternativo.",
     "Zones d'arrêt interdit appliquées par le LAPD pour la gestion du covoiturage ; bornes Metro Bike Share à proximité ; DASH et Metrolink proposés comme accès alternatif.",
     "洛杉矶警察局（LAPD）执行禁止停车区域以管理网约车；附近设有 Metro Bike Share 停靠点；另提供 DASH 和 Metrolink 作为替代出行方式。"),

    # ── Rose Bowl Stadium ───────────────────────────────────────────────────
    ("Rose Bowl Stadium", "venue", 0, "capacity_text",
     "26,000 espacios", "26 000 places", "26,000 个车位"),
    ("Rose Bowl Stadium", "parking", 0, "price_notes",
     "Para el fútbol americano de UCLA (Nebraska vs. UCLA, 11/8/2025): vehículo regular en la puerta $44 (incluye cargo tecnológico de $4); vehículo de gran tamaño en la puerta $154 (incluye cargo de $4). Compra anticipada: regular $38 (incluye cargo de $3); de gran tamaño $128 (incluye cargo de $3) — disponible hasta las 11:45 PM la noche antes del evento. No se acepta efectivo en la puerta.",
     "Pour le football américain UCLA (Nebraska vs. UCLA, 11/8/2025) : véhicule standard sur place 44 $ (frais technologiques de 4 $ inclus) ; véhicule surdimensionné sur place 154 $ (frais de 4 $ inclus). Achat anticipé : standard 38 $ (frais de 3 $ inclus) ; surdimensionné 128 $ (frais de 3 $ inclus) — disponible jusqu'à 23h45 la veille de l'événement. Aucun paiement en espèces accepté sur place.",
     "以 UCLA 橄榄球赛（内布拉斯加对阵 UCLA，2025 年 11 月 8 日）为例：现场购票普通车辆 $44（含 $4 技术服务费）；超大型车辆现场购票 $154（含 $4 服务费）。提前购买：普通车辆 $38（含 $3 服务费）；超大型车辆 $128（含 $3 服务费）——可在活动前一晚 11:45 PM 前购买。现场不接受现金支付。"),
    ("Rose Bowl Stadium", "parking", 0, "pricing_basis",
     "Fútbol americano de UCLA, 11/8/2025 — precios no confirmados para los Juegos Olímpicos LA28",
     "Football américain UCLA, 11/8/2025 — tarifs non confirmés pour les Jeux Olympiques LA28",
     "UCLA 橄榄球赛，2025 年 11 月 8 日——尚未确认为 LA28 奥运会正式价格"),
    ("Rose Bowl Stadium", "parking", 0, "surge_notes",
     "Los precios son específicos de cada evento y se establecen por evento (se confirmó una tarifa diferente para el portal de estacionamiento de eventos del público general frente al portal de fútbol americano de UCLA).",
     "Les tarifs sont spécifiques à chaque événement et fixés par événement (tarif différent confirmé pour le portail de stationnement événementiel grand public par rapport au portail football américain UCLA).",
     "价格因活动而异，按每场活动单独设定（已确认公众活动停车门户与 UCLA 橄榄球门户的费率不同）。"),
    ("Rose Bowl Stadium", "parking", 0, "notes",
     "Lote más cercano a la entrada del recinto: Lote D, B, F. Para el partido de UCLA del 11/8/2025: el estacionamiento abrió a las 12:00 PM para un inicio a las 6:00 PM (6 horas antes); todos los vehículos deben desalojar no más de 90 minutos después de que termine el partido. Nota general: se restringe a los asistentes el ingreso a las vías residenciales circundantes.",
     "Parking le plus proche de l'entrée du site : Parking D, B, F. Pour le match UCLA du 11/8/2025 : le parking a ouvert à 12h00 pour un coup d'envoi à 18h00 (6 heures avant) ; tous les véhicules doivent quitter les lieux au plus tard 90 minutes après la fin du match. Remarque générale : les spectateurs ne sont pas autorisés à emprunter les routes résidentielles environnantes.",
     "距场馆入口最近的停车场：D、B、F 停车场。以 2025 年 11 月 8 日 UCLA 比赛为例：停车场于中午 12:00 开放，比赛于晚上 6:00 开球（提前 6 小时）；所有车辆须在比赛结束后 90 分钟内离场。一般说明：观众不得进入周边居民区道路。"),
    ("Rose Bowl Stadium", "curb", 0, "rideshare_zone_description",
     "Varía según el evento — para los partidos de fútbol americano de UCLA y la mayoría de los conciertos (Guns N' Roses, Oasis, Rüfüs du Sol, etc.), los servicios de viajes compartidos/taxis deben recoger y dejar pasajeros en el área de Old Town Pasadena (no en el propio estadio). En un concierto (Karol G, 2023) se permitió la entrega en el Lote H en su lugar. Para el 109.º Rose Bowl Game, no se permitió ninguna entrega de viajes compartidos/taxis en el estadio.",
     "Varie selon l'événement — pour les matchs de football américain UCLA et la plupart des concerts (Guns N' Roses, Oasis, Rüfüs du Sol, etc.), les services de covoiturage/taxis doivent déposer et prendre en charge les passagers dans le quartier d'Old Town Pasadena (pas au stade lui-même). Un concert (Karol G, 2023) a permis la dépose au Parking H à la place. Pour le 109e Rose Bowl Game, aucune dépose de covoiturage/taxi n'était autorisée au stade.",
     "因活动而异——对于 UCLA 橄榄球赛和大多数演唱会（Guns N' Roses、Oasis、rüfüs du sol 等），网约车/出租车须在 Old Town Pasadena 区域（而非体育场本身）上下客。有一场演唱会（Karol G，2023 年）改为允许在 H 停车场下客。第 109 届玫瑰碗赛事期间，体育场完全不允许网约车/出租车上下客。"),
    ("Rose Bowl Stadium", "curb", 0, "rideshare_zone_open_window",
     "Depende de la hora del evento", "Dépend de l'heure de l'événement", "取决于活动时间"),
    ("Rose Bowl Stadium", "curb", 0, "taxi_accessible_zone",
     "La misma zona de Old Town Pasadena que los viajes compartidos para la mayoría de los eventos",
     "Même zone d'Old Town Pasadena que le covoiturage pour la plupart des événements",
     "对于大多数活动，与网约车共用同一 Old Town Pasadena 区域"),
    ("Rose Bowl Stadium", "curb", 0, "curbside_restrictions",
     "El estadio se encuentra en una zona residencial; los asistentes deben seguir las indicaciones del personal de control de tráfico y tienen restringido el ingreso a las vías residenciales cercanas al estadio",
     "Le stade se trouve dans une zone résidentielle ; les spectateurs doivent suivre les instructions du personnel de contrôle de la circulation et ne sont pas autorisés à emprunter les routes résidentielles à proximité du stade",
     "体育场位于居民区；观众须听从交通管制人员指挥，不得进入体育场附近的居民区道路"),
    ("Rose Bowl Stadium", "transit", 0, "gbfs_dock_description",
     "No hay Metro Bike Share ni patinetes en Pasadena",
     "Pas de Metro Bike Share ni de trottinettes à Pasadena",
     "帕萨迪纳（Pasadena）没有 Metro Bike Share 或滑板车"),
    ("Rose Bowl Stadium", "transit", 0, "transit_notes",
     "Tiempo a pie desde la estación: 42 min. Parada de autobús más cercana: Colorado y Arroyo. Tiempo a pie desde la parada de autobús: 27 min. Carril/ruta para bicicletas cerca: Sí — se cita el sendero Arroyo Seco como una ruta transitable a pie/en bicicleta desde la estación Memorial Park. El transporte gratuito Foothill Transit Rose Bowl Shuttle circula desde el Lote B de estacionamiento de Parsons (Old Town, cerca de la estación Memorial Park) cada 5–7 minutos para eventos seleccionados, pero la disponibilidad varía según el evento — confirmar con el organizador. Metro recomienda llegar a la estación Memorial Park al menos 90 minutos antes de la hora de inicio del evento para tomar el transporte y evitar aglomeraciones. El estacionamiento en Parsons cuesta $27.50 o $30. Los pasajeros de Metrolink deben transbordar a la Línea A en Union Station.",
     "Temps de marche depuis la station : 42 min. Arrêt de bus le plus proche : Colorado et Arroyo. Temps de marche depuis l'arrêt de bus : 27 min. Piste/voie cyclable à proximité : Oui — le sentier Arroyo Seco est cité comme itinéraire praticable à pied/à vélo depuis la station Memorial Park. La navette gratuite Foothill Transit Rose Bowl circule depuis le Parking B de Parsons (Old Town, près de la station Memorial Park) toutes les 5 à 7 minutes pour certains événements, mais la disponibilité varie selon l'événement — à confirmer auprès de l'organisateur. Metro recommande d'arriver à la station Memorial Park au moins 90 minutes avant le début de l'événement pour prendre la navette et éviter la foule. Le stationnement chez Parsons coûte 27,50 $ ou 30 $. Les usagers de Metrolink doivent correspondre avec la ligne A à Union Station.",
     "从车站步行时间：42 分钟。最近的公交车站：Colorado 与 Arroyo。从公交车站步行时间：27 分钟。附近自行车道/路径：有——Arroyo Seco 步道被列为从 Memorial Park 站可步行/骑行到达的路线。免费的 Foothill Transit Rose Bowl 接驳车从 Parsons 停车场 B 区（Old Town，靠近 Memorial Park 站）出发，部分活动期间每 5–7 分钟一班，但具体班次视活动而定——请与主办方确认。Metro 建议至少提前 90 分钟抵达 Memorial Park 站，以搭乘接驳车并避开人群。在 Parsons 停车费用为 $27.50 或 $30。Metrolink 乘客须在 Union Station 换乘 A 线。"),
    ("Rose Bowl Stadium", "congestion", 0, "arrival_notes",
     "Para el partido de UCLA del 11/8/2025: el estacionamiento abrió 6 horas antes del inicio (12:00 PM para las 6:00 PM), el transporte comenzó 3 horas antes, las puertas abrieron 1.5 horas antes. Por separado, Metro recomienda llegar a la estación Memorial Park al menos 90 minutos antes de la hora de inicio del evento.",
     "Pour le match UCLA du 11/8/2025 : le parking a ouvert 6 heures avant le coup d'envoi (12h00 pour 18h00), la navette a démarré 3 heures avant, les portes ont ouvert 1,5 heure avant. Par ailleurs, Metro recommande d'arriver à la station Memorial Park au moins 90 minutes avant le début de l'événement.",
     "以 2025 年 11 月 8 日 UCLA 比赛为例：停车场在开球前 6 小时开放（中午 12:00 对应晚上 6:00 开球），接驳车在开球前 3 小时启动，大门在开球前 1.5 小时开放。此外，Metro 建议至少提前 90 分钟抵达 Memorial Park 站。"),
    ("Rose Bowl Stadium", "congestion", 0, "high_congestion_entry_roads",
     "Las autopistas 134, 110, 210 y Fair Oaks Ave/Linda Vista Ave/Salvia Canyon",
     "Autoroutes 134, 110, 210 et Fair Oaks Ave/Linda Vista Ave/Salvia Canyon",
     "134、110、210 号高速公路，以及 Fair Oaks Ave/Linda Vista Ave/Salvia Canyon"),
    ("Rose Bowl Stadium", "congestion", 0, "general_tdm_notes",
     "El servicio de transporte gratuito entre Old Town Pasadena (Parsons) y el estadio es la principal herramienta de gestión de la demanda de transporte (TDM); a los asistentes se les indica evitar la entrega de viajes compartidos en el propio estadio para la mayoría de los eventos importantes.",
     "Le service de navette gratuite entre Old Town Pasadena (Parsons) et le stade est le principal outil de gestion de la demande de transport (TDM) ; les spectateurs sont dirigés loin de la dépose de covoiturage au stade lui-même pour la plupart des grands événements.",
     "Old Town Pasadena（Parsons）与体育场之间的免费接驳车服务是主要的出行需求管理（TDM）手段；在大多数重要活动中，观众被引导避开体育场本身的网约车上下客点。"),
]

_ENTITY_MODEL = {
    "parking": (ParkingOption, "parking_option"),
    "transit": (TransitAccess, "transit_access"),
}


def _resolve_entity_id(session: Session, venue: Venue, entity: str, idx: int) -> tuple[str, int]:
    """Map (entity kind, list position) to (entity_type, real DB row id)."""
    if entity == "venue":
        return "venue", venue.id
    if entity == "congestion":
        if not venue.congestion_tdm:
            raise ValueError(f"{venue.name} has no congestion_tdm row")
        return "congestion_tdm", venue.congestion_tdm.id
    if entity == "curb":
        rows = sorted(venue.curb_dropoffs, key=lambda r: r.id)
        return "curb_dropoff", rows[idx].id
    model, entity_type = _ENTITY_MODEL[entity]
    rows = sorted(
        session.query(model).filter(model.venue_id == venue.id).all(),
        key=lambda r: r.id,
    )
    return entity_type, rows[idx].id


def seed(session: Session) -> None:
    venues_by_name = {v.name: v for v in session.query(Venue).all()}
    created = 0
    skipped = 0
    for venue_name, entity, idx, field, es, fr, zh in TRANSLATIONS:
        venue = venues_by_name.get(venue_name)
        if not venue:
            print(f"Venue not found, skipping: {venue_name}")
            continue
        entity_type, entity_id = _resolve_entity_id(session, venue, entity, idx)
        for language, value in (("es", es), ("fr", fr), ("zh-Hans", zh)):
            exists = (
                session.query(VenueTranslation)
                .filter(
                    VenueTranslation.entity_type == entity_type,
                    VenueTranslation.entity_id == entity_id,
                    VenueTranslation.field == field,
                    VenueTranslation.language == language,
                )
                .first()
            )
            if exists:
                skipped += 1
                continue
            session.add(VenueTranslation(
                venue_id=venue.id,
                entity_type=entity_type,
                entity_id=entity_id,
                field=field,
                language=language,
                value=value,
                reviewed=False,
            ))
            created += 1
    session.commit()
    print(f"Seeded {created} venue translations ({skipped} already present).")


if __name__ == "__main__":
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as _Session

    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    with _Session(engine) as session:
        seed(session)
