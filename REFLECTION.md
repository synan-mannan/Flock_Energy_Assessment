# Reflection

1. **What assumptions did you make?** I treated the observed portal response shapes as the current contract. The client uses a 401 or 403 as a signal to refresh its local session once; it does not assume a particular cookie/token format. Coordinates are clearly numeric, while energy readings and timestamps remain strings because their precise meaning and timezone were not confirmed.

2. **Which part was most difficult, and how did you get unstuck?** A direct form POST failed with 403 although the browser form had no hidden CSRF field. Comparing requests showed that same-origin `Origin` and `Referer` headers were needed. The authenticated browser requests then provided the actual API paths and response shapes; the unsigned export request returned `signature_invalid`, so I left export out.

3. **If you had another day, what would you improve?** I would add integration tests against a controlled portal fixture, investigate session expiry more deeply, define a data-freshness strategy, and add structured operational logging without logging credentials or session values.

4. **What mistake did you make?** I tried calling the export endpoint directly without its signing flow. The observed `signature_invalid` response made clear that the endpoint alone was not enough, so I stopped rather than inventing the missing protocol.

5. **What would you criticize in your own submission?** The one-shot recovery is intentionally simple and does not coordinate concurrent requests that expire at the same time. Detail lookup depends on an exact search result because no separate verified meter-detail endpoint was found. The automated tests mock portal responses, so they verify our behavior but not future portal changes.
