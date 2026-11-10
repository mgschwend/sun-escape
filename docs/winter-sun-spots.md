# Winter sun escapes from Winterthur — research (2026-11-10)

Question: which places, reachable by train, most often have sun on the winter days when Winterthur doesn't?

## Method

- **Data:** SwissMetNet daily sunshine (`sre000d0`), MeteoSwiss OGD.
- **Period:** winters Nov–Feb, 2012/13 to 2025/26, 1,683 days.
- **Home:** Aadorf/Tänikon (TAE, 539 m, 14 km from Winterthur).
- **Grey home day:** TAE < 1 h of sun. That's **975 days = 58 % of winter days**.
- **Escape:** the station has ≥ 2 h of sun on a grey home day.
- **Train times:** transport.opendata.ch, Thu 12 Nov 2026, leaving Winterthur after 08:30. The last leg (lift, hike) is my estimate.

## Escape odds per station (grey home days)

| Station | Alt. | Escape | Ø sun on grey home days | Train to sunny point |
|---|---|---|---|---|
| Lugano (LUG) | 273 m | 59 % | 3.6 h | 2:19 |
| Biasca (BIA, proxy for Bellinzona) | 278 m | 54 % | 2.3 h | 2:03 (Bellinzona) |
| Davos (DAV) | 1594 m | 44 % | 2.6 h | 2:48 |
| Flims Crap Masegn (CMA) | 2468 m | 43 % | 2.8 h | ~2:50 with lift |
| Andermatt Gütsch (GUE) | 2286 m | 43 % | 2.7 h | ~2:50 with lift |
| **Chur (CHU)** | 556 m | **40 %** | 2.2 h | **1:43**, 1 change |
| Säntis (SAE) | 2501 m | 38 % | 2.8 h | cable car closed until 2027 |
| Pilatus (PIL) | 2105 m | 36 % | 2.4 h | ~2:20 via Alpnachstad cogwheel |
| **Bad Ragaz (RAG)** | 497 m | **33 %** | 1.8 h | **1:32** |
| Napf (NAP) | 1404 m | 26 % | 1.9 h | ~3:20 with hike |
| Hörnli (HOE) | 1133 m | 18 % | 1.3 h | ~1:35 with 1 h hike |
| Uetliberg (UEB) | 854 m | 17 % | 1.1 h | 0:56 |
| Zürich Fluntern (SMA) | 604 m | 8 % | 0.4 h | — |

Full table of 36 stations: `winter_sun.py` output (scratchpad); Generoso, Cimetta and Locarno run 59–62 %.

## What it says

- **The nearby fog-top hills rarely save a grey day.** Hörnli is sunny on 18 % of grey home days, Uetliberg 17 %, Napf 26 %. A grey day is often a real overcast day, not just high fog, so even Säntis is sunny only 38 % of the time.
- **Föhn valleys are the surprise:** Chur (40 %) and Bad Ragaz (33 %) need no lift, are 1.5–1.75 h away, and beat Pilatus and Napf.
- **The south side is the strongest escape:** Bellinzona and Lugano are sunny on 54–59 % of grey home days, but Lugano is just over 2 h away.
- **What a shortlist covers** (at least one spot with ≥ 2 h sun, share of grey home days):

  | Travel budget | Spots | Covered |
  |---|---|---|
  | ≤ 1 h | Uetliberg | 17 % |
  | ≤ 1 h 40 | + Hörnli, Bad Ragaz | 37 % |
  | ≤ 2 h 05 | + Chur, Bellinzona | **59 %** |
  | ≤ 2 h 25 | + Pilatus, Lugano | **76 %** |
  | ≤ 2 h 55 | + Andermatt, Davos, Flims | 79 % |

- **Historically, the nearest sunny spot on a grey home day was:** Bad Ragaz 19 %, Uetliberg 17 %, Bellinzona 15 %, Lugano 15 %, Chur 6 %, others ≤ 2 %, none 20 %.

## Caveats

- **"≥ 2 h over the whole day" doesn't mean the sun is still out when you arrive.** The app still checks the forecast after arrival.
- **Several popular spots have no sunshine station:** Rigi, Stoos, Ebenalp, Hoher Kasten, Flumserberg and Weissenstein. There's no historical evidence for them, so they're left off the list rather than guessed.
- **Bellinzona uses Biasca (20 km up the valley) as a proxy.** Generoso's record is short (292 grey days).
- **Train times come from one weekday sample**, so treat them as approximate; a trip planner like OJP should replace them.

## Decided (2026-11-10)

- **Travel budget ~2 h 25** (replaces the strict 2 h): Uetliberg, Bad Ragaz, Chur, Bellinzona, Pilatus, Lugano. At least one of them is sunny on 76 % of grey home days.
- **UI:** a map with only these spots, coloured by the selected day's forecast, plus one box with the nearest spot that has sun. The trip table goes.
