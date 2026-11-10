# K?t qu? tri?n khai ph? l?c ? 03/11/2026

38 m?c ki?m k? g?c v? 4 ngu?n s?a ??i b? sung ?? ???c thu th?p. C? 38 ngu?n t?i ?? theo metadata v? 4 ngu?n t?i m?t ph?n. File v?n l?u tr?n m?y; ch?a upload R2.

Nh?n di?n 208 ph?n ph? l?c/bi?u m?u, g?m {'form': 136, 'reference': 40, 'unknown': 32}. ??y l? s? ph?n nh?n di?n, ch?a ph?i s? ph? l?c ?? x?c minh: 95 ph?n ?ang ch? r? so?t.

Qdrant: 98 chunk ph? l?c; fingerprint x?c nh?n 1.481 point c? s? (payload v? vector) kh?ng thay ??i. Ch?y l?i kh?ng embedding th?m n?i dung kh?ng ??i.

Neo4j: ?? n?p v? x?c minh 300 node, 1161 c?nh; ch?y l?n hai kh?ng nh?n ??i. T?ng dataset sau n?p: 12044 node, 34518 c?nh. Fingerprint node/c?nh g?c gi? nguy?n.

SHACL h?p nh?t: ??t. TT 09/2020 t?ch ??ng I?V; ?i?u 8 ? II, ?i?u 9 ? III?IV, ?i?u 10 ? V. TT 19/2016 nh?n di?n 18 ph? l?c bi?u m?u. N? 135/2020 nh?n di?n I?III. N? 97/2022 nh?n di?n I?II.

51 ki?m th? ?? qua ? l?n ch?y t?ch h?p. Notebook ?? ch?y kernel m?i v?i m?ng t?t m?c ??nh. API ?? ki?m tra lu?ng chat th?t ? xem tr?ch d?n ? t?i file ??ng hash. Giao di?n ch?a ???c ki?m tra tr?c quan do kh?ng c? tr?nh duy?t k?t n?i trong phi?n.

## Ngu?n ch?a tr?ch xu?t ???c ph? l?c

| V?n b?n | Tr?ng th?i t?i | Nh?n c?n thi?u | Chi ti?t |
|---|---|---|---|
| 09/2016/TTLT-BLĐTBXH-BTC | downloaded |  | VanBanGoc_TT09BLDTBXH-BTC_2.pdf: ValueError: Scanned PDF needs an explicit --ocr extraction run |
| 11/2017/TT-BLĐTBXH | downloaded |  | VanBanGoc_TT 11 BLDTBXH.pdf: ValueError: Scanned PDF needs an explicit --ocr extraction run |
| 152/2020/NĐ-CP | downloaded | 1, 2 | VanBanGoc_nghi-dinh-152-2020-nd-cp-ve-nguoi-lao-dong-nuoc-ngoai-lam-viec-tai-viet-nam.pdf: ValueError: Scanned PDF needs an explicit --ocr extraction run |
| 16/2022/TT-BLĐTBXH | downloaded |  | Ch?a nh?n di?n ???c ti?u ??/n?i dung ph? l?c trong c?c file ?? l?y; c?n ??i chi?u ngu?n ho?c b?n s?a ??i. |
| 23/2021/NĐ-CP | downloaded | 1, 2 | VanBanGoc_23.signed.pdf: ValueError: Scanned PDF needs an explicit --ocr extraction run |
| 28/2015/NĐ-CP | downloaded |  | Ch?a nh?n di?n ???c ti?u ??/n?i dung ph? l?c trong c?c file ?? l?y; c?n ??i chi?u ngu?n ho?c b?n s?a ??i. |
| 29/2021/TT-BYT | downloaded | 4, 5 | Ch?a nh?n di?n ???c ti?u ??/n?i dung ph? l?c trong c?c file ?? l?y; c?n ??i chi?u ngu?n ho?c b?n s?a ??i. |
| 61/2015/NĐ-CP | downloaded |  | Ch?a nh?n di?n ???c ti?u ??/n?i dung ph? l?c trong c?c file ?? l?y; c?n ??i chi?u ngu?n ho?c b?n s?a ??i. |
| 24/2017/TT-BLĐTBXH | downloaded |  | VanBanGoc_TT 24 2017 BLÐTBXH.pdf: ValueError: Scanned PDF needs an explicit --ocr extraction run |
| 74/2019/NĐ-CP | downloaded |  | VanBanGoc_74.signed.pdf: ValueError: Scanned PDF needs an explicit --ocr extraction run |

N? 28/2015 c? ngu?n b? sung N? 61/2020: ?? l?y ???c g?i M?u 01?05 t? PDF C?ng b?o. Vi?c ch?a nh?n di?n ph? l?c trong b?n g?c kh?ng ??ng ngh?a ch?a c? to?n b? m?u li?n quan.

## Ngu?n t?i ch?a ??

| V?n b?n | L?i c?n ghi nh?n |
|---|---|
| 18/2021/TT-BLĐTBXH | Thong tu 18.2021.TT-BLĐTBXH.docx: HTTPError: 404 Client Error: Not Found for url: https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/minio/buckets/vbpl/153297/Thong%20tu%2018.2021.TT-BL%C4%90TBXH.docx/download |
| 40/2021/QĐ-TTg | VanBanGoc_quyet-dinh-40-2021-qd-ttg-thu-tuong-chinh-phu.pdf: ValueError: Download is not the expected binary format |
| 45/2015/TT-BLĐTBXH | 45.2015.TT.BLĐTBXH và Phụ lục.doc: HTTPError: 404 Client Error: Not Found for url: https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/minio/buckets/vbpl/94582/45.2015.TT.BL%C4%90TBXH%20v%C3%A0%20Ph%E1%BB%A5%20l%E1%BB% |
| 61/2020/NĐ-CP | 61_2020_ND-CP_393789.doc: HTTPError: 404 Client Error: Not Found for url: https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/minio/buckets/vbpl/142819/61_2020_ND-CP_393789.doc/download; Alternative source: SSLError: HTTPSConnectionPool(host='g7.cdnchinhphu.vn', port=443): Max retries exceeded with url: /api/download/stream?Url=tm-8mq6BhNw0NbrKRhTDAQWsKg3tuqaY0aWypnY78U6M2BY68Ekp0Gvvr483flbR505 |

## ?nh x? graph c?n b? sung

C? m?t d?n chi?u ch?a t?o c?nh: `02-2023-tt-byt:pl35` ? ?i?u 8 v? ?i?u ngu?n ch?a c? trong projection c? s?. Chi ti?t ? `graph_report.json`; kh?ng t?o ?i?u gi? ?? ho?n t?t ?nh x?.

## Ch?y v? r? so?t ti?p

Xem [APPENDICES.md](../../APPENDICES.md) ?? ch?y API, notebook, n?p b? sung v? s?a b?ng r? so?t. Quy?t ??nh ph?n lo?i/phi?n b?n ? `review_overrides.csv`; file local ghi ?? ? `data/raw/appendix/review.csv`. Ch?a c? b??c t? ??ng chuy?n file l?n Cloudflare.
