SELECT known_fields,label,COUNT(*) states,COUNT(DISTINCT case_id) households,AVG(spread) mean_spread FROM observations GROUP BY known_fields,label ORDER BY known_fields,label;
SELECT case_id,COUNT(*) states,MAX(spread) max_spread,MIN(spread) min_spread FROM observations GROUP BY case_id ORDER BY max_spread DESC,case_id;
