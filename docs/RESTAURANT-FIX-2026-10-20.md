# Sakura Mobile 0.3.10 — restaurant request routing

The exact request “suggest me a good restaurant” previously bypassed the native map lookup because it lacked an explicit “near me” phrase. It went to the generic cloud chat prompt instead.

- Suggest/recommend/find/check/show restaurant and cafe requests now trigger current-location/map lookup without requiring “near me”. Recipe/business-definition questions stay ordinary chat.
- Added nearby named restaurant matching for common chains and explicit names such as “find Blue Moon restaurant” or “restaurant called Blue Moon”. Cache entries include the requested name, so generic and named requests cannot return each other's cached listings.
- Every successful/empty listing response includes a Search in Maps button retaining the selected name. The same query is retained on network failure. Lists cover about 3 km from the fresh location; coverage depends on OpenStreetMap.
- Maps can show reviews and wider search results. Sakura does not claim verified ratings, opening hours, availability or “best restaurant” rankings from OSM data.
- Background wake requests that need fresh location still ask the user to open Sakura; no background location permission was added.

Validation: actual Java intent/name regression cases include the screenshot wording, generic cafe recommendation, chain and arbitrary name extraction, generic recommendation exclusion from name filtering and non-search recipe/business questions. Android compilation/R8/signature/archive checks passed; packaged WebView test verifies place buttons and exact named Maps query. Physical GPS and upstream live restaurant availability remain device/service dependent.

Install over existing Sakura Mobile. Name, package and signing identity unchanged; no models bundled.
SHA256: e502fb9f440cc5de03796991040e031504d54e1d51e655be1cf3435a0d8343fa
