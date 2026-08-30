"""
industry_chain/
產業鏈知識圖譜與輪動模型（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md）。

比照 backend/ai/ 在既有系統之上新增自成一格套件的既有前例（ADR-IC-02）：跨標的批次運算
（CCF、BFS）與圖譜資料存取獨立於 strategies/ 之外，因為 @condition 簽章是單一標的單一
時點，表達不了跨標的比較。

本批次（第一批交付）只有 config.py（YAML 骨架 + 功能旗標）；LLM 萃取（extractor.py／
validator.py／schema.py）、BFS 與外溢篩選（graph.py／spillover.py）留待後續批次。
"""
