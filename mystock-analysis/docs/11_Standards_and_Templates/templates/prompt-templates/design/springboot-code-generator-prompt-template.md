# SpringBoot 程式生成 Prompt Library

## 📋 文件說明
本文件提供thmcpa達航船員考評系統專用的SpringBoot程式生成prompt範本，專門用於根據DDL SQL語句快速生成Entity、Repository、Service、Controller四層架構的完整程式碼。

**注意**: 詳細的程式設計規範請參考 [Spring Boot程式設計規範文件](../../4.document-templates/standards/Spring-Boot程式設計規範文件.md)

## 🏷️ Prompt 分類
- **程式生成**: 根據DDL生成完整SpringBoot程式
- **Entity設計**: JPA實體類生成與優化
- **Repository實作**: 資料存取層程式生成
- **Service開發**: 業務邏輯層程式生成
- **Controller開發**: RESTful API控制器生成
- **程式優化**: 代碼重構與效能優化
- **測試**: 單元測試與整合測試生成

## 📊 Prompt 清單表

| ID | 類別 | Prompt名稱 | 用途 | 更新日期 | 使用頻率 |
|----|------|------------|------|----------|----------|
| P001 | 程式生成 | SpringBoot四層架構生成器 | 根據DDL生成Entity、Repository、Service、Controller | 2024-01-15 | ⭐⭐⭐⭐⭐ |
| P002 | Entity設計 | JPA實體類優化生成 | 生成符合規範的JPA實體類 | 待新增 | - |
| P003 | Repository實作 | 自訂查詢Repository生成 | 生成包含業務查詢的Repository | 待新增 | - |
| P004 | Service開發 | 業務邏輯Service生成 | 生成完整的Service層程式 | 待新增 | - |
| P005 | Controller開發 | RESTful API完整生成 | 生成符合RESTful規範的Controller | 待新增 | - |
| P006 | 程式優化 | 程式碼重構與優化 | 優化現有程式碼結構與效能 | 待新增 | - |
| P007 | 測試 | Controller單元測試生成器 | 依照指定Controller生成完整單元測試 | 2024-01-15 | ⭐⭐⭐⭐ |

---

## 📝 Prompt 詳細內容

### 🆔 P001 - SpringBoot四層架構生成器

**分類**: 程式生成  
**優先級**: 高  
**適用場景**: 需要根據DDL SQL語句快速生成完整SpringBoot四層架構程式時使用

#### Prompt 內容:
```
你是資深的SpringBoot後端工程師。
請根據以下DDL SQL語句，為thmcpa達航船員考評系統生成完整的SpringBoot 3四層架構程式。

**系統資訊**:
- 專案名稱：thmcpa (達航船員考評系統)
- 架構：前後端分離
- 技術棧：SpringBoot 3 + PrimeVue 3
- 執行環境：Docker

**DDL輸入**:
[DDL_SQL_PLACEHOLDER]

**生成要求** (請參考Spring Boot程式設計規範文件):

1. **Entity層**: ShipEntity 繼承 AuditableEntity，包含完整的JPA註解和驗證
2. **Repository層**: ShipRepository 提供基本CRUD和自訂查詢方法
3. **Service層**: ShipService 包含業務邏輯、事務管理和資料轉換
4. **Controller層**: ShipController 提供RESTful API端點
5. **DTO層**: 請求和回應的資料傳輸物件
6. **Mapper層**: 使用MapStruct進行Entity和DTO轉換
7. **異常處理**: 自訂業務異常和統一回應格式

**快速參考 - 四層架構結構**:

Entity結構：
@Entity
@Table(name = "table_name")
@Data
@ToString(exclude = {"sensitiveField"})
public class EntityName extends AuditableEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(name = "field_name", nullable = false, length = 50)
    @NotBlank(message = "欄位不能為空")
    private String fieldName;
    // 其他業務欄位...
}

Repository結構：
@Repository
public interface EntityNameRepository extends JpaRepository<EntityName, Long> {
    Optional<EntityName> findByFieldName(String fieldName);
    Page<EntityName> findByStatusOrderByCreateTimestampDesc(Integer status, Pageable pageable);
    
    @Query("SELECT e FROM EntityName e WHERE e.fieldName LIKE %:keyword%")
    List<EntityName> findByKeyword(@Param("keyword") String keyword);
}

Service結構：
@Service
@Transactional
@Slf4j
public class EntityNameService {
    
    private final EntityNameRepository repository;
    
    public EntityNameService(EntityNameRepository repository) {
        this.repository = repository;
    }
    
    @Transactional(readOnly = true)
    public Page<EntityName> getAll(int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return repository.findAll(pageable);
    }
    
    public EntityName create(EntityName entity) {
        // 業務邏輯驗證
        validateEntity(entity);
        return repository.save(entity);
    }
    
    public EntityName update(Long id, EntityName entity) {
        EntityName existing = repository.findById(id)
            .orElseThrow(() -> new BusinessException("資料不存在"));
        // 更新邏輯...
        return repository.save(existing);
    }
    
    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw new BusinessException("資料不存在");
        }
        repository.deleteById(id);
    }
    
    private void validateEntity(EntityName entity) {
        // 業務邏輯驗證
    }
}

Controller結構：
@RestController
@RequestMapping("/api/v1/entity-names")
@CrossOrigin(origins = "*")
@Validated
@Tag(name = "EntityName Management", description = "EntityName管理API")
public class EntityNameController {
    
    private final EntityNameService service;
    
    public EntityNameController(EntityNameService service) {
        this.service = service;
    }
    
    @GetMapping
    @Operation(summary = "查詢列表", description = "支援分頁查詢")
    public ResponseEntity<ApiResponse<Page<EntityName>>> getAll(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        Page<EntityName> result = service.getAll(page, size);
        return ResponseEntity.ok(ApiResponse.success(result));
    }
    
    @GetMapping("/{id}")
    @Operation(summary = "查詢單筆", description = "根據ID查詢")
    public ResponseEntity<ApiResponse<EntityName>> getById(@PathVariable Long id) {
        EntityName result = service.getById(id);
        return ResponseEntity.ok(ApiResponse.success(result));
    }
    
    @PostMapping
    @Operation(summary = "新增", description = "建立新記錄")
    public ResponseEntity<ApiResponse<EntityName>> create(@RequestBody @Valid EntityName entity) {
        EntityName result = service.create(entity);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(result));
    }
    
    @PutMapping("/{id}")
    @Operation(summary = "更新", description = "更新記錄")
    public ResponseEntity<ApiResponse<EntityName>> update(
            @PathVariable Long id, 
            @RequestBody @Valid EntityName entity) {
        EntityName result = service.update(id, entity);
        return ResponseEntity.ok(ApiResponse.success(result));
    }
    
    @DeleteMapping("/{id}")
    @Operation(summary = "刪除", description = "刪除記錄")
    public ResponseEntity<ApiResponse<Void>> delete(@PathVariable Long id) {
        service.delete(id);
        return ResponseEntity.ok(ApiResponse.success(null));
    }
}

請生成完整、可執行的四層架構程式碼，並確保符合thmcpa專案的設計規範。
```

#### 使用說明:
- 將DDL SQL語句貼入指定位置
- 生成的程式碼將遵循專案設計規範
- 包含完整的Entity、Repository、Service、Controller四層
- 詳細規範請參考 [Spring Boot程式設計規範文件](../../4.document-templates/standards/Spring-Boot程式設計規範文件.md)
- Service層包含業務邏輯驗證和異常處理

#### 預期輸出:
- 符合規範的SpringBoot 3 Entity類別
- 包含自訂查詢的Repository介面
- 完整業務邏輯的Service類別
- 符合RESTful規範的Controller類別
- 適當的註解和異常處理機制

#### 相關標籤:
`#SpringBoot3` `#JPA` `#Entity` `#Repository` `#Service` `#Controller` `#DDL` `#四層架構`

---

### 🆔 P005 - RESTful API完整生成器

**分類**: Controller開發  
**優先級**: 高  
**適用場景**: 根據需求文件生成符合RESTful規範的完整Controller程式時使用

#### Prompt 內容:
```
你是資深的SpringBoot後端工程師。
請根據以下需求文件，為thmcpa達航船員考評系統生成符合RESTful規範的完整Controller程式。

**系統資訊**:
- 專案名稱：thmcpa (達航船員考評系統)
- 架構：前後端分離
- 技術棧：SpringBoot 3 + PrimeVue 3
- 執行環境：Docker

**📋 需求文件輸入**:
```
模組名稱：[MODULE_NAME]
功能描述：[MODULE_DESCRIPTION]

API端點需求：
1. [API_ENDPOINT_1] - [DESCRIPTION_1]
2. [API_ENDPOINT_2] - [DESCRIPTION_2]
3. [API_ENDPOINT_3] - [DESCRIPTION_3]
...

業務規則：
- [BUSINESS_RULE_1]
- [BUSINESS_RULE_2]
- [BUSINESS_RULE_3]
...

驗證需求：
- [VALIDATION_REQUIREMENT_1]
- [VALIDATION_REQUIREMENT_2]
- [VALIDATION_REQUIREMENT_3]
...

權限控制：
- [PERMISSION_RULE_1]
- [PERMISSION_RULE_2]
...

回應格式要求：
- [RESPONSE_FORMAT_1]
- [RESPONSE_FORMAT_2]
...
```

**🎯 生成要求** (請遵循Spring Boot程式設計規範):

**1. Controller設計要求**:
- 使用RESTful API設計原則
- 路徑格式：/api/v1/[resource-name]
- 包含完整CRUD操作（GET、POST、PUT、DELETE）
- 支援分頁、排序、篩選查詢
- 統一的API回應格式

**2. HTTP方法對應**:
```
GET    /api/v1/[resource]           - 查詢列表（支援分頁、排序、篩選）
GET    /api/v1/[resource]/{id}      - 查詢單筆資料
POST   /api/v1/[resource]           - 新增資料
PUT    /api/v1/[resource]/{id}      - 更新資料
DELETE /api/v1/[resource]/{id}      - 刪除資料
GET    /api/v1/[resource]/search    - 條件搜尋
POST   /api/v1/[resource]/batch     - 批次操作
GET    /api/v1/[resource]/export    - 匯出功能
```

**3. 必要註解和功能**:
- @RestController, @RequestMapping, @CrossOrigin
- @Operation, @ApiResponse (Swagger文件)
- @Valid, @Validated (資料驗證)
- @PathVariable, @RequestParam, @RequestBody
- 完整的異常處理機制
- 統一的回應格式 (ApiResponse)

**4. Controller結構範本**:
```java
@RestController
@RequestMapping("/api/v1/[resource-names]")
@CrossOrigin(origins = "*")
@Validated
@Tag(name = "[Resource] Management", description = "[Resource]管理API")
@Slf4j
public class [Resource]Controller {
    
    private final [Resource]Service service;
    
    public [Resource]Controller([Resource]Service service) {
        this.service = service;
    }
    
    /**
     * 查詢列表（分頁）
     */
    @GetMapping
    @Operation(summary = "查詢[Resource]列表", description = "支援分頁、排序、篩選查詢")
    public ResponseEntity<ApiResponse<Page<[Resource]ResponseDTO>>> getAll(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size,
            @RequestParam(defaultValue = "id") String sort,
            @RequestParam(defaultValue = "DESC") String direction,
            @RequestParam(required = false) String keyword) {
        
        log.debug("查詢[Resource]列表: page={}, size={}, sort={}, direction={}, keyword={}", 
                 page, size, sort, direction, keyword);
        
        Page<[Resource]ResponseDTO> result = service.getAll(page, size, sort, direction, keyword);
        return ResponseEntity.ok(ApiResponse.success(result));
    }
    
    /**
     * 查詢單筆資料
     */
    @GetMapping("/{id}")
    @Operation(summary = "查詢[Resource]詳情", description = "根據ID查詢單筆[Resource]資料")
    public ResponseEntity<ApiResponse<[Resource]ResponseDTO>> getById(
            @PathVariable @NotNull @Min(1) Long id) {
        
        log.debug("查詢[Resource]詳情: id={}", id);
        
        [Resource]ResponseDTO result = service.getById(id);
        return ResponseEntity.ok(ApiResponse.success(result));
    }
    
    /**
     * 新增資料
     */
    @PostMapping
    @Operation(summary = "新增[Resource]", description = "建立新的[Resource]記錄")
    public ResponseEntity<ApiResponse<[Resource]ResponseDTO>> create(
            @RequestBody @Validated([Resource]RequestDTO.Create.class) [Resource]RequestDTO request) {
        
        log.info("新增[Resource]: {}", request);
        
        [Resource]ResponseDTO result = service.create(request);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(result));
    }
    
    /**
     * 更新資料
     */
    @PutMapping("/{id}")
    @Operation(summary = "更新[Resource]", description = "更新[Resource]資料")
    public ResponseEntity<ApiResponse<[Resource]ResponseDTO>> update(
            @PathVariable @NotNull @Min(1) Long id,
            @RequestBody @Validated([Resource]RequestDTO.Update.class) [Resource]RequestDTO request) {
        
        log.info("更新[Resource]: id={}, request={}", id, request);
        
        [Resource]ResponseDTO result = service.update(id, request);
        return ResponseEntity.ok(ApiResponse.success(result));
    }
    
    /**
     * 刪除資料
     */
    @DeleteMapping("/{id}")
    @Operation(summary = "刪除[Resource]", description = "刪除[Resource]記錄")
    public ResponseEntity<ApiResponse<Void>> delete(
            @PathVariable @NotNull @Min(1) Long id) {
        
        log.info("刪除[Resource]: id={}", id);
        
        service.delete(id);
        return ResponseEntity.ok(ApiResponse.success(null));
    }
    
    /**
     * 條件搜尋
     */
    @GetMapping("/search")
    @Operation(summary = "條件搜尋[Resource]", description = "根據多條件搜尋[Resource]")
    public ResponseEntity<ApiResponse<Page<[Resource]ResponseDTO>>> search(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        
        log.debug("條件搜尋[Resource]: keyword={}, status={}, startDate={}, endDate={}", 
                 keyword, status, startDate, endDate);
        
        Page<[Resource]ResponseDTO> result = service.search(keyword, status, startDate, endDate, page, size);
        return ResponseEntity.ok(ApiResponse.success(result));
    }
    
    /**
     * 批次操作
     */
    @PostMapping("/batch")
    @Operation(summary = "批次操作[Resource]", description = "批次新增、更新或刪除[Resource]")
    public ResponseEntity<ApiResponse<List<[Resource]ResponseDTO>>> batchOperation(
            @RequestBody @Valid [Resource]BatchRequestDTO request) {
        
        log.info("批次操作[Resource]: operation={}, count={}", 
                request.getOperation(), request.getData().size());
        
        List<[Resource]ResponseDTO> result = service.batchOperation(request);
        return ResponseEntity.ok(ApiResponse.success(result));
    }
    
    /**
     * 匯出功能
     */
    @GetMapping("/export")
    @Operation(summary = "匯出[Resource]", description = "匯出[Resource]資料為Excel檔案")
    public ResponseEntity<Resource> export(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate endDate) {
        
        log.info("匯出[Resource]: keyword={}, status={}, startDate={}, endDate={}", 
                keyword, status, startDate, endDate);
        
        ByteArrayResource resource = service.export(keyword, status, startDate, endDate);
        
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, 
                       "attachment; filename=[resource]_" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss")) + ".xlsx")
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .body(resource);
    }
}
```

**5. 統一回應格式**:
```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ApiResponse<T> {
    private boolean success;
    private String message;
    private T data;
    private String timestamp;
    private String path;
    
    public static <T> ApiResponse<T> success(T data) {
        ApiResponse<T> response = new ApiResponse<>();
        response.setSuccess(true);
        response.setMessage("操作成功");
        response.setData(data);
        response.setTimestamp(LocalDateTime.now().toString());
        return response;
    }
    
    public static <T> ApiResponse<T> error(String message) {
        ApiResponse<T> response = new ApiResponse<>();
        response.setSuccess(false);
        response.setMessage(message);
        response.setTimestamp(LocalDateTime.now().toString());
        return response;
    }
}
```

**📊 輸出要求**:
請生成以下完整程式碼：
1. **Controller類別** - 包含所有API端點實作
2. **RequestDTO/ResponseDTO** - 資料傳輸物件
3. **BatchRequestDTO** - 批次操作請求物件
4. **全域異常處理器** - 統一異常處理機制
5. **API文件範例** - Swagger/OpenAPI使用範例
6. **單元測試範例** - Controller層測試案例

詳細設計規範請參考：[Spring Boot程式設計規範文件](../../4.document-templates/standards/Spring-Boot程式設計規範文件.md)
```

#### 使用說明:
- 將 `[MODULE_NAME]`、`[MODULE_DESCRIPTION]` 等替換為實際內容
- 將API端點需求、業務規則等替換為具體內容
- 將 `[Resource]` 替換為實際的業務資源名稱
- 根據專案需求調整API端點和功能
- 可選擇性移除不需要的功能（如批次操作、匯出等）

#### 預期輸出:
- 生成符合RESTful規範的完整Controller類別
- 包含完整的CRUD操作和額外功能
- 提供統一的API回應格式
- 包含完善的資料驗證和異常處理
- 提供完整的Swagger API文件註解
- 附帶相應的DTO和測試範例

#### 相關標籤:
`#SpringBoot3` `#RESTful` `#Controller` `#API設計` `#需求驅動` `#Swagger`

---

## 🔄 使用指南

### 快速開始
1. 準備DDL SQL語句或需求文件
2. 選擇適合的prompt（P001用於DDL驅動四層架構，P007用於需求驅動）
3. 替換prompt中的placeholder為實際內容
4. 執行生成，獲得符合規範的程式碼
5. 參考 [Spring Boot程式設計規範文件](../../4.document-templates/standards/Spring-Boot程式設計規範文件.md) 進行檢查

### 注意事項
- 生成後需檢查程式碼是否符合專案設計規範
- 複雜的業務邏輯建議額外調整和優化
- 建議配合單元測試一起使用
- 定期更新prompt以符合最新的技術標準

---

## 📈 貢獻指南

歡迎團隊成員貢獻新的prompt或改進現有prompt：

1. **新增Prompt**: 按照標準格式新增到對應分類
2. **更新現有Prompt**: 修改內容並更新日期
3. **回饋使用經驗**: 更新使用頻率評級
4. **分享最佳實務**: 在使用說明中補充實用技巧
5. **提交測試案例**: 提供實際的DDL測試範例

---

## 📚 相關文件

- [Spring Boot程式設計規範文件](../../4.document-templates/standards/Spring-Boot程式設計規範文件.md)
- [Spring Boot資料庫設計規範文件](../../4.document-templates/standards/Spring Boot 資料庫設計規範文件.md)
- [後端開發人員Prompt Library](backend-developer-prompt-template.md)