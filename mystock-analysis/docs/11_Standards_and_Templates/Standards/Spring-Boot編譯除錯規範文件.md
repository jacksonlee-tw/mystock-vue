# Spring Boot 編譯除錯規範文件

> 本文件定義Spring Boot專案編譯、除錯和問題解決的標準規範，確保開發過程的一致性和問題解決的系統性。

## 📋 文檔資訊

| 項目 | 內容 |
|------|------|
| **文檔版本** | v1.0.0 |
| **最後更新** | 2025-09-21 |
| **適用技術** | Spring Boot 3 + Maven + Java  |
| **資料庫** | MySQL 8.0 / PostgreSQL / Oracle |
| **負責單位** | 技術架構組 |

---

## 🎯 編譯除錯原則

### 核心理念
- **系統性分析**: 從基礎到複雜，逐層解決問題
- **標準化流程**: 遵循固定的除錯步驟和檢查清單
- **完整性驗證**: 確保編譯、啟動、運行各階段都正常
- **文檔化記錄**: 詳細記錄問題和解決方案
- **可重現性**: 解決方案能夠重複應用

---

## 🔧 編譯除錯流程

### 階段一：環境準備檢查

#### 1.1 開發環境驗證
```bash
# 檢查Java版本
java -version
echo $JAVA_HOME

# 檢查Maven版本
mvn -version

# 檢查專案結構
tree src/ -I target
```

#### 1.2 必要檢查項目
- [ ] Java版本符合專案要求 
- [ ] Maven版本 3.6.0 以上
- [ ] 專案目錄結構正確
- [ ] pom.xml檔案存在且可讀取
- [ ] application.yml配置檔案存在

### 階段二：編譯驗證檢查

#### 2.1 基礎編譯檢查
```bash
# 清理專案
mvn clean

# 編譯主程式
mvn compile

# 編譯測試程式
mvn test-compile
```

#### 2.2 常見編譯錯誤處理

##### Java語法錯誤
```java
// 錯誤範例：缺少匯入語句
public class UserService {
    @Autowired
    private UserRepository userRepository; // 錯誤：缺少 import
}

// 正確範例：
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class UserService {
    @Autowired
    private UserRepository userRepository;
}
```

##### 型別不匹配錯誤
```java
// 錯誤範例：型別不匹配
public Optional<User> findUser(String id) {
    return userRepository.findById(id); // 錯誤：id應為Long型別
}

// 正確範例：
public Optional<User> findUser(Long id) {
    return userRepository.findById(id);
}
```

##### 註解錯誤
```java
// 錯誤範例：註解參數錯誤
@RequestMapping(value = "/users", method = RequestMethod.GET)
@ResponseBody // 多餘註解，@RestController已包含
public List<User> getUsers() {
    return userService.getAllUsers();
}

// 正確範例：
@GetMapping("/users")
public List<User> getUsers() {
    return userService.getAllUsers();
}
```

### 階段三：相依性檢查

#### 3.1 相依性分析
```bash
# 查看相依性樹
mvn dependency:tree

# 分析相依性問題
mvn dependency:analyze

# 解決相依性衝突
mvn dependency:resolve
```

#### 3.2 常見相依性問題

##### SpringBoot版本不相容
```xml
<!-- 錯誤範例：版本不匹配 -->
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.0</version>
</parent>

<dependencies>
    <!-- 錯誤：使用舊版Spring Security -->
    <dependency>
        <groupId>org.springframework.security</groupId>
        <artifactId>spring-security-web</artifactId>
        <version>5.7.2</version>
    </dependency>
</dependencies>

<!-- 正確範例：使用starter管理版本 -->
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.0</version>
</parent>

<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-security</artifactId>
    </dependency>
</dependencies>
```

##### MySQL驅動程式問題
```xml
<!-- 常見問題：缺少MySQL驅動 -->
<dependency>
    <groupId>mysql</groupId>
    <artifactId>mysql-connector-java</artifactId>
    <scope>runtime</scope>
</dependency>

<!-- 正確配置：使用最新驅動 -->
<dependency>
    <groupId>com.mysql</groupId>
    <artifactId>mysql-connector-j</artifactId>
    <scope>runtime</scope>
</dependency>
```

##### Validation API缺失
```xml
<!-- 補充驗證相依性 -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-validation</artifactId>
</dependency>
```

### 階段四：配置檔案驗證

#### 4.1 application.yml檢查

##### 資料庫連線配置
```yaml
# 錯誤範例：URL格式錯誤
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/thmcpa # 缺少參數
    username: root
    password: password

# 正確範例：完整配置
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/thmcpa?useSSL=false&serverTimezone=Asia/Taipei&allowPublicKeyRetrieval=true
    username: root
    password: password
    driver-class-name: com.mysql.cj.jdbc.Driver
```

##### JPA配置
```yaml
# 推薦的JPA配置
spring:
  jpa:
    hibernate:
      ddl-auto: validate # 生產環境使用validate
    show-sql: false # 生產環境關閉
    properties:
      hibernate:
        dialect: org.hibernate.dialect.MySQL8Dialect
        format_sql: true
    open-in-view: false # 避免Lazy Loading問題
```

##### 伺服器配置
```yaml
# 伺服器配置
server:
  port: 8088
  servlet:
    context-path: /api
  compression:
    enabled: true
    mime-types: text/html,text/xml,text/plain,text/css,text/javascript,application/javascript,application/json
```

#### 4.2 配置檔案驗證工具
```bash
# 使用Spring Boot配置處理器驗證
mvn spring-boot:run -Dspring-boot.run.arguments=--spring.config.location=classpath:/application.yml
```

### 階段五：應用程式啟動測試

#### 5.1 啟動檢查步驟
```bash
# 完整建置
mvn clean package -DskipTests

# 啟動應用程式
java -jar target/thmcpa-crew-import-0.0.1-SNAPSHOT.jar

# 檢查健康狀態
curl http://localhost:8088/actuator/health
```

#### 5.2 常見啟動錯誤

##### Bean循環依賴
```java
// 錯誤範例：循環依賴
@Service
public class UserService {
    @Autowired
    private OrderService orderService;
}

@Service 
public class OrderService {
    @Autowired
    private UserService userService; // 循環依賴
}

// 解決方案：使用@Lazy或重構設計
@Service
public class UserService {
    private final OrderService orderService;
    
    public UserService(@Lazy OrderService orderService) {
        this.orderService = orderService;
    }
}
```

##### 資料庫連線失敗
```yaml
# 檢查資料庫連線池配置
spring:
  datasource:
    hikari:
      maximum-pool-size: 10
      minimum-idle: 5
      idle-timeout: 300000
      connection-timeout: 20000
      validation-timeout: 3000
      leak-detection-threshold: 60000
```

##### Port被佔用
```bash
# 檢查連接埠使用情況
netstat -tulpn | grep :8088

# 終止佔用程式
kill -9 [PID]

# 或修改application.yml中的server.port
```

---

## 🔍 除錯技巧和工具

### 日誌分析技巧

#### 1. 啟用詳細日誌
```yaml
# application-debug.yml
logging:
  level:
    org.springframework: DEBUG
    org.hibernate: DEBUG
    com.tcci.thmcpa: DEBUG
  pattern:
    console: "%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n"
    file: "%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n"
  file:
    name: logs/debug.log
```

#### 2. 異常堆疊追蹤分析
```bash
# 關鍵錯誤訊息識別
grep -n "ERROR\|Exception\|Failed" logs/debug.log

# 查看完整堆疊追蹤
grep -A 20 "Exception" logs/debug.log
```

### Maven除錯命令

#### 相依性問題診斷
```bash
# 查看有效POM
mvn help:effective-pom

# 查看相依性衝突
mvn dependency:tree -Dverbose

# 強制更新相依性
mvn dependency:purge-local-repository

# 重新下載相依性
mvn dependency:resolve -U
```

#### 編譯問題診斷
```bash
# 詳細編譯輸出
mvn compile -X

# 清理並重新編譯
mvn clean compile -U

# 跳過測試的完整建置
mvn clean package -DskipTests -U
```

---

## 📊 效能診斷和優化

### 啟動效能分析

#### 1. 啟動時間測量
```yaml
# 啟用啟動時間報告
spring:
  main:
    log-startup-info: true
  application:
    startup-reporting:
      enabled: true
      
management:
  endpoints:
    web:
      exposure:
        include: startup
```

#### 2. Bean載入分析
```java
// 使用@Profile進行條件載入
@Service
@Profile("!test")
public class ProductionOnlyService {
    // 生產環境才載入的服務
}

// 使用@ConditionalOnProperty進行條件配置
@Component
@ConditionalOnProperty(name = "feature.email.enabled", havingValue = "true")
public class EmailService {
    // 依配置決定是否載入
}
```

### 記憶體使用分析

#### JVM參數優化
```bash
# 啟動時加入JVM監控參數
java -Xms512m -Xmx1024m \
     -XX:+PrintGCDetails \
     -XX:+PrintGCTimeStamps \
     -XX:+HeapDumpOnOutOfMemoryError \
     -XX:HeapDumpPath=/logs/heapdump.hprof \
     -jar target/thmcpa-crew-import-0.0.1-SNAPSHOT.jar
```

---

## ✅ 編譯除錯檢查清單

### 📋 環境準備檢查
- [ ] Java版本正確 (Java 17)
- [ ] Maven版本符合要求 (3.6.0+)
- [ ] IDE設定正確
- [ ] 專案結構完整
- [ ] Git狀態乾淨

### 🔧 編譯階段檢查
- [ ] `mvn clean` 執行成功
- [ ] `mvn compile` 無錯誤
- [ ] `mvn test-compile` 無錯誤
- [ ] 所有Java檔案語法正確
- [ ] 所有import語句正確
- [ ] 註解使用正確

### 📦 相依性檢查
- [ ] pom.xml語法正確
- [ ] SpringBoot版本一致
- [ ] 無相依性衝突
- [ ] 必要相依性完整
- [ ] 相依性範圍設定正確

### ⚙️ 配置檔案檢查
- [ ] application.yml語法正確
- [ ] 資料庫連線參數正確
- [ ] JPA設定適當
- [ ] 日誌設定完整
- [ ] Profile設定正確

### 🚀 啟動測試檢查
- [ ] 應用程式正常啟動
- [ ] 所有Bean正確載入
- [ ] 資料庫連線成功
- [ ] API端點正確註冊
- [ ] 健康檢查通過
- [ ] 無記憶體洩漏警告

### 📝 文檔記錄檢查
- [ ] 問題清單完整記錄
- [ ] 解決方案詳細說明
- [ ] 修改內容追蹤
- [ ] 驗證結果確認
- [ ] 知識庫更新

---

## 🎯 最佳實務建議

### 預防性措施
1. **定期更新相依性**: 使用 `mvn versions:display-dependency-updates` 檢查
2. **使用IDE靜態分析**: 啟用程式碼檢查和格式化
3. **建立CI/CD流水線**: 自動化編譯和測試
4. **程式碼評審**: 同儕檢視減少錯誤
5. **測試驅動開發**: 先寫測試再寫實作

### 除錯效率提升
1. **系統性分析**: 從簡單到複雜逐步排查
2. **保留日誌**: 詳細記錄除錯過程
3. **建立知識庫**: 累積常見問題解決方案
4. **工具輔助**: 使用IDE偵錯器和性能分析工具
5. **團隊協作**: 分享經驗和最佳實務

---

## 📚 相關資源

- [Spring Boot官方文檔](https://spring.io/projects/spring-boot)
- [Maven官方指南](https://maven.apache.org/guides/)
- [MySQL連接器文檔](https://dev.mysql.com/doc/connector-j/8.0/en/)
- [Java 17新特性](https://openjdk.java.net/projects/jdk/17/)
- [IntelliJ IDEA除錯指南](https://www.jetbrains.com/help/idea/debugging-code.html)
